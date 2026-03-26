# Apple Developer Docs Skill

An agent skill that gives the Agent efficient access to Apple developer documentation through sandboxed Python code execution.

## What it does

Instead of making multiple API calls and processing large JSON responses, this skill lets the Agent write Python code that fetches and filters Apple documentation directly — significantly reducing token usage.

### Available APIs

- **Apple Documentation** — Fetch and parse docs from developer.apple.com
- **Swift Evolution** — Search 500+ proposals by keyword, version, or status
- **Swift Forums** — Search forums.swift.org for discussions, pitches, and review threads
- **Swift Repositories** — Search and fetch source code from Apple/SwiftLang GitHub repos
- **WWDC Sessions** — Search session notes and get video links
- **Human Interface Guidelines** — Search design guidance by topic and platform

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
- "Search WWDC sessions on concurrency"
- "Check the HIG for navigation patterns"
- "Fetch the Swift source for Task"

## Token efficiency

The sandbox filters API responses before they enter context. Across all tools:

| API | Typical reduction |
|-----|-------------------|
| `fetch_documentation` | 97% — SwiftUI View: 94KB → 1.7KB |
| `search_swift_forums` | 95% — 50 topics down to top 5 with key fields |
| `search_proposals` | 92% — dozens of proposals to title/status/SE number |
| `fetch_github_file` | 74–90% — full source to first 30 lines |
| `get_proposal` | 73% — full metadata to summary fields |

The Agent controls the depth — a quick lookup returns ~120 chars, a deep dive ~10KB.

## Why code execution?

This skill adapts the [code execution architecture](https://www.anthropic.com/engineering/code-execution-with-mcp) originally designed for MCP servers and applies it as a standalone skill. Instead of direct tool calls, the Agent writes Python code that runs in a sandboxed subprocess, filtering and combining API results before they enter context — no MCP server required.

This matters most for data-heavy APIs — Apple documentation pages, 500+ Swift Evolution proposals, forum threads, and GitHub source files can be large. Running queries and filtering in the sandbox means only the relevant fields come back. Combining multiple queries in a single execution also cuts down on round trips.

## Structure

```
apple-developer-docs/
├── SKILL.md              # Skill instructions
├── scripts/
│   ├── run.py            # Sandbox runner (entry point)
│   ├── sandbox.py        # Sandboxed execution environment
│   ├── security.py       # AST-based code validation
│   └── apis/             # API implementations
│       ├── apple_docs.py
│       ├── swift_evolution.py  # Proposals + Forums
│       ├── swift_repos.py
│       ├── wwdc_notes.py
│       └── hig.py
└── references/
    ├── api-reference.md  # Full API signatures and return types
    └── security.md       # Sandbox security model
```

## Known Limitations

- Requires Python 3.10+ (uses `match`/`case`)
- `RLIMIT_AS` memory limits may not apply on all platforms
- Swift Forums search returns top 20 topics and 20 posts per query

## License

MIT
