"""
Code Security Validation for Sandbox Execution
===============================================

Provides AST-based static analysis to validate code before execution.
These checks constrain generated code; they are not a substitute for OS sandboxing.

Security Strategy:
1. AST validation catches dangerous constructs structurally (not inside strings/comments)
2. Restricted builtins limit the capabilities available to accepted code
"""

import ast
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of code validation."""
    is_safe: bool
    errors: List[str]
    warnings: List[str]

    @classmethod
    def safe(cls) -> 'ValidationResult':
        return cls(is_safe=True, errors=[], warnings=[])

    @classmethod
    def unsafe(cls, errors: List[str], warnings: Optional[List[str]] = None) -> 'ValidationResult':
        return cls(is_safe=False, errors=errors, warnings=warnings or [])


class CodeValidator:
    """
    Validates Python code for safe sandbox execution.

    This validator blocks:
    - Import statements (no external modules)
    - Dunder access (__name__, __class__, etc.)
    - Dangerous builtins (exec, eval, open, etc.)
    - Attribute introspection (getattr, setattr, etc.)
    """

    # Modules blocked from attribute access (e.g. os.system, sys.path)
    BLOCKED_MODULES = {'os', 'sys', 'subprocess'}

    # Functions blocked from sandbox execution
    BLOCKED_FUNCTIONS = {
        'exec', 'eval', 'compile', 'open',
        'getattr', 'setattr', 'delattr', 'hasattr',
        'globals', 'locals', 'vars', 'dir',
        'breakpoint', 'input', '__import__', 'format', 'format_map',
    }

    def __init__(self, max_code_length: int = 10000):
        """
        Initialize the code validator.

        Args:
            max_code_length: Maximum allowed code length in characters
        """
        self.max_code_length = max_code_length

    def validate(self, code: str) -> ValidationResult:
        """
        Validate code for sandbox execution.

        Args:
            code: Python code to validate

        Returns:
            ValidationResult indicating if code is safe to execute
        """
        errors = []
        warnings = []

        # Check 1: Code length
        if len(code) > self.max_code_length:
            return ValidationResult.unsafe([
                f"Code too long: {len(code)} chars (max {self.max_code_length})"
            ])

        # Check 2: Empty code
        if not code or not code.strip():
            return ValidationResult.unsafe(["Empty code provided"])

        try:
            tree = ast.parse(code)
            ast_errors, has_result = self._scan_ast(tree)
            if ast_errors:
                return ValidationResult.unsafe(ast_errors)
        except (RecursionError, MemoryError):
            return ValidationResult.unsafe(["Code is too deeply nested to validate"])
        except SyntaxError as e:
            return ValidationResult.unsafe([f"Syntax error: {e.msg} at line {e.lineno}"])

        if not has_result:
            warnings.append("Code should assign to 'result' variable to return data")

        return ValidationResult(is_safe=True, errors=[], warnings=warnings)

    def _scan_ast(self, tree: ast.AST) -> tuple[List[str], bool]:
        """Single-pass AST walk returning (errors, has_result_assignment)."""
        errors: List[str] = []
        has_result = False

        for node in ast.walk(tree):
            match node:
                case ast.Import() | ast.ImportFrom():
                    errors.append("Import statements are not allowed")

                case ast.Call(func=ast.Name(id=func_name)) if func_name in self.BLOCKED_FUNCTIONS:
                    errors.append(f"Function '{func_name}' is not allowed")

                case ast.Attribute(attr=attr) if attr in self.BLOCKED_FUNCTIONS:
                    errors.append(f"Function '{attr}' is not allowed")

                case ast.Attribute(value=ast.Name(id=module_name)) if module_name in self.BLOCKED_MODULES:
                    errors.append(f"Access to '{module_name}' module is not allowed")

                case ast.Attribute(attr=attr) if attr in {'gi_frame', 'gi_code', 'gi_yieldfrom', 'cr_frame', 'cr_code', 'cr_await', 'ag_frame', 'ag_code', 'ag_await', 'tb_frame', 'tb_next', 'f_back', 'f_globals', 'f_locals', 'f_builtins', 'f_code'}:
                    errors.append(f"Introspection attribute '{attr}' is not allowed")

                case ast.Attribute(attr=attr) if attr.startswith('__') and attr.endswith('__'):
                    errors.append(f"Dunder attribute access '{attr}' is not allowed")

                case ast.Name(id=name) if name in self.BLOCKED_FUNCTIONS:
                    errors.append(f"Reference to '{name}' is not allowed")

                case ast.Name(id=name) if name.startswith('__') and name.endswith('__'):
                    errors.append(f"Dunder name '{name}' is not allowed")

                case ast.Assign(targets=targets):
                    if any(isinstance(t, ast.Name) and t.id == 'result' for t in targets):
                        has_result = True

                case ast.AnnAssign(target=ast.Name(id='result')):
                    has_result = True

        return errors, has_result
