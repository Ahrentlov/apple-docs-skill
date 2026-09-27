"""
Apple Tutorials
===============

List the tutorials in an Apple course (Develop in Swift, SwiftUI, App Dev
Training, ...) from the course overview's JSON. Step-by-step tutorial pages
(kind 'project') are then read with `fetch_documentation`, which serves them
as Markdown.
"""

import json
import re
from typing import Dict

from ._utils import fetch_page, mark_untrusted


TUTORIALS_DATA = "https://developer.apple.com/tutorials/data/tutorials"


def list_tutorials(course: str) -> Dict:
    """
    List a course's tutorials in order.

    Args:
        course: Course slug from its URL, e.g. 'develop-in-swift', 'swiftui',
                'app-dev-training', 'swiftui-concepts', 'sample-apps'.

    Returns:
        {course, title, url, total, tutorials: [{volume, chapter, title, kind,
         url, abstract, markdown}]}. `markdown` is True for step-by-step
         tutorials (kind 'project'), which `fetch_documentation` can read;
         articles and overviews have no Markdown rendering.
    """
    if not isinstance(course, str) or not re.fullmatch(r'[a-z0-9-]+', course.strip().lower()):
        return {"error": "invalid_input", "message": "course must be a slug such as 'develop-in-swift'"}
    course = course.strip().lower()
    url = f"https://developer.apple.com/tutorials/{course}"
    page, err = fetch_page(f"{TUTORIALS_DATA}/{course}.json", url, 'application/json')
    if err: return err
    try:
        data = json.loads(page.body)
    except ValueError as exc:
        return {"error": "invalid_json", "message": str(exc), "url": url}
    if not isinstance(data, dict) or data.get('metadata', {}).get('role') != 'overview':
        return {"error": "invalid_schema", "message": "Expected a tutorial course overview", "url": url}

    references = data.get('references', {})
    tutorials = []
    for volume in data.get('sections', []):
        if volume.get('kind') != 'volume':
            continue
        for chapter in volume.get('chapters', []):
            for identifier in chapter.get('tutorials', []):
                ref = references.get(identifier, {})
                if not ref.get('url'):
                    continue
                tutorials.append({
                    "volume": volume.get('name'), "chapter": chapter.get('name'),
                    "title": ref.get('title', ''), "kind": ref.get('kind', ''),
                    "url": f"https://developer.apple.com{ref['url']}",
                    "abstract": "".join(i.get('text', '') for i in ref.get('abstract', []) if isinstance(i, dict)).strip(),
                    "markdown": ref.get('kind') == 'project',
                })
    return mark_untrusted({
        "course": course, "title": data['metadata'].get('title', ''), "url": url,
        "total": len(tutorials), "tutorials": tutorials,
    }, "developer.apple.com tutorials")
