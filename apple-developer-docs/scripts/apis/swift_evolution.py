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
from typing import Dict, Optional, List

from ._utils import open_url, read_bounded, UA_APP, clamp_limit, fetch_json, mark_untrusted, require_string


class SwiftEvolutionAPI:
    """Interface to Swift Evolution proposals via swift.org data feed."""

    EVOLUTION_JSON_URL = "https://download.swift.org/swift-evolution/v1/evolution.json"
    GITHUB_WEB_BASE = "https://github.com/swiftlang/swift-evolution"
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/swiftlang/swift-evolution/main/proposals"

    def __init__(self):
        self._cache: Optional[Dict] = None

    def _fetch_data(self) -> Optional[Dict]:
        # Memoize for the process lifetime (run.py is one process per script),
        # so a script looking up several proposals downloads the ~1-2MB feed
        # once instead of per call. A failed fetch leaves the cache empty to retry.
        if self._cache is None:
            self._cache = fetch_json(self.EVOLUTION_JSON_URL)
        return self._cache


_api = SwiftEvolutionAPI()


def search_proposals(feature: str, version: Optional[str] = None, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> Dict:
    """
    Search Swift Evolution proposals by feature name, version, or status.

    Args:
        feature: Feature name, Swift version, or status to search
                 Examples: 'async', 'Swift 6', 'actors', 'rejected'

    Returns:
        Dictionary with matching proposals sorted by relevance
    """
    err = require_string(feature, 'feature')
    if err: return err
    for field, value in (("version", version), ("status", status)):
        if value is not None:
            err = require_string(value, field)
            if err: return err
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return {"error": "invalid_input", "message": "offset must be a nonnegative integer"}
    limit = clamp_limit(limit)
    data = _api._fetch_data()

    if not data:
        return {
            'error': 'fetch_failed',
            'message': 'Could not fetch Swift Evolution data — check connectivity to download.swift.org',
            'feature': feature,
        }

    proposals = data.get('proposals', [])
    feature_lower = feature.lower()
    results = []

    # Check for version search
    version_match = re.search(r'swift\s*(\d+\.?\d*)', feature_lower)
    search_version = version_match.group(1) if version_match else None

    for proposal in proposals:
        score = 0
        proposal_status = proposal.get('status', {})
        impl_version = proposal_status.get('version', '')
        if version is not None and not (impl_version == version or impl_version.startswith(version + '.')):
            continue
        if status is not None and proposal_status.get('state', '').lower() != status.lower():
            continue

        # Version scoring
        if search_version:
            if impl_version == search_version:
                score += 100
            elif impl_version and impl_version.startswith(search_version + "."):
                score += 50

        # Text scoring
        title = proposal.get('title', '').lower()
        summary = proposal.get('summary', '').lower()
        status_state = proposal_status.get('state', '').lower()

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
                'status': proposal_status.get('state', 'unknown'),
                'version': impl_version or 'N/A',
                'summary': proposal.get('summary', '')[:200] + '...' if len(proposal.get('summary', '')) > 200 else proposal.get('summary', ''),
                'github_url': f"{_api.GITHUB_WEB_BASE}/blob/main/proposals/{proposal.get('link', '')}",
                'relevance_score': score
            })

    results.sort(key=lambda x: x['relevance_score'], reverse=True)

    response = {
        'feature': feature,
        'total_found': len(results),
        'proposals': results[offset:offset + limit],
        'returned': len(results[offset:offset + limit]),
        'offset': offset,
        'truncated': offset > 0 or offset + limit < len(results),
        'next_offset': offset + limit if limit > 0 and offset + limit < len(results) else None,
        'filters': {'version': version, 'status': status},
        'search_scope': 'case-insensitive substring of the complete title, summary, or status state; '
                        'queries containing Swift N also match implementation version N or N.x; '
                        'empty query matches all metadata; no proposal-body search',
        'matching': {'fields': ['title', 'summary', 'status.state'],
                     'rule': 'case-insensitive substring (whole query, not separate words)',
                     'implementation_version_query': search_version,
                     'empty_query_matches_all': feature == ''},
        'available_versions': data.get('implementationVersions', [])
    }

    # Add deep search suggestion for sparse results
    if len(results) < 3:
        encoded_query = urllib.parse.quote(feature)
        response['deep_search'] = {
            'reason': f"Only {len(results)} result(s) found in proposal metadata.",
            'suggestion': "The term may appear in proposal body text. Try GitHub deep search:",
            'github_url': f"https://github.com/search?q={encoded_query}+repo:swiftlang/swift-evolution+path:proposals&type=code"
        }

    return mark_untrusted(response, "swift.org Swift Evolution metadata")


def get_proposal(se_number: str) -> Dict:
    """
    Get detailed information about a specific Swift Evolution proposal.

    Args:
        se_number: The proposal number (e.g., 'SE-0413', '0413', '413')

    Returns:
        Dictionary with proposal details
    """
    err = require_string(se_number, 'se_number')
    if err: return err

    raw = se_number.strip()
    if not raw:
        return {
            'error': 'empty_input',
            'message': "Pass a proposal id like 'SE-0413' or '413'",
        }

    digits = raw.upper().removeprefix('SE-')
    if not digits.isdigit():
        return {
            'error': 'invalid_input',
            'message': f"Proposal id must be digits or SE-DDDD; got {se_number!r}",
        }

    data = _api._fetch_data()
    if not data:
        return {
            'error': 'fetch_failed',
            'message': 'Could not fetch Swift Evolution data — check connectivity to download.swift.org',
            'se_number': se_number,
        }

    se_num = f'SE-{digits.zfill(4)}'

    proposals = data.get('proposals', [])
    proposal = next((p for p in proposals if p.get('id', '').upper() == se_num), None)

    if not proposal:
        return {
            'error': 'proposal_not_found',
            'message': f'Proposal {se_num} not found — browse all at https://www.swift.org/swift-evolution/',
            'se_number': se_num,
        }

    status = proposal.get('status', {})
    authors = proposal.get('authors', [])

    return mark_untrusted({
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
    }, "swift.org Swift Evolution metadata")


def search_swift_forums_urls(query: str, category: Optional[str] = None) -> Dict:
    """
    Generate search URLs for the Swift Forums (forums.swift.org).

    Args:
        query: Search term (e.g., 'async let', 'ownership', 'SE-0413')
        category: Optional category filter (evolution, development, using-swift, related-projects)

    Returns:
        Dictionary with search URLs for different forum sections
    """
    err = require_string(query, 'query')
    if err: return err
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
        category_lower = str(category).lower().replace(' ', '-')
        result['filtered_url'] = f"https://forums.swift.org/search?q={encoded_query}%20%23{urllib.parse.quote(category_lower)}"

    return result


def search_swift_forums(query: str, category: Optional[str] = None, limit: int = 20) -> Dict:
    """
    Search Swift Forums and return structured results.

    Args:
        query: Search term (e.g., 'async let', 'ownership', 'SE-0413')
        category: Optional category filter (evolution, development, using-swift, related-projects)
        limit: Max topics + max posts returned (default 20, capped at 200)

    Returns:
        Dictionary with topics, posts, and metadata
    """
    err = require_string(query, 'query')
    if err: return err
    limit = clamp_limit(limit)
    search_query = urllib.parse.quote(query)
    if category:
        search_query += urllib.parse.quote(f" #{str(category).lower().replace(' ', '-')}")

    api_url = f"https://forums.swift.org/search.json?q={search_query}"

    try:
        req = urllib.request.Request(
            api_url,
            headers={
                'User-Agent': UA_APP,
                'Accept': 'application/json'
            }
        )
        with open_url(req, timeout=15) as response:
            data = json.loads(read_bounded(response).decode('utf-8'))
    except Exception as e:
        return {'error': 'fetch_failed', 'message': str(e), 'query': query}

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
    } for t in topics_raw[:limit]]

    posts = []
    for p in posts_raw[:limit]:
        topic = topic_map.get(p.get('topic_id'))
        post_number = p.get('post_number', 1)
        post = {
            'blurb': p.get('blurb', ''),
            'username': p.get('username', ''),
            'like_count': p.get('like_count', 0),
            'created_at': p.get('created_at', '')[:10],
            'topic_id': p.get('topic_id'),
            'post_url': f"https://forums.swift.org/t/{p.get('topic_id')}/{post_number}",
        }
        if topic:
            slug = topic.get('slug', '')
            tid = topic['id']
            post['topic_title'] = topic.get('title', '')
            post['topic_url'] = f"https://forums.swift.org/t/{slug}/{tid}"
            post['post_url'] = f"https://forums.swift.org/t/{slug}/{tid}/{post_number}"
        posts.append(post)

    # Forum posts are arbitrary user-generated text, the highest-risk source
    # this skill returns. Blurbs, titles, tags, and usernames are all untrusted.
    return mark_untrusted({
        'query': query,
        'category': category,
        'search_scope': 'one upstream search page; counts are not global totals',
        'more_available': bool(data.get('grouped_search_result', {}).get('more_full_page_results') or data.get('grouped_search_result', {}).get('more_posts')),
        'truncated': len(topics_raw) > limit or len(posts_raw) > limit,
        'total_topics': len(topics_raw),
        'total_posts': len(posts_raw),
        'returned_topics': len(topics),
        'returned_posts': len(posts),
        'topics': topics,
        'posts': posts,
    }, "forums.swift.org (user-generated posts)")
