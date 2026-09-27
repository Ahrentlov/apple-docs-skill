# Apple Developer Docs Skill

An agent skill for source-backed Apple and Swift documentation lookups. The
agent writes a short Python query that fetches and filters documentation before
returning relevant evidence to its context. No MCP server or third-party Python
packages are required.

Apple documentation and HIG pages come back as Apple's own Markdown, so tables,
topics, and change logs survive; parsed DocC fields are available on request.
Other features include bounded section/line reads with citations,
framework-scoped symbol discovery, compiler searches pinned to a branch/tag/commit,
and bounded comparisons of a file between two revisions. See the
[API guide](apple-developer-docs/SKILL.md) for signatures and coverage limits.

## Sources

- **Apple documentation:** Apple's Markdown rendering of each page (tables,
  topics, relationships, availability metadata) with section/line selection, or
  parsed DocC fields (declarations, parameters, related symbols) on request.
- **Framework symbol index:** search every page Apple lists for a framework,
  including deprecated and beta APIs, with one fetch.
- **Platform availability:** introduced/deprecated versions and a status for a
  given platform and OS version.
- **Tutorials:** course listings and step-by-step tutorial pages as Markdown.
- **Human Interface Guidelines:** topic discovery and Markdown page content with section selection.
- **Xcode release notes:** version discovery and page fetching.
- **Documentation Archive:** title/facet search over legacy guides, Tech Notes,
  Q&As, and sample-code links. Read linked HTML with a browser tool.
- **Swift Evolution:** proposal metadata search with version/status filters and
  pagination; fetch proposal bodies through the GitHub helper.
- **Swift Forums:** topics and post excerpts from a search page.
- **Apple/SwiftLang repositories:** scoped search-link generation and file reads.
- **Swift compiler docs:** path search and bounded full-text search, plus a
  static compiler-phase overview.
- **WWDC:** search a community-maintained session index, read Apple's
  transcripts (with chapters and code samples), and fetch community notes.

Search-link generators return URLs, not search results. The skill explains how
to combine those links with an available browser/search tool. It distinguishes
primary documentation from community notes and discussions.

## Installation

```bash
npx skills add Ahrentlov/apple-docs-skill --skill apple-developer-docs
```

Update an installed copy with `npx skills update apple-developer-docs`.

Or download the skill archive from
[Releases](https://github.com/Ahrentlov/apple-docs-skill/releases) and place the
`apple-developer-docs/` folder in your agent's skills directory.

Requires **Python 3.10+ on macOS or Linux**. Network access to the documentation
sources is needed. Normal agent execution permissions still apply.

## Usage

The skill is intended to activate for documentation lookups, not every Swift
programming question. Example requests:

- “Look up SwiftUI View and its platform availability.”
- “Is glassEffect available on iOS 17?”
- “List SwiftUI's deprecated structs.”
- “What did Apple say about list performance in WWDC25 session 256?”
- “Walk me through the first Develop in Swift tutorial.”
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
- Pages default to Apple's Markdown. The optional DocC JSON rendering covers
  common text, code, lists, tables, and cross-references; its `unrendered_types`
  identifies unsupported content. Non-Swift language variants require the
  original page.
- HIG discovery walks a bounded topic index; `platform` is an annotation, not a
  filter. Partial fetches are disclosed and are not cached as complete indexes.
- Compiler text search has a file budget and per-file size cap. Failures and
  truncation are disclosed. Search terms must occur on the same line.
- Forum results cover one upstream search page, not all matches. WWDC notes are
  community-authored and are not available for every session. Apple transcripts
  exist only for sessions Apple still hosts on developer.apple.com.
- Symbol search covers Apple's navigator index for one framework; symbols
  documented under another framework are not included.
- Upstream schemas, rate limits, and availability can change. Empty or partial
  results do not prove that documentation does not exist.

## Development

The installable skill lives in `apple-developer-docs/`: `SKILL.md` contains the
workflow, `scripts/` contains the runner and API adapters, and `references/`
contains source-specific signatures, schemas, and examples.

Tests live in `tests/` and use only the standard library. Offline tests replace
the network with canned responses; live tests query developer.apple.com and
run only with `APPLE_DOCS_LIVE=1`:

```bash
python3 -m unittest discover tests
APPLE_DOCS_LIVE=1 python3 -m unittest discover tests
```

CI runs the offline tests on every push and pull request (Python 3.10 and
3.13) and the live tests weekly, which catches upstream format changes.

## License

MIT
