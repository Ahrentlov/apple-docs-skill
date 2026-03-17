"""
Human Interface Guidelines API
==============================

Standalone implementation for searching Apple's Human Interface Guidelines.
Provides search URLs for design patterns and platform-specific guidance.
"""

import urllib.parse
from typing import Dict, Optional, List


PLATFORMS = ["ios", "macos", "tvos", "watchos", "visionos"]
BASE_URL = "https://developer.apple.com/design/human-interface-guidelines"


def search_hig_urls(query: str, platform: Optional[str] = None) -> Dict:
    """
    Search Human Interface Guidelines by topic or keyword.

    Args:
        query: Search term (e.g., "navigation", "buttons", "dark mode")
        platform: Optional platform filter (ios, macos, tvos, watchos, visionos)

    Returns:
        Dictionary with search URLs and platform links
    """
    encoded_query = urllib.parse.quote(query)

    results = {
        "query": query,
        "platform": platform,
        "base_url": BASE_URL,
        "search_url": f"https://www.google.com/search?q=site:developer.apple.com/design/human-interface-guidelines+{encoded_query}",
        "direct_link": BASE_URL
    }

    # Add platform-specific search if specified
    if platform and platform.lower() in PLATFORMS:
        platform_lower = platform.lower()
        results["platform_url"] = f"{BASE_URL}/platforms/{platform_lower}"
        results["platform_search"] = (
            f"https://www.google.com/search?q=site:developer.apple.com/design/human-interface-guidelines+{platform_lower}+{encoded_query}"
        )

    return results


PLATFORM_NAMES = {
    "ios": "iOS",
    "macos": "macOS",
    "tvos": "tvOS",
    "watchos": "watchOS",
    "visionos": "visionOS",
}


def list_hig_platforms() -> List[Dict]:
    """
    List all supported Apple platforms with Human Interface Guidelines links.

    Returns:
        List of platforms with their URLs
    """
    return [
        {
            "platform": platform,
            "name": PLATFORM_NAMES.get(platform, platform),
            "url": f"{BASE_URL}/platforms/{platform}"
        }
        for platform in PLATFORMS
    ]
