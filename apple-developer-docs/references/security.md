# Execution and security model

## Boundary

The CLI validates generated Python, then supervises a worker that executes API
handlers. A second Python process runs the query with restricted builtins and
calls the worker through JSON IPC. The supervisor enforces wall time across both
query execution and network/API work, terminating the worker and query process
and removing its temporary directory on completion or timeout.

This is a restricted execution environment, **not OS confinement**. Subprocesses
run as the current user; AST checks and builtin restrictions are not proof that
hostile Python cannot escape. Use an agent/OS sandbox for that boundary. Do not
interpret an allowlist of `run.py` as permission to execute arbitrary hostile
code. The CLI's `--file` option reads a user-supplied query file in the calling
process before validation; it is not restricted to the worker's directory.

The CLI requires macOS or Linux and Python 3.10+. Its supervisor uses POSIX fork
before API threads are created. `SandboxExecutor` is intended for this
single-threaded CLI, not embedding inside a multithreaded application.

## Controls

- AST validation rejects imports, dangerous builtins and aliases, dunder access,
  frame/generator introspection, and `str.format`/`format_map` traversal. Use
  f-strings for formatting. Strings and comments are data, not AST operations.
- Query Python starts in isolated mode (`-I`) with a temporary working directory
  and a minimal environment. Only data operations and registered API wrappers
  are exposed; file, socket, and process APIs are not supplied to query code.
- API wrappers come from the same public registry as the handlers. Positional
  and keyword arguments cross IPC as JSON, with no object deserialization.
- The supervisor applies the configured wall deadline (10 seconds by default,
  1–300 seconds allowed), including blocking API requests. Process shutdown may
  add a short cleanup interval.
- Query CPU time is limited to the configured timeout. A 50 MiB `RLIMIT_AS` is
  attempted, but may be unavailable or ineffective on macOS. This limit does
  not constrain API-worker memory. Resource limits are not a general DoS guarantee.
- Code is limited to 10,000 characters, captured prints to 64 KiB, serialized
  query output to 1 MiB, and individual IPC messages to 8 MiB. Oversized or
  unserializable output fails explicitly rather than being silently cut off.
- HTTP responses are bounded to 32 MiB for indexes/DocC, 1,000,000 bytes for
  GitHub files, 500,000 bytes for WWDC notes, and a 1 MiB searchable prefix per
  compiler file (plus one probe byte to detect truncation). Oversized compiler
  files retain complete-line prefix matches and appear in `truncated_files`;
  failed downloads appear in `failed_files`.
- HTTPS hosts and GitHub repository scope are validated on initial requests
  **and redirects**. Supported hosts are developer.apple.com, download.swift.org,
  swift.org, www.swift.org, forums.swift.org, github.com, api.github.com, and
  raw.githubusercontent.com. GitHub access is limited to apple/swiftlang plus
  the specific wwdcnotes/wwdcnotes repository used by WWDC APIs. The public
  `fetch_github_file` helper only accepts apple/swiftlang. These are application
  checks on HTTP helpers, not an OS egress policy.

## External content

Fetched documents and search metadata are third-party data. Text-bearing API
results include `content_notice`; GitHub file and WWDC note bodies also carry
`BEGIN EXTERNAL CONTENT` / `END EXTERNAL CONTENT` markers. An exact end-marker
inside fetched text is neutralized. Markers provide context, not sanitization
or a prompt-injection guarantee. Treat community forum posts and WWDC notes as
community sources, and retain source URLs in filtered results.

## IPC

```json
{"__api_call__": {"func": "search_proposals", "args": ["async"], "kwargs": {"version": "6"}}}
```

The API worker returns `{"result": ...}` or an IPC-level `{"error": ...}`.
An API may itself return an error dictionary; that remains ordinary query data.
See [sandbox.md](sandbox.md) for the final execution envelope and builtins.
