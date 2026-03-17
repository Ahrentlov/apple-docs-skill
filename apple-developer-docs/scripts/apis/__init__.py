"""
Apple Documentation APIs
========================

Standalone implementations for use in the sandbox.
These make direct HTTP calls - no external dependencies.
"""

from .apple_docs import fetch_documentation, search_apple_online_urls, get_framework_info
from .swift_evolution import search_proposals, get_proposal
from .swift_repos import search_swift_repos_urls, fetch_github_file
from .wwdc_notes import search_wwdc_notes_urls, get_wwdc_session
from .hig import search_hig_urls, list_hig_platforms

__all__ = [
    'fetch_documentation',
    'search_apple_online_urls',
    'get_framework_info',
    'search_proposals',
    'get_proposal',
    'search_swift_repos_urls',
    'fetch_github_file',
    'search_wwdc_notes_urls',
    'get_wwdc_session',
    'search_hig_urls',
    'list_hig_platforms',
]
