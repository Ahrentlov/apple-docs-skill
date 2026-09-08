"""
Sandboxed Python Execution Environment
======================================

Executes user-provided Python code in an isolated subprocess with:
- Resource limits (CPU time, memory)
- Restricted builtins
- Dynamic API calls via IPC (stdin/stdout)
- No file or network builtins exposed to generated code

Security Model:
- AST checks and restricted builtins constrain generated code; this is not OS confinement
- A supervising process bounds wall time, including API calls
- Resource and output limits bound common accidental resource exhaustion

IPC Protocol:
- Sandbox writes API requests to stdout as JSON: {"__api_call__": {"func": "name", "args": [...]}}
- Parent reads request, executes API, writes response to stdin
- Sandbox reads response and continues execution
"""

import subprocess
import tempfile
import json
import os
import sys
import time
import multiprocessing
import signal
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, fields

from security import CodeValidator


@dataclass
class ExecutionResult:
    """Result of sandbox code execution."""
    success: bool
    result: Any = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time_ms: int = 0
    validation_warnings: list = None
    api_calls_made: int = 0

    def __post_init__(self):
        if self.validation_warnings is None:
            self.validation_warnings = []

    def to_dict(self) -> Dict:
        """Convert to a JSON-serializable dict for the run.py output envelope.

        Builds the dict shallowly via dataclasses.fields (not asdict, which
        would recurse into deeply-nested user `result` data and overflow the
        parent's recursion limit). Iterating fields keeps this in sync with the
        dataclass automatically — no hand-maintained field list to drift.
        """
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        return {k: v for k, v in d.items() if k in {"success", "result", "execution_time_ms", "api_calls_made"} or (v is not None and v != [] and v != "")}


class SandboxExecutor:
    """
    Executes Python code in an isolated subprocess with dynamic API access.

    The executor:
    1. Validates code statically (defense-in-depth)
    2. Spawns subprocess with IPC channel
    3. Handles API calls from sandbox via stdin/stdout
    4. Returns results
    """

    # Template for the sandbox script with IPC support
    SANDBOX_TEMPLATE = '''
import json
import sys
import resource

# Set resource limits (Unix only)
try:
    resource.setrlimit(resource.RLIMIT_CPU, ({timeout}, {timeout}))
    memory_bytes = {max_memory_mb} * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
except (ValueError, resource.error):
    pass

# Restricted builtins
ALLOWED_BUILTINS = {{
    'len': len, 'range': range, 'enumerate': enumerate, 'zip': zip,
    'map': map, 'filter': filter, 'reversed': reversed,
    'iter': iter, 'next': next,
    'min': min, 'max': max, 'sum': sum, 'any': any, 'all': all, 'sorted': sorted,
    'abs': abs, 'round': round, 'pow': pow, 'divmod': divmod,
    'list': list, 'dict': dict, 'set': set, 'tuple': tuple,
    'str': str, 'int': int, 'float': float, 'bool': bool, 'bytes': bytes,
    'isinstance': isinstance, 'type': type,
    'print': print, 'repr': repr,
    'Exception': Exception, 'ValueError': ValueError, 'KeyError': KeyError,
    'TypeError': TypeError, 'IndexError': IndexError, 'AttributeError': AttributeError,
    'RuntimeError': RuntimeError, 'ZeroDivisionError': ZeroDivisionError,
    'True': True, 'False': False, 'None': None,
}}

# API implementations remain in the worker; only JSON crosses this bridge.
def make_api(func_name):
    def call(*args, **kwargs):
        request = {{"__api_call__": {{"func": func_name, "args": args, "kwargs": kwargs}}}}
        wire = json.dumps(request)
        if len(wire.encode('utf-8')) > {max_ipc_bytes}:
            raise ValueError("API request exceeds IPC limit")
        sys.stdout.write(wire + "\\n")
        sys.stdout.flush()
        response_line = sys.stdin.readline({max_ipc_bytes} + 1)
        if not response_line:
            raise RuntimeError("API bridge closed")
        response = json.loads(response_line)
        if "error" in response:
            raise RuntimeError(response['error'])
        return response['result']
    return call

namespace = {{'__builtins__': ALLOWED_BUILTINS}}
for api_name in {api_names}:
    namespace[api_name] = make_api(api_name)

# User code execution
user_output = []
output_bytes = 0
original_print = print

def capturing_print(*args, **kwargs):
    """Capture print output."""
    global output_bytes
    import io
    output = io.StringIO()
    kwargs['file'] = output
    original_print(*args, **kwargs)
    value = output.getvalue()
    output_bytes += len(value.encode("utf-8"))
    if output_bytes > 65536:
        raise ValueError("Printed output exceeds 64 KiB; filter before printing")
    user_output.append(value)

namespace['print'] = capturing_print
ALLOWED_BUILTINS['print'] = capturing_print

try:
    exec({user_code}, namespace)

    if 'result' in namespace:
        result = namespace['result']
        output = {{"success": True, "result": result, "stdout": "".join(user_output)}}
    else:
        output = {{"success": False, "error": "No 'result' variable set", "error_type": "MissingResultError", "stdout": "".join(user_output)}}

except Exception as e:
    output = {{
        "success": False,
        "error": str(e),
        "error_type": type(e).__name__,
        "stdout": "".join(user_output)
    }}

# Final output marker
sys.stdout.write("__SANDBOX_COMPLETE__\\n")
try:
    wire = json.dumps(output, default=str)
    if len(wire.encode('utf-8')) > {max_output_bytes}:
        raise ValueError("Result exceeds 1 MiB; filter before returning")
except (ValueError, TypeError, RecursionError) as e:
    wire = json.dumps({{"success": False, "error": str(e), "error_type": "OutputError"}})
sys.stdout.write(wire + "\\n")
sys.stdout.flush()
'''

    def __init__(
        self,
        timeout: int = 10,
        max_memory_mb: int = 50,
        python_path: Optional[str] = None,
        api_handlers: Optional[Dict[str, Callable]] = None
    ):
        """
        Initialize the sandbox executor.

        Args:
            timeout: Maximum execution time in seconds
            max_memory_mb: Maximum memory usage in MB
            python_path: Path to Python interpreter
            api_handlers: Dict mapping function names to handler callables
        """
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 300:
            raise ValueError("timeout must be an integer from 1 to 300 seconds")
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.python_path = python_path or sys.executable
        self.validator = CodeValidator()
        self.api_handlers = api_handlers or {}

    def execute(self, code: str, api_handlers: Optional[Dict[str, Callable]] = None) -> ExecutionResult:
        """
        Execute code in the sandbox with dynamic API access.

        Args:
            code: Python code to execute
            api_handlers: Dict mapping function names to handler callables

        Returns:
            ExecutionResult with success status, result, and any errors
        """
        start_time = time.monotonic()
        validation_warnings = []
        handlers = self.api_handlers if api_handlers is None else api_handlers

        # Step 1: Validate code
        validation = self.validator.validate(code)
        if not validation.is_safe:
            return ExecutionResult(
                success=False,
                error="; ".join(validation.errors),
                error_type="ValidationError",
                execution_time_ms=int((time.monotonic() - start_time) * 1000)
            )
        validation_warnings = validation.warnings

        # Step 2: Create sandbox script
        try:
            script = self._create_sandbox_script(code, handlers)
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Failed to prepare sandbox: {str(e)}",
                error_type="PreparationError",
                execution_time_ms=int((time.monotonic() - start_time) * 1000)
            )

        # Step 3: Execute with IPC
        try:
            result = self._supervise(script, handlers)
            result.validation_warnings = validation_warnings
            result.execution_time_ms = int((time.monotonic() - start_time) * 1000)
            return result
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error=f"Execution timed out after {self.timeout} seconds",
                error_type="TimeoutError",
                execution_time_ms=int((time.monotonic() - start_time) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Execution failed: {str(e)}",
                error_type="ExecutionError",
                execution_time_ms=int((time.monotonic() - start_time) * 1000)
            )

    def _supervise(self, script, handlers):
        # POSIX-only, like resource.setrlimit. Fork preserves injected handlers
        # for offline tests. The CLI calls this before starting any threads.
        context = multiprocessing.get_context("fork")
        receiver, sender = context.Pipe(duplex=False)
        with tempfile.TemporaryDirectory(prefix="apple-docs-") as directory:
            worker = context.Process(target=_execute_worker, args=(sender, self, script, handlers, directory))
            worker.start()
            sender.close()
            code_pid = None
            completed = False
            deadline = time.monotonic() + self.timeout
            try:
                while receiver.poll(max(0, deadline - time.monotonic())):
                    message = receiver.recv_bytes(MAX_IPC_BYTES)
                    if message.startswith(b"pid:"):
                        code_pid = int(message[4:])
                        continue
                    completed = True
                    return ExecutionResult(**json.loads(message))
                raise subprocess.TimeoutExpired(cmd="documentation worker", timeout=self.timeout)
            except EOFError:
                return ExecutionResult(success=False, error="Documentation worker exited without a result", error_type="ProcessError")
            finally:
                if completed:
                    worker.join(timeout=0.2)
                if code_pid is not None and not completed:
                    try:
                        os.kill(code_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=0.2)
                    if worker.is_alive():
                        worker.kill()
                worker.join()
                receiver.close()
                worker.close()

    def _create_sandbox_script(self, code: str, handlers=None) -> str:
        return self.SANDBOX_TEMPLATE.format(
            timeout=self.timeout,
            max_memory_mb=self.max_memory_mb,
            user_code=repr(code),
            api_names=repr(list(self.api_handlers if handlers is None else handlers)),
            max_ipc_bytes=MAX_IPC_BYTES,
            max_output_bytes=MAX_OUTPUT_BYTES,
        )

    def _handle_api_call(self, data: Dict, handlers: Dict[str, Callable]) -> Dict:
        """Execute an API call from the sandbox and return the IPC response."""
        call_info = data["__api_call__"]
        func_name = call_info["func"]
        args = call_info["args"]

        if func_name not in handlers:
            return {"error": f"Unknown API function: {func_name}"}

        try:
            return {"result": handlers[func_name](*args, **call_info.get("kwargs", {}))}
        except Exception as e:
            return {"error": str(e)}

    def _run_with_ipc(self, script: str, handlers: Dict[str, Callable], directory: str) -> ExecutionResult:
        """
        Run sandbox with IPC for API calls.

        Args:
            script: Sandbox script to execute
            handlers: API handlers

        Returns:
            ExecutionResult
        """
        # Write script to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir=directory) as f:
            f.write(script)
            script_path = f.name

        api_calls_made = 0
        collected_output = []

        try:
            env = {
                'PATH': os.environ.get('PATH', ''),
                'PYTHONPATH': '',
                'HOME': directory,
            }

            # Start subprocess with pipes for IPC
            proc = subprocess.Popen(
                [self.python_path, "-I", "-B", script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=directory
            )

            self._worker_sender.send_bytes(f"pid:{proc.pid}".encode())

            # Process IPC until completion or timeout
            deadline = time.time() + self.timeout
            result_line = None

            while True:
                if time.time() > deadline:
                    proc.kill()
                    raise subprocess.TimeoutExpired(cmd=script_path, timeout=self.timeout)

                line = proc.stdout.readline(MAX_IPC_BYTES + 1)
                if not line:
                    break

                if len(line.encode("utf-8")) > MAX_IPC_BYTES:
                    raise ValueError("Sandbox message exceeds IPC limit")
                line = line.strip()

                if line == "__SANDBOX_COMPLETE__":
                    result_line = proc.stdout.readline(MAX_IPC_BYTES + 1)
                    break

                # Try to parse as API call
                api_call = None
                try:
                    data = json.loads(line)
                    if "__api_call__" in data:
                        api_call = data
                except json.JSONDecodeError:
                    pass

                if api_call:
                    api_calls_made += 1
                    response = self._handle_api_call(api_call, handlers)
                    wire = json.dumps(response)
                    if len(wire.encode("utf-8")) > MAX_IPC_BYTES:
                        wire = json.dumps({"error": "API response exceeds 8 MiB IPC limit"})
                    proc.stdin.write(wire + "\n")
                    proc.stdin.flush()
                else:
                    collected_output.append(line)

            # Wait for process to finish
            proc.wait(timeout=1)
            stderr = proc.stderr.read()

            # Parse final result
            if result_line is None:
                return ExecutionResult(
                    success=False,
                    stdout="\n".join(collected_output),
                    stderr=stderr,
                    error="Sandbox process exited without completing (possible resource limit or crash)",
                    error_type="ProcessError",
                    api_calls_made=api_calls_made
                )

            try:
                output = json.loads(result_line)
                return ExecutionResult(
                    success=output.get("success", False),
                    result=output.get("result"),
                    stdout=output.get("stdout", ""),
                    stderr=stderr,
                    error=output.get("error"),
                    error_type=output.get("error_type"),
                    api_calls_made=api_calls_made
                )
            except json.JSONDecodeError:
                return ExecutionResult(
                    success=False,
                    stdout="\n".join(collected_output),
                    stderr=stderr,
                    error="Failed to parse sandbox output",
                    error_type="ParseError",
                    api_calls_made=api_calls_made
                )

        finally:
            if "proc" in locals():
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                for stream in (proc.stdin, proc.stdout, proc.stderr):
                    stream.close()
            try:
                os.unlink(script_path)
            except OSError:
                pass


MAX_OUTPUT_BYTES = 1024 * 1024
MAX_IPC_BYTES = 8 * 1024 * 1024


def _execute_worker(sender, executor, script, handlers, directory):
    executor._worker_sender = sender
    def terminate(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, terminate)
    try:
        result = executor._run_with_ipc(script, handlers, directory)
    except Exception as exc:
        result = ExecutionResult(success=False, error=str(exc), error_type=type(exc).__name__)
    try:
        wire = json.dumps(result.to_dict()).encode("utf-8")
        if len(wire) > MAX_IPC_BYTES:
            wire = json.dumps({"success": False, "error": "Worker output exceeds limit", "error_type": "OutputError"}).encode()
        sender.send_bytes(wire)
    finally:
        sender.close()
