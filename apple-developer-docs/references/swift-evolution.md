# Swift Evolution & Forums

## search_proposals(feature: str) -> Dict

Search 500+ Swift Evolution proposals.

**Parameters:**
- `feature`: keyword, Swift version, or status (e.g. `async`, `Swift 6`, `actors`, `rejected`).

**Returns:**
```python
{
    "feature": str,
    "total_found": int,
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
data = search_proposals("async")
implemented = [p for p in data["proposals"] if p["status"] == "implemented"]
result = {"count": len(implemented), "titles": [p["title"] for p in implemented[:5]]}
```

---

## get_proposal(se_number: str) -> Dict

Fetch a single proposal.

**Parameters:**
- `se_number`: `SE-0413`, `0413`, or `413`.

**Returns:** Full proposal dict with `se_number, title, status, version, summary, authors, github_url, ...`.

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
    "total_topics": int,             # full upstream hit count
    "total_posts": int,
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
