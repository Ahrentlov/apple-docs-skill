# Swift Evolution & Forums

## search_proposals(feature: str, version=None, status=None, limit=20, offset=0) -> Dict

Search Swift Evolution proposal metadata. The whole query is matched as a
case-insensitive substring against the complete title, summary, or status state,
not separate words or proposal bodies. A query containing `Swift N` additionally
matches implementation version N or N.x. Empty query lists all metadata. Returned
summary excerpts may be shorter than the text searched. Preserve `search_scope`
and `matching` when filtering output and explain that scope in exhaustive answers.
Read the relevant detailed-design, isolation/execution rules, and compatibility
passages for each matching proposal before classifying its semantics. First
paragraphs or the first few keyword hits often contain only motivation or a
table of contents. Return and read the actual supporting sections, including
qualifications and feature flags. Explain whether a proposal changes general
rules, introduces new APIs with isolation behavior, or preserves existing rules;
continue retrieving evidence for any unresolved item while its source is available.
A caveat about shallow reading does not complete a requested classification. If
retrieval fails or the source is inconclusive, explicitly mark that item unresolved
and explain the actual blocker. Record
the excerpt ranges actually returned, not just that complete bodies were fetched.
For a classification, state the supported behavioral conclusion first. Only add
parameter defaults, attribute spellings, or other mechanisms after reading their
declarations or detailed explanations; do not expand a supported introduction
with syntax recalled from memory.
Implementation versions are metadata labels, not evidence of current release
availability; omit shipping-status claims unless independently verified.

**Parameters:**
- `feature`: keyword, Swift version, or status (e.g. `async`, `Swift 6`, `actors`, `rejected`). Empty string lists all metadata.
- `version`: exact version or major family (`6` includes `6.1`); applied before pagination.
- `status`: exact status, case-insensitive; applied before pagination.
- `limit`: page size, default 20, capped at 200.
- `offset`: nonnegative page offset. Follow `next_offset` until null for all matches.

**Returns:**
```python
{
    "feature": str,
    "total_found": int,             # matching metadata before pagination
    "returned": int,
    "offset": int,
    "next_offset": int | None,
    "truncated": bool,
    "filters": {"version": str | None, "status": str | None},
    "search_scope": str,
    "matching": dict,                 # fields, rule, implementation_version_query, empty_query_matches_all
    "proposals": [
        {
            "se_number": str,         # "SE-0413"
            "title": str,
            "status": str,            # "implemented", "accepted", "review", ...
            "version": str,           # Swift version
            "summary": str,
            "github_url": str,
            "relevance_score": int
        }
    ],
    "available_versions": list[str],
    "deep_search": {                  # only when fewer than 3 results
        "reason": str,
        "suggestion": str,
        "github_url": str
    }
}
```

**Errors:** `fetch_failed`.

**Example:**
```python
data = search_proposals("async", version="6", status="implemented", limit=5)
if 'error' in data:
    result = data
else:
    result = {"total_matching_metadata": data['total_found'], "sample": data['proposals'],
              "next_offset": data['next_offset'], "truncated": data['truncated']}
```

---

## get_proposal(se_number: str) -> Dict

Fetch metadata for a single proposal. This does not fetch its full text. Use
`fetch_github_file(metadata["github_url"])` to read the proposal body after checking
for an error. `forum_url` is a generated search link, not a fetched discussion.

**Parameters:**
- `se_number`: `SE-0413`, `0413`, or `413`.

**Returns:** Proposal metadata with `se_number, title, status, version, summary, authors, github_url, ...`.

**Errors:** `fetch_failed`, `proposal_not_found`.

---

## search_swift_forums_urls(query: str, category: str = None) -> Dict

Search URLs for Swift Forums (forums.swift.org). Returns URLs only.

**Returns:** `{query, category, search_urls: {...}}`.

---

## search_swift_forums(query: str, category: str = None, limit: int = 20) -> Dict

Search Swift Forums and return actual topics + posts (not just URLs).

**Parameters:**
- `query`: Search term.
- `category`: Optional category filter (`evolution`, `development`, `using-swift`, `related-projects`).
- `limit`: Max topics + max posts returned (default 20, capped at 200).

**Returns:**
```python
{
    "query": str,
    "category": str | None,
    "total_topics": int,             # count in this upstream response page, not a global total
    "total_posts": int,
    "more_available": bool,           # upstream indicates more results
    "truncated": bool,                # local limit omitted topics/posts
    "search_scope": str,
    "returned_topics": int,          # post-limit slice size
    "returned_posts": int,
    "topics": [
        {"title": str, "url": str, "posts_count": int, "reply_count": int,
         "created_at": str, "last_posted_at": str, "tags": list}
    ],
    "posts": [
        {"blurb": str, "username": str, "like_count": int, "created_at": str,
         "topic_id": int, "topic_title": str, "topic_url": str, "post_url": str}
    ]
}
```

**Errors:** `fetch_failed`.

All proposal metadata and forum text results carry `content_notice`. Search summaries
and forum blurbs are excerpts, not full documents. A zero-result metadata search
does not establish that a term is absent from proposal bodies.
