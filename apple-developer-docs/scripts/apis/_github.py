"""Shared revision validation and immutable GitHub revision resolution."""
import json
import re
import urllib.request
import urllib.error
import urllib.parse

from ._utils import open_url, read_bounded, UA_APP, require_string


def validate_ref(ref):
    err = require_string(ref, 'ref')
    if err:
        return err
    if (not ref or len(ref) > 255 or '..' in ref or '@{' in ref
            or any(c.isspace() or ord(c) < 32 or c in '~^:?*[\\' for c in ref)
            or any(part in ('', '.') for part in ref.split('/'))):
        return {'error': 'invalid_ref', 'message': 'Expected a branch, tag, or commit SHA'}
    return None


def resolve_revision(repo, ref):
    err = validate_ref(ref)
    if err:
        return err
    if not re.fullmatch(r'(apple|swiftlang)/[A-Za-z0-9_.-]+', repo):
        return {'error': 'invalid_repo', 'message': 'Expected an apple/ or swiftlang/ repository'}
    url = f'https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(ref, safe="")}'
    try:
        request = urllib.request.Request(url, headers={'User-Agent': UA_APP, 'Accept': 'application/vnd.github+json'})
        with open_url(request, timeout=15) as response:
            data = json.loads(read_bounded(response).decode('utf-8'))
    except urllib.error.HTTPError as exc:
        return {'error': 'revision_fetch_failed', 'ref': ref, 'status': exc.code,
                'message': str(exc.reason), 'retry_after': exc.headers.get('Retry-After'),
                'rate_limit_remaining': exc.headers.get('X-RateLimit-Remaining'),
                'rate_limit_reset': exc.headers.get('X-RateLimit-Reset')}
    except (ValueError, OSError) as exc:
        return {'error': 'revision_fetch_failed', 'ref': ref,
                'reason': type(exc).__name__, 'message': str(exc)}
    if not isinstance(data, dict) or not re.fullmatch(r'[0-9a-fA-F]{40}', str(data.get('sha', ''))):
        return {'error': 'revision_fetch_failed', 'ref': ref,
                'message': 'Could not resolve revision; it may be missing, inaccessible, or rate limited'}
    return {'ref': ref, 'resolved_ref': data['sha'],
            'commit_url': f'https://github.com/{repo}/commit/{data["sha"]}'}
