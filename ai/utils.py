import json


def _get_base_url(raw_url: str) -> str:
    url = (raw_url or '').strip().rstrip('/')
    if not url:
        return ''
    return url.rstrip('/v1') + '/v1'


def _content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ''
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get('text')
                if isinstance(text, str):
                    parts.append(text)
                    continue
                if isinstance(text, dict) and isinstance(text.get('value'), str):
                    parts.append(text['value'])
        if parts:
            return ''.join(parts)
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)
