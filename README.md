# Apple Developer Docs Skill

An agent skill that gives Claude efficient access to Apple developer documentation through sandboxed Python code execution.

## What it does

Instead of making multiple API calls and processing large JSON responses, this skill lets Claude write Python code that fetches and filters Apple documentation directly — significantly reducing token usage.

### Available APIs

- **Apple Documentation** — Fetch and parse docs from developer.apple.com
- **Swift Evolution** — Search 500+ proposals by keyword, version, or status
- **Swift Repositories** — Search and fetch source code from Apple/SwiftLang GitHub repos
- **WWDC Sessions** — Search session notes and get video links
- **Human Interface Guidelines** — Search design guidance by topic and platform

## Installation

### Claude Code

Clone this repository and place the `apple-developer-docs/` folder in your skills directory.

### Claude.ai

1. Download or clone this repository
2. Zip the `apple-developer-docs/` folder
3. Go to **Settings > Capabilities > Skills**
4. Click **Upload skill** and select the zip

## Usage

The skill activates automatically when you ask about Apple APIs, Swift Evolution proposals, WWDC sessions, or Human Interface Guidelines.

**Example prompts:**
- "Look up the SwiftUI View protocol"
- "Find Swift Evolution proposals about async"
- "Search WWDC sessions on concurrency"
- "Check the HIG for navigation patterns"
- "Fetch the Swift source for Task"

## Why code execution?

This skill adapts the [code execution architecture](https://www.anthropic.com/engineering/code-execution-with-mcp) originally designed for MCP servers and applies it as a standalone skill. Instead of direct tool calls, Claude writes Python code that runs in a sandboxed subprocess, filtering and combining API results before they enter context — no MCP server required.

This matters most for the data-heavy APIs — Apple documentation pages, 500+ Swift Evolution proposals, and GitHub source files can be large. Running queries and filtering in the sandbox means only the relevant fields come back, rather than entire payloads flowing through context. Combining multiple queries in a single execution also cuts down on round trips.

## Structure

```
apple-developer-docs/
├── SKILL.md              # Skill instructions
├── scripts/
│   ├── run.py            # Sandbox runner (entry point)
│   ├── sandbox.py        # Sandboxed execution environment
│   ├── security.py       # Code validation
│   └── apis/             # API implementations
│       ├── apple_docs.py
│       ├── swift_evolution.py
│       ├── swift_repos.py
│       ├── wwdc_notes.py
│       └── hig.py
└── references/
    ├── api-reference.md  # Full API signatures and return types
    └── security.md       # Sandbox security model
```

## License

MIT
