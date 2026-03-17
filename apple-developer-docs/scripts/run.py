#!/usr/bin/env python3
"""
Apple Developer Docs Runner
============================

CLI entry point for executing Python code in a sandboxed environment with
access to Apple documentation APIs. This is the main executable that Claude
invokes via the Bash tool.

Usage:
    python run.py "code_string"
    python run.py --file script.py

The sandbox provides:
- Restricted Python environment (no imports, no file I/O)
- Access to documentation APIs via IPC
- Resource limits (CPU, memory)
- JSON output for easy parsing

Available APIs in the sandbox:
- fetch_documentation(url) - Apple Developer docs
- search_apple_online_urls(query, platform?) - Apple docs search URLs
- get_framework_info(framework) - Framework documentation URLs
- search_proposals(feature) - Swift Evolution proposals
- get_proposal(se_number) - Specific proposal details
- search_swift_repos_urls(query) - Apple/SwiftLang GitHub search URLs
- fetch_github_file(url) - Fetch file from GitHub
- search_wwdc_notes_urls(query) - WWDC session search URLs
- get_wwdc_session(session_id) - Session URLs
- search_hig_urls(query, platform?) - HIG search URLs
- list_hig_platforms() - List HIG platforms
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from sandbox import SandboxExecutor
from apis import (
    fetch_documentation, search_apple_online_urls, get_framework_info,
    search_proposals, get_proposal,
    search_swift_repos_urls, fetch_github_file,
    search_wwdc_notes_urls, get_wwdc_session,
    search_hig_urls, list_hig_platforms,
)


def create_api_handlers():
    """Create the API handler dictionary for the sandbox."""
    return {
        # Apple Documentation
        "fetch_documentation": fetch_documentation,
        "search_apple_online_urls": lambda query, platform=None: search_apple_online_urls(query, platform),
        "get_framework_info": get_framework_info,

        # Swift Evolution
        "search_proposals": search_proposals,
        "get_proposal": get_proposal,

        # Swift Repos
        "search_swift_repos_urls": search_swift_repos_urls,
        "fetch_github_file": fetch_github_file,

        # WWDC Notes
        "search_wwdc_notes_urls": search_wwdc_notes_urls,
        "get_wwdc_session": get_wwdc_session,

        # Human Interface Guidelines
        "search_hig_urls": lambda query, platform=None: search_hig_urls(query, platform),
        "list_hig_platforms": list_hig_platforms,
    }


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

    # Get code from argument or file
    if args.file:
        try:
            with open(args.file, 'r') as f:
                code = f.read()
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
