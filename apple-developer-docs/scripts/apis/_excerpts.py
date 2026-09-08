"""Bounded, source-line-aware selections for Markdown and reStructuredText."""
import re


def validate_selection(start_line, end_line, section, max_lines):
    if type(max_lines) is not int or not 1 <= max_lines <= 1000:
        return {'error': 'invalid_selection', 'message': 'max_lines must be an integer from 1 to 1000'}
    for name, value in (('start_line', start_line), ('end_line', end_line)):
        if value is not None and (type(value) is not int or value < 1):
            return {'error': 'invalid_selection', 'message': f'{name} must be a positive integer'}
    if end_line is not None and end_line < (start_line or 1):
        return {'error': 'invalid_selection', 'message': 'end_line precedes start_line'}
    if section is not None and (not isinstance(section, str) or not section.strip()
                                or start_line is not None or end_line is not None):
        return {'error': 'invalid_selection', 'message': 'Use a nonempty section name OR line bounds'}
    return None


def heading_ranges(lines, rst=False):
    """Recognize Markdown ATX/setext or RST underlines, ignoring fenced code."""
    headings, stack, styles = [], [], []
    fence = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        match = re.match(r'^ {0,3}(`{3,}|~{3,})', line) if not rst else None
        if match:
            token = match[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not stripped[len(token):].strip():
                fence = None
            continue
        if fence:
            continue
        title, level, start = None, None, i + 1
        atx = re.match(r'^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line) if not rst else None
        if atx:
            title, level = atx[2], len(atx[1])
        elif (i > 0 and lines[i-1].strip() and not lines[i-1].startswith((' ', '\t'))
              and len(stripped) >= 3 and len(set(stripped)) == 1
              and stripped[0] in ('=-~^"\'`:+*#' if rst else '=-')):
            title, start = lines[i-1].strip(), i
            if rst:
                if stripped[0] not in styles:
                    styles.append(stripped[0])
                level = styles.index(stripped[0]) + 1
            else:
                level = 1 if stripped[0] == '=' else 2
        if title is None:
            continue
        while stack and stack[-1]['level'] >= level:
            stack.pop()
        path = [h['title'] for h in stack] + [title]
        entry = {'title': title, 'level': level, 'path': path, 'start_line': start}
        headings.append(entry)
        stack.append(entry)
    following = []
    for heading in reversed(headings):
        while following and following[-1]['level'] > heading['level']:
            following.pop()
        heading['end_line'] = following[-1]['start_line'] - 1 if following else len(lines)
        following.append(heading)
    return headings


def select_text(text, start_line=None, end_line=None, section=None, max_lines=200, rst=False):
    err = validate_selection(start_line, end_line, section, max_lines)
    if err:
        return err
    lines = text.splitlines()
    selected = None
    if section is not None:
        headings = heading_ranges(lines, rst=rst)
        needle = section.strip().casefold()
        matches = [h for h in headings if needle in (h['title'].casefold(), ' > '.join(h['path']).casefold())]
        if len(matches) != 1:
            candidates = matches or headings
            return {'error': 'ambiguous_section' if matches else 'section_not_found',
                    'section': section, 'candidates': candidates[:50],
                    'candidates_truncated': len(candidates) > 50}
        selected = matches[0]
        start_line, end_line = selected['start_line'], selected['end_line']
    start = start_line or 1
    if start > len(lines):
        return {'error': 'line_out_of_range', 'total_lines': len(lines), 'start_line': start}
    requested_end = min(end_line or len(lines), len(lines))
    end = min(requested_end, start + max_lines - 1)
    result = {'content': '\n'.join(lines[start-1:end]), 'total_lines': len(lines),
              'start_line': start, 'end_line': end, 'returned_lines': end - start + 1,
              'selection_end_line': requested_end, 'selection_truncated': end < requested_end,
              'excerpt_partial': start > 1 or end < len(lines),
              'next_start_line': end + 1 if end < requested_end else None}
    if selected:
        result['section'] = selected
    return result
