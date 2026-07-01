# Sandbox Model

User code runs in a subprocess sandbox managed by `scripts/run.py`. The host
process holds the API handlers; user code calls them via line-oriented JSON
IPC. Always assign the final output to a variable named `result`.

## Allowed builtins

- Data types: `list`, `dict`, `set`, `tuple`, `str`, `int`, `float`, `bool`, `bytes`
- Iteration: `len`, `range`, `enumerate`, `zip`, `map`, `filter`, `reversed`, `sorted`, `iter`, `next`
- Aggregation: `min`, `max`, `sum`, `any`, `all`
- Math: `abs`, `round`, `pow`, `divmod`
- Type checks: `isinstance`, `type`
- Output: `print`, `repr`
- Exceptions: `Exception`, `ValueError`, `KeyError`, `TypeError`, `IndexError`, `AttributeError`, `RuntimeError`, `ZeroDivisionError`

`import` statements are not allowed. All API functions are pre-loaded into the namespace.

## Resource limits

- CPU: per-call timeout (default 10s; override with `--timeout 30` etc.).
- Memory: `RLIMIT_AS` set to the executor's `max_memory_mb` (default 50 MB).
- Output: max bytes capped to keep the JSON envelope small.

## Output shape

```python
{
    "success": bool,
    "result": Any,            # whatever the user code assigned to `result`
    "stdout": str,            # captured prints
    "error": str | None,      # exception message on failure
    "error_type": str | None, # exception type
    "execution_time_ms": int,
    "api_calls_made": int
}
```

For the AST-level allow / deny rules and the rationale, see `security.md`.
