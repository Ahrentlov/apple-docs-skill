#!/usr/bin/env python3
"""
Apple Developer Docs Runner
============================

CLI entry point for executing Python code in a sandboxed environment with
access to Apple documentation APIs. This is the main executable that an agent
invokes through its shell tool.

Usage:
    python run.py "code_string"
    python run.py --file script.py

The sandbox provides:
- Restricted Python environment (no imports, no file I/O)
- Access to documentation APIs via IPC
- Resource limits (CPU, memory)
- JSON output for easy parsing

Available APIs in the sandbox (see SKILL.md / references/ for full signatures):

Apple Documentation
- fetch_documentation(url, section?, start_line?, end_line?, max_lines?) - Parse any /documentation/ or /design/human-interface-guidelines/ page
- search_apple_online_urls(query, ...)  - Apple docs search URLs
- get_framework_info(framework)         - Framework documentation URL

Swift Evolution & Forums
- search_proposals(feature) / get_proposal(se_number)
- search_swift_forums(query, ...) / search_swift_forums_urls(query, ...)

Swift Repositories
- search_swift_repos_urls(query) / fetch_github_file(url, start_line?, end_line?, section?, ref?, max_lines?)
- compare_github_file(url, base_ref, head_ref, context_lines?, max_diff_lines?)
- search_symbols(framework, query, limit?, max_pages?)

WWDC Sessions
- search_wwdc_sessions(query, year?, limit?)  - Search ~3000 sessions
- fetch_wwdc_session(session_id)              - Fetch the actual community-written notes

Human Interface Guidelines
- search_hig(query, platform?, limit?) / fetch_hig(topic)

Documentation Archive
- search_archive(query, platform?, framework?, resource_type?, topic?, limit?)
- list_archive_frameworks / list_archive_topics / list_archive_resource_types

Swift Compiler Internals
- search_compiler_docs(query, limit?, ref?)            - File-path search
- search_compiler_docs_text(query, limit?, ...)  - Full-text grep
- list_compiler_phases / get_compiler_phase

Xcode Release Notes
- list_xcode_release_notes(major?) / get_xcode_release_notes_url(version)
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import apis
from sandbox import SandboxExecutor


def create_api_handlers():
    """Map every public name in `apis.__all__` to its callable."""
    return {name: getattr(apis, name) for name in apis.__all__}


def main():
    parser = argparse.ArgumentParser(
        description='Execute Python code in Apple Documentation sandbox',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Execute inline code
  python run.py "result = search_proposals('async')"

  # Execute from file
  python run.py --file my_script.py

  # With longer timeout
  python run.py --timeout 30 "result = fetch_documentation('https://developer.apple.com/documentation/swiftui/view')"
'''
    )
    parser.add_argument('code', nargs='?', help='Python code to execute')
    parser.add_argument('--file', '-f', help='Read code from file instead')
    parser.add_argument('--timeout', '-t', type=int, default=10, help='Execution timeout in seconds (default: 10)')
    parser.add_argument('--pretty', '-p', action='store_true', help='Pretty-print JSON output')

    args = parser.parse_args()
    if not 1 <= args.timeout <= 300:
        parser.error('--timeout must be between 1 and 300 seconds')
    if args.file and args.code:
        parser.error('pass either inline code or --file, not both')

    # Get code from argument or file
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                code = f.read(10001)
        except FileNotFoundError:
            print(json.dumps({"success": False, "error": f"File not found: {args.file}"}))
            sys.exit(1)
        except Exception as e:
            print(json.dumps({"success": False, "error": f"Failed to read file: {e}"}))
            sys.exit(1)
    elif args.code:
        code = args.code
    else:
        parser.print_help()
        sys.exit(1)

    # Create sandbox executor with API handlers
    executor = SandboxExecutor(
        timeout=args.timeout,
        max_memory_mb=50,
        api_handlers=create_api_handlers()
    )

    # Execute the code
    result = executor.execute(code)

    # Output result as JSON
    output = result.to_dict()
    if args.pretty:
        print(json.dumps(output, indent=2, default=str))
    else:
        print(json.dumps(output, default=str))

    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == '__main__':
    main()
