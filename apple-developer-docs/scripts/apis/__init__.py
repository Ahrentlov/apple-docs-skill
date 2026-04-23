"""
Apple Documentation APIs
========================

Standalone implementations for use in the sandbox.
These make direct HTTP calls - no external dependencies.
"""

from .apple_docs import fetch_documentation, search_apple_online_urls, get_framework_info
from .swift_evolution import search_proposals, get_proposal, search_swift_forums_urls, search_swift_forums
from .swift_repos import search_swift_repos_urls, fetch_github_file
from .wwdc_notes import search_wwdc_notes_urls, get_wwdc_session
from .hig import search_hig_urls, list_hig_platforms
from .archive import (
    search_archive, list_archive_frameworks, list_archive_topics,
    list_archive_resource_types,
)
from .swift_compiler import (
    search_compiler_docs, list_compiler_phases, get_compiler_phase,
)

__all__ = [
    'fetch_documentation',
    'search_apple_online_urls',
    'get_framework_info',
    'search_proposals',
    'get_proposal',
    'search_swift_forums_urls',
    'search_swift_forums',
    'search_swift_repos_urls',
    'fetch_github_file',
    'search_wwdc_notes_urls',
    'get_wwdc_session',
    'search_hig_urls',
    'list_hig_platforms',
    'search_archive',
    'list_archive_frameworks',
    'list_archive_topics',
    'list_archive_resource_types',
    'search_compiler_docs',
    'list_compiler_phases',
    'get_compiler_phase',
]
