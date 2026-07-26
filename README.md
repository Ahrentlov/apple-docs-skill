# Apple Developer Docs Skill

An agent skill that gives the Agent efficient access to Apple developer documentation through sandboxed Python code execution.

## What it does

Instead of making multiple API calls and processing large JSON responses, this skill lets the Agent write Python code that fetches and filters Apple documentation directly — significantly reducing token usage.

### Available APIs

- **Apple Documentation** — Fetch and parse docs from developer.apple.com (works for `/documentation/` and `/design/human-interface-guidelines/`)
- **Documentation Archive** — Search ~5200 legacy Tech Notes, Tech Q&As, Sample Code, Guides, and Release Notes from developer.apple.com/library/archive
- **Swift Evolution** — Search 500+ proposals by keyword, version, or status
- **Swift Forums** — Search forums.swift.org for discussions, pitches, and review threads
- **Swift Repositories** — Search and fetch source code from Apple/SwiftLang GitHub repos
- **Swift Compiler Internals** — Search compiler docs in `swiftlang/swift/docs` by filename or full text (SIL, ABI, type checker, IRGen, generics)
- **WWDC Sessions** — Search ~3000 sessions; fetch community-written markdown notes
- **Human Interface Guidelines** — Search and fetch HIG topics (Buttons, Dark Mode, Accessibility, …)
- **Xcode Release Notes** — Discover every Xcode release-notes page; resolve versions to URLs

## Installation

```bash
npx skills add Ahrentlov/apple-docs-skill --skill apple-developer-docs
```

Or download the `.zip` from [Releases](https://github.com/Ahrentlov/apple-docs-skill/releases) and place the `apple-developer-docs/` folder in your agent's skills directory.

## Usage

The skill activates automatically when you ask about Apple APIs, Swift Evolution proposals, Swift Forums discussions, WWDC sessions, or Human Interface Guidelines.

**Example prompts:**
- "Look up the SwiftUI View protocol"
- "Find Swift Evolution proposals about async"
- "What's the forum discussion around SE-0461?"
- "Search WWDC sessions on concurrency and fetch the top one"
- "Show me the HIG topic on Dark Mode"
- "Fetch the Swift source for Task"
- "Find archived Core Data sample code"
- "Grep the compiler docs for 'reborrow'"
- "What changed in Xcode 15.4?"

## Token efficiency

The sandbox filters API responses before they enter context. Across all tools:

| API | Typical reduction |
|-----|-------------------|
| `fetch_documentation` / `fetch_hig` | 97% — SwiftUI View: 94KB → 1.7KB |
| `search_wwdc_sessions` | 95% — ~3000 sessions filtered to title + description matches |
| `search_swift_forums` | 95% — 50 topics down to top 5 with key fields |
| `search_proposals` | 92% — dozens of proposals to title/status/SE number |
| `search_compiler_docs_text` | 90% — full file content reduced to matched lines |
| `fetch_github_file` | 74–90% — full source to first 30 lines |
| `get_proposal` | 73% — full metadata to summary fields |

The Agent controls the depth — a quick lookup returns ~120 chars, a deep dive ~10KB.

## Why code execution?

This skill adapts the [code execution architecture](https://www.anthropic.com/engineering/code-execution-with-mcp) originally designed for MCP servers and applies it as a standalone skill. Instead of direct tool calls, the Agent writes Python code that runs in a sandboxed subprocess, filtering and combining API results before they enter context — no MCP server required.

This matters most for data-heavy APIs — Apple documentation pages, 500+ Swift Evolution proposals, forum threads, and GitHub source files can be large. Running queries and filtering in the sandbox means only the relevant fields come back. Combining multiple queries in a single execution also cuts down on round trips.

## Security model

Security scanners will flag this skill for code execution and network access. Both are its purpose, not an accident: the skill exists to run generated Python and fetch remote documentation.

### Why sandbox agent-written code at all?

An agent running this skill typically has shell access already, so the sandbox is not about protecting the machine from the agent in general. It exists for three specific reasons:

1. **It makes the skill safe to auto-approve.** Users allowlist `run.py` invocations once. Without the sandbox, that grant would mean "arbitrary Python with my full user privileges". With it, the same grant means "query documentation APIs and compute over the results", and nothing else.
2. **It contains indirect prompt injection.** The skill ingests untrusted text (user-generated forum posts, community notes, fetched source). If that content ever steered the generated code, sandboxed code still cannot read local files, reach non-documentation hosts, or spawn processes. The blast radius of a poisoned lookup stays inside the sandbox.
3. **It keeps the skill auditable.** Reviewers and automated scanners can verify a small, explicit boundary (one entry point, one allowlist, fixed egress) instead of reasoning about arbitrary code.

### The layers

- **Subprocess isolation** is the primary boundary. Generated code never runs in the parent process. It runs in a separate Python process with CPU-time and memory limits (`resource.setrlimit`) and a hard timeout.
- **AST validation** (defense-in-depth) rejects code before it runs: no imports, no `exec`/`eval`/`open`/`getattr`, no dunder access, no `os`/`sys`/`subprocess`.
- **Restricted builtins**: the sandbox namespace exposes only a small allowlist (`len`, `sorted`, type constructors, and similar) plus the documented API functions. All I/O goes through an IPC bridge to the parent; the sandbox itself has no file or socket access.
- **Constrained egress**: network requests go only to fixed documentation hosts (developer.apple.com, swift.org, forums.swift.org, GitHub), and GitHub fetches are restricted to the `apple` and `swiftlang` organizations with a 1 MB size cap.
- **Third-party content is labeled**: API results carrying external text include a `content_notice`, and large blobs (GitHub files, WWDC notes) are wrapped in explicit `BEGIN/END EXTERNAL CONTENT` boundary markers, so a consuming agent can distinguish quoted untrusted text (including user-generated forum posts) from the skill's own output and ignore instructions embedded in it.

Full details on the threat model, allowed builtins, IPC protocol, and content-boundary mechanics are in [`references/security.md`](apple-developer-docs/references/security.md) and [`references/sandbox.md`](apple-developer-docs/references/sandbox.md).

## Structure

```
apple-developer-docs/
├── SKILL.md              # Skill instructions
├── scripts/
│   ├── run.py            # Sandbox runner (entry point)
│   ├── sandbox.py        # Sandboxed execution environment
│   ├── security.py       # AST-based code validation
│   └── apis/             # API implementations
│       ├── _utils.py             # Shared fetch helpers + third-party content marking
│       ├── apple_docs.py
│       ├── archive.py            # Documentation Archive
│       ├── swift_evolution.py    # Proposals + Forums
│       ├── swift_repos.py
│       ├── swift_compiler.py     # Compiler internals (path + full-text search)
│       ├── wwdc_notes.py         # WWDC search + note fetch
│       ├── hig.py                # HIG search + topic fetch
│       └── xcode_releases.py     # Xcode release-notes index
└── references/
    ├── apple-docs.md      # fetch_documentation + Apple-docs URL helpers
    ├── archive.md         # Documentation Archive search
    ├── compiler.md        # Swift compiler internals (path + full-text)
    ├── hig.md             # Human Interface Guidelines
    ├── sandbox.md         # Sandbox model + allowed builtins
    ├── security.md        # AST validation + threat model
    ├── swift-evolution.md # Proposals + Forums
    ├── swift-repos.md     # Apple/SwiftLang GitHub source fetch
    ├── wwdc.md            # WWDC sessions + community notes
    └── xcode-releases.md  # Xcode release-notes index
```

## Known Limitations

- Requires Python 3.10+ (uses `match`/`case`)
- `RLIMIT_AS` memory limits may not apply on all platforms
- Swift Forums search returns top 20 topics and 20 posts per query

## License

MIT
