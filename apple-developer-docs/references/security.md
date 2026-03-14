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

### Blocked Patterns (Regex)
- `import` - No external modules
- `__name__`, `__class__` - No dunder attributes
- `open()` - No file access
- `exec()`, `eval()`, `compile()` - No dynamic execution
- `globals()`, `locals()`, `vars()` - No namespace inspection
- `getattr()`, `setattr()`, `delattr()` - No attribute manipulation
- `os.`, `sys.`, `subprocess.` - No system access

### AST Validation
Code is parsed and validated structurally:
- Import statements blocked
- Dangerous function calls blocked
- Dunder attribute access blocked

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

1. **Regex match:** Immediate rejection with error message
2. **AST violation:** Rejection with specific error
3. **Timeout:** Process killed, TimeoutError returned
4. **Memory exceeded:** Process killed by OS
5. **No `result` variable:** Warning returned (code runs but result is None)
