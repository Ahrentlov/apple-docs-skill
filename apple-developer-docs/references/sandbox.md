# Query execution

Run a short Python query with `scripts/run.py`, using an inline argument or
`--file /path/to/query.py`. The CLI reads at most 10,001 characters from a query
file so overlong input is rejected. Assign the output to `result`; omitting it
fails with `MissingResultError`. No imports are needed or permitted.

## Builtins

- Data types: `list`, `dict`, `set`, `tuple`, `str`, `int`, `float`, `bool`, `bytes`
- Iteration: `len`, `range`, `enumerate`, `zip`, `map`, `filter`, `reversed`, `sorted`, `iter`, `next`
- Aggregation: `min`, `max`, `sum`, `any`, `all`
- Math: `abs`, `round`, `pow`, `divmod`
- Type checks: `isinstance`, `type`
- Output: `print`, `repr`
- Exceptions: `Exception`, `ValueError`, `KeyError`, `TypeError`, `IndexError`, `AttributeError`, `RuntimeError`, `ZeroDivisionError`

Use f-strings, not `str.format` or `format_map`. File, network, process, and
introspection builtins are not exposed. API wrappers accept the positional and
keyword arguments documented in the source references.

## Limits

- Wall time: 10 seconds by default; `--timeout` accepts integers from 1 to 300.
  Includes API calls. Use 60 seconds for cold indexes and multi-source queries.
- Query CPU time: the configured timeout; memory: attempts a 50 MiB address-space
  limit, which may not work on macOS and does not cover the API worker.
- Code: 10,000 characters; prints: 64 KiB; serialized output: 1 MiB; IPC: 8 MiB
  per message. Filter large results before returning them.
- Requires Python 3.10+ on macOS/Linux. No external Python packages are needed.

## Output

```python
{
    "success": bool,
    "result": ...,                 # query's result, including empty/null values
    "stdout": str,                 # captured print output, when nonempty
    "stderr": str,                 # subprocess diagnostics, when nonempty
    "error": str,                  # on failure
    "error_type": str,             # on failure
    "execution_time_ms": int,
    "api_calls_made": int,
    "validation_warnings": list,   # when nonempty
}
```

Empty/null optional fields are omitted. `success`, `result`, `execution_time_ms`, and
`api_calls_made` are always included for executions. CLI argument/file-reading
errors can have a smaller envelope or argparse diagnostics on stderr.
The exit code is zero only when query execution succeeds. An API error returned
as `result` does not make the execution itself fail; inspect both levels.
On supervisor timeout/crash, `api_calls_made` may be zero even if requests began.

See [security.md](security.md) for the actual security boundary.
