# Sandbox Security Model

## Architecture

```
┌─────────────────┐     IPC (stdin/stdout)     ┌──────────────────┐
│  MCP Server     │◄──────────────────────────►│  Sandbox Process │
│  (Parent)       │                            │  (Subprocess)    │
│                 │  {"__api_call__": ...}     │                  │
│  - Database     │◄─────────────────────────  │  - User code     │
│  - API Bridge   │  {"result": ...}           │  - Restricted    │
│                 │ ─────────────────────────► │    builtins      │
└─────────────────┘                            └──────────────────┘
```

**Primary boundary:** Subprocess isolation (OS-level)
**Secondary:** Static code validation (defense-in-depth)

## Forbidden Operations

### AST Validation
Code is parsed and validated structurally (not via regex, so strings and comments are ignored):
- Import statements (`import`, `from ... import`)
- Blocked function calls (`exec`, `eval`, `compile`, `open`, `getattr`, `setattr`, `delattr`, `hasattr`, `globals`, `locals`, `vars`, `dir`, `breakpoint`, `input`, `__import__`)
- Blocked module access (`os.`, `sys.`, `subprocess.`)
- Dunder attribute access (`__class__`, `__name__`, `__subclasses__`, etc.)
- Dunder name references (`__builtins__`, etc.)

## Resource Limits

```python
timeout = 5          # seconds
max_memory = 50      # MB
max_code_length = 10000  # characters
max_output = 10 * 1024   # bytes
```

## IPC Protocol

Sandbox calls APIs via stdout/stdin JSON:

```json
// Request (sandbox → parent)
{"__api_call__": {"func": "search_proposals", "args": ["async"]}}

// Response (parent → sandbox)
{"result": {"proposals": [...]}}
```

## Allowed Builtins (Complete List)

```python
# Type constructors
list, dict, set, tuple, str, int, float, bool, bytes

# Iteration
len, range, enumerate, zip, map, filter, reversed

# Aggregation
min, max, sum, any, all, sorted

# Math
abs, round, pow, divmod

# Type checking
isinstance, type

# Output
print, repr

# Constants
True, False, None
```

## What Happens on Violation

1. **AST violation:** Rejection with specific error
2. **Timeout:** Process killed, TimeoutError returned
3. **Memory exceeded:** Process killed by OS
4. **No `result` variable:** Warning returned (code runs but result is None)
