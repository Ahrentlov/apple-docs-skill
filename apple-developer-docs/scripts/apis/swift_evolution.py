"""
Swift Evolution API
====================

Standalone implementation for searching and retrieving Swift Evolution proposals
and Swift Forums discussions. Uses swift.org's official JSON feed and Discourse
search - no authentication required.
"""

import re
import urllib.request
import urllib.parse
import json
import time
from typing import Dict, Optional, List


class SwiftEvolutionAPI:
    """Interface to Swift Evolution proposals via swift.org data feed."""

    EVOLUTION_JSON_URL = "https://download.swift.org/swift-evolution/v1/evolution.json"
    GITHUB_WEB_BASE = "https://github.com/swiftlang/swift-evolution"
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/swiftlang/swift-evolution/main/proposals"

    def __init__(self):
        self.cache = None
        self.cache_time = 0
        self.cache_ttl = 3600

    def _fetch_data(self) -> Optional[Dict]:
        """Fetch and cache evolution.json from swift.org."""
        if self.cache and (time.time() - self.cache_time) < self.cache_ttl:
            return self.cache

        try:
            req = urllib.request.Request(
                self.EVOLUTION_JSON_URL,
                headers={'User-Agent': 'AppleDeveloperDocs/1.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.cache = data
                self.cache_time = time.time()
                return data
        except Exception:
            return None


_api = SwiftEvolutionAPI()


def search_proposals(feature: str) -> Dict:
    """
    Search Swift Evolution proposals by feature name, version, or status.

    Args:
        feature: Feature name, Swift version, or status to search
                 Examples: 'async', 'Swift 6', 'actors', 'rejected'

    Returns:
        Dictionary with matching proposals sorted by relevance
    """
    data = _api._fetch_data()

    if not data:
        return {
            'error': 'Failed to fetch Swift Evolution data',
            'feature': feature,
            'suggestion': 'Check your internet connection'
        }

    proposals = data.get('proposals', [])
    feature_lower = feature.lower()
    results = []

    # Check for version search
    version_match = re.search(r'swift\s*(\d+\.?\d*)', feature_lower)
    search_version = version_match.group(1) if version_match else None

    for proposal in proposals:
        score = 0
        status = proposal.get('status', {})
        impl_version = status.get('version', '')

        # Version scoring
        if search_version:
            if impl_version == search_version:
                score += 100
            elif impl_version and impl_version.startswith(search_version):
                score += 50

        # Text scoring
        title = proposal.get('title', '').lower()
        summary = proposal.get('summary', '').lower()
        status_state = status.get('state', '').lower()

        if feature_lower in title:
            score += 10
        if feature_lower in summary:
            score += 5
        if feature_lower in status_state:
            score += 15

        if score > 0:
            results.append({
                'se_number': proposal.get('id', ''),
                'title': proposal.get('title', ''),
                'status': status.get('state', 'unknown'),
                'version': impl_version or 'N/A',
                'summary': proposal.get('summary', '')[:200] + '...' if len(proposal.get('summary', '')) > 200 else proposal.get('summary', ''),
                'github_url': f"{_api.GITHUB_WEB_BASE}/blob/main/proposals/{proposal.get('link', '')}",
                'relevance_score': score
            })

    results.sort(key=lambda x: x['relevance_score'], reverse=True)

    response = {
        'feature': feature,
        'total_found': len(results),
        'proposals': results[:20],
        'available_versions': data.get('implementationVersions', [])
    }

    # Add deep search suggestion for sparse results
    if len(results) < 3:
        encoded_query = urllib.parse.quote(feature)
        response['deep_search'] = {
            'reason': f"Only {len(results)} result(s) found in proposal titles/summaries.",
            'suggestion': "The term may appear in proposal body text. Try GitHub deep search:",
            'github_url': f"https://github.com/search?q={encoded_query}+repo:swiftlang/swift-evolution+path:proposals&type=code"
        }

    return response


def get_proposal(se_number: str) -> Dict:
    """
    Get detailed information about a specific Swift Evolution proposal.

    Args:
        se_number: The proposal number (e.g., 'SE-0413', '0413', '413')

    Returns:
        Dictionary with proposal details
    """
    data = _api._fetch_data()

    if not data:
        return {
            'error': 'Failed to fetch Swift Evolution data',
            'se_number': se_number,
            'suggestion': 'Check your internet connection'
        }

    # Normalize SE number
    se_num = se_number.upper()
    if not se_num.startswith('SE-'):
        se_num = f'SE-{se_num.zfill(4)}'

    proposals = data.get('proposals', [])
    proposal = next((p for p in proposals if p.get('id', '').upper() == se_num), None)

    if not proposal:
        return {
            'error': f'Proposal {se_num} not found',
            'se_number': se_num,
            'suggestion': f'Visit https://www.swift.org/swift-evolution/ to browse proposals'
        }

    status = proposal.get('status', {})
    authors = proposal.get('authors', [])

    return {
        'se_number': proposal.get('id', ''),
        'title': proposal.get('title', ''),
        'status': status.get('state', 'unknown'),
        'version': status.get('version', 'N/A'),
        'summary': proposal.get('summary', ''),
        'authors': [a.get('name', 'Unknown') for a in authors],
        'github_url': f"{_api.GITHUB_WEB_BASE}/blob/main/proposals/{proposal.get('link', '')}",
        'raw_url': f"{_api.GITHUB_RAW_BASE}/{proposal.get('link', '')}",
        'swift_org_url': f'https://www.swift.org/swift-evolution/#?id={proposal.get("id", "")}',
        'forum_url': f'https://forums.swift.org/search?q={urllib.parse.quote(proposal.get("title", ""))}'
    }


def search_swift_forums_urls(query: str, category: Optional[str] = None) -> Dict:
    """
    Generate search URLs for the Swift Forums (forums.swift.org).

    Args:
        query: Search term (e.g., 'async let', 'ownership', 'SE-0413')
        category: Optional category filter (evolution, development, using-swift, related-projects)

    Returns:
        Dictionary with search URLs for different forum sections
    """
    encoded_query = urllib.parse.quote(query)

    result = {
        'query': query,
        'category': category,
        'search_urls': {
            'all': f"https://forums.swift.org/search?q={encoded_query}",
            'evolution': f"https://forums.swift.org/search?q={encoded_query}%20%23evolution",
            'development': f"https://forums.swift.org/search?q={encoded_query}%20%23development",
            'using_swift': f"https://forums.swift.org/search?q={encoded_query}%20%23using-swift",
        },
    }

    if category:
        category_lower = category.lower().replace(' ', '-')
        result['filtered_url'] = f"https://forums.swift.org/search?q={encoded_query}%20%23{urllib.parse.quote(category_lower)}"

    return result


def search_swift_forums(query: str, category: Optional[str] = None) -> Dict:
    """
    Search Swift Forums and return structured results.

    Args:
        query: Search term (e.g., 'async let', 'ownership', 'SE-0413')
        category: Optional category filter (evolution, development, using-swift, related-projects)

    Returns:
        Dictionary with topics, posts, and metadata
    """
    search_query = urllib.parse.quote(query)
    if category:
        search_query += urllib.parse.quote(f" #{category.lower().replace(' ', '-')}")

    api_url = f"https://forums.swift.org/search.json?q={search_query}"

    try:
        req = urllib.request.Request(
            api_url,
            headers={
                'User-Agent': 'AppleDeveloperDocs/1.0',
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e), 'query': query}

    topics_raw = data.get('topics', [])
    posts_raw = data.get('posts', [])

    topic_map = {t['id']: t for t in topics_raw}

    topics = [{
        'title': t.get('title', ''),
        'url': f"https://forums.swift.org/t/{t.get('slug', '')}/{t.get('id', '')}",
        'posts_count': t.get('posts_count', 0),
        'reply_count': t.get('reply_count', 0),
        'created_at': t.get('created_at', '')[:10],
        'last_posted_at': t.get('last_posted_at', '')[:10],
        'tags': t.get('tags', []),
    } for t in topics_raw[:20]]

    posts = []
    for p in posts_raw[:20]:
        topic = topic_map.get(p.get('topic_id'))
        post = {
            'blurb': p.get('blurb', ''),
            'username': p.get('username', ''),
            'like_count': p.get('like_count', 0),
            'created_at': p.get('created_at', '')[:10],
        }
        if topic:
            post['topic_title'] = topic.get('title', '')
            post['topic_url'] = f"https://forums.swift.org/t/{topic.get('slug', '')}/{topic['id']}"
        posts.append(post)

    return {
        'query': query,
        'category': category,
        'total_topics': len(topics_raw),
        'total_posts': len(posts_raw),
        'topics': topics,
        'posts': posts,
    }
