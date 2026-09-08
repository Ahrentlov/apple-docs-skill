# Apple Developer Docs Skill

An agent skill for source-backed Apple and Swift documentation lookups. The
agent writes a short Python query that fetches and filters documentation before
returning relevant evidence to its context. No MCP server or third-party Python
packages are required.

New lookup features include bounded section/line reads with citations,
framework-scoped symbol discovery, compiler searches pinned to a branch/tag/commit,
and bounded comparisons of a file between two revisions. See the
[API guide](apple-developer-docs/SKILL.md) for signatures and coverage limits.

## Sources

- **Apple documentation:** DocC declarations, availability, deprecation,
  discussion, parameters, return values, related symbols, and section content.
- **Human Interface Guidelines:** topic discovery and structured page content.
- **Xcode release notes:** version discovery and DocC page fetching.
- **Documentation Archive:** title/facet search over legacy guides, Tech Notes,
  Q&As, and sample-code links. Read linked HTML with a browser tool.
- **Swift Evolution:** proposal metadata search with version/status filters and
  pagination; fetch proposal bodies through the GitHub helper.
- **Swift Forums:** topics and post excerpts from a search page.
- **Apple/SwiftLang repositories:** scoped search-link generation and file reads.
- **Swift compiler docs:** path search and bounded full-text search, plus a
  static compiler-phase overview.
- **WWDC:** search a community-maintained session index and fetch community notes.

Search-link generators return URLs, not search results. The skill explains how
to combine those links with an available browser/search tool. It distinguishes
primary documentation from community notes and discussions.

## Installation

```bash
npx skills add Ahrentlov/apple-docs-skill --skill apple-developer-docs
```

Or download the skill archive from
[Releases](https://github.com/Ahrentlov/apple-docs-skill/releases) and place the
`apple-developer-docs/` folder in your agent's skills directory.

Requires **Python 3.10+ on macOS or Linux**. Network access to the documentation
sources is needed. Normal agent execution permissions still apply.

## Usage

The skill is intended to activate for documentation lookups, not every Swift
programming question. Example requests:

- “Look up SwiftUI View and its platform availability.”
- “Find implemented Swift 6 proposals about async.”
- “Find forum discussion around SE-0461.”
- “Search WWDC sessions on concurrency and read the top session's notes.”
- “Show me the HIG topic on Dark Mode.”
- “Fetch the Swift source for Task.”
- “Find archived Core Data sample code.”
- “Search compiler docs for reborrow.”
- “What changed in Xcode 15.4?”

To invoke the runner directly from this checkout:

```bash
python3 apple-developer-docs/scripts/run.py --timeout 60 \
  'result = fetch_hig("buttons")'
```

For multiline queries, save code to a temporary file and pass `--file path.py`.
APIs and restricted builtins are preloaded. Assign the final output to `result`.
Check both the execution envelope's `success` and any API-level `error`.

## Why query code?

Apple documentation indexes and source files can be large. Filtering in Python
lets an agent return the declaration, relevant sections, and source URL without
loading the whole upstream response into context. One query can combine sources
and follow links. Token savings depend on the query and retained evidence; this
repository does not claim a measured universal reduction.

The design draws on the
[code execution with MCP architecture](https://www.anthropic.com/engineering/code-execution-with-mcp),
implemented here as a standalone skill. The instructions emphasize retaining
citations, availability, version information, and search-completeness metadata
alongside compact results.

Proposal metadata and complete HIG indexes are memoized within a process.
Separate CLI invocations start fresh; no disk cache is written.

## Execution model

A supervisor bounds wall time across a worker running documentation APIs and a
separate Python process running generated query code. Queries use AST validation,
restricted builtins, JSON IPC, and resource/output limits. HTTP helpers validate
HTTPS hosts, GitHub repository scope, and redirects, and bound response sizes.

**This is not an OS filesystem/network sandbox or a guarantee that arbitrary
Python is safe.** Processes run as the invoking user. Keep the host agent's normal
sandbox and approval controls. `--file` reads a supplied local query file before
validation. The supervisor uses POSIX fork and is intended for a single-threaded
CLI, not embedding in a multithreaded application.

The default wall deadline is 10 seconds, adjustable from 1 to 300. Captured prints
are capped at 64 KiB, query output at 1 MiB, and IPC messages at 8 MiB. A 50 MiB
query-process address-space limit is attempted but may not work on macOS; it does
not cover the API worker. See [security.md](apple-developer-docs/references/security.md)
and [sandbox.md](apple-developer-docs/references/sandbox.md) for the actual controls.

## Limitations

- Apple URL helpers and repository search helpers generate links only.
- DocC rendering covers common text, code, lists, tables, and cross-references.
  `unrendered_types` identifies unsupported content; consult the original page
  when it matters. Non-Swift language variants require the original page.
- HIG discovery walks a bounded topic index; `platform` is an annotation, not a
  filter. Partial fetches are disclosed and are not cached as complete indexes.
- Compiler text search has a file budget and per-file size cap. Failures and
  truncation are disclosed. Search terms must occur on the same line.
- Forum results cover one upstream search page, not all matches. WWDC notes are
  community-authored and are not available for every session.
- Upstream schemas, rate limits, and availability can change. Empty or partial
  results do not prove that documentation does not exist.

## Development

The installable skill lives in `apple-developer-docs/`: `SKILL.md` contains the
workflow, `scripts/` contains the runner and API adapters, and `references/`
contains source-specific signatures, schemas, and examples.

## License

MIT
