import json
import urllib.error
import urllib.request
from json import JSONDecodeError


def _candidate_chat_urls(raw_url: str) -> list[str]:
    url = (raw_url or '').strip().rstrip('/')
    if not url:
        return []

    lower_url = url.lower()
    candidates: list[str] = []
    if lower_url.endswith('/chat/completions'):
        candidates.append(url)
    elif lower_url.endswith('/v1'):
        candidates.append(f'{url}/chat/completions')
        candidates.append(f'{url[:-3]}/chat/completions')
    else:
        candidates.append(f'{url}/v1/chat/completions')
        candidates.append(f'{url}/chat/completions')

    results: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item and item not in seen:
            results.append(item)
            seen.add(item)
    return results


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


def _parse_tool_arguments(raw_arguments) -> tuple[dict, str]:
    if isinstance(raw_arguments, str):
        arguments_text = raw_arguments.strip() or '{}'
    elif raw_arguments is None:
        arguments_text = '{}'
    else:
        try:
            arguments_text = json.dumps(raw_arguments, ensure_ascii=False)
        except Exception:
            arguments_text = '{}'

    parsed_arguments: dict = {}
    try:
        data = json.loads(arguments_text)
        if isinstance(data, dict):
            parsed_arguments = data
    except Exception:
        parsed_arguments = {}

    return parsed_arguments, arguments_text


def normalize_tool_call(tool_call: dict) -> dict:
    function = tool_call.get('function') or {}
    arguments, arguments_text = _parse_tool_arguments(function.get('arguments'))
    return {
        'id': tool_call.get('id', ''),
        'type': tool_call.get('type', 'function'),
        'name': function.get('name', ''),
        'arguments': arguments,
        'arguments_text': arguments_text,
    }


def build_assistant_tool_calls(tool_calls: list[dict] | None) -> list[dict]:
    results: list[dict] = []
    for tool_call in tool_calls or []:
        arguments_text = tool_call.get('arguments_text')
        if not isinstance(arguments_text, str) or not arguments_text.strip():
            arguments_text = json.dumps(tool_call.get('arguments', {}), ensure_ascii=False)
        results.append({
            'id': tool_call.get('id', ''),
            'type': 'function',
            'function': {
                'name': tool_call.get('name', ''),
                'arguments': arguments_text,
            },
        })
    return results


def build_openai_messages(history: list[dict]) -> list[dict]:
    messages: list[dict] = []
    for item in history:
        role = item.get('role')
        if role == 'assistant' and item.get('tool_calls'):
            messages.append({
                'role': 'assistant',
                'content': item.get('content') or '',
                'tool_calls': build_assistant_tool_calls(item.get('tool_calls') or []),
            })
            continue
        if role == 'tool':
            messages.append({
                'role': 'tool',
                'tool_call_id': item.get('tool_call_id', ''),
                'name': item.get('name', ''),
                'content': item.get('content') or '',
            })
            continue
        if role in ('system', 'user', 'assistant'):
            messages.append({
                'role': role,
                'content': item.get('content') or '',
            })
    return messages


def call_openai_chat_completion(messages: list[dict], cfg: dict, tools: list[dict] | None = None, tool_choice='auto') -> dict:
    ai_cfg = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    endpoints = _candidate_chat_urls(api_url)

    if not endpoints:
        return {'content': '⚠️ AI 接口未配置，请在设置中填写 api_url。', 'tool_calls': []}

    req_body: dict = {
        'model': model,
        'messages': messages,
        'stream': False,
    }
    if tools:
        req_body['tools'] = tools
        if tool_choice is not None:
            req_body['tool_choice'] = tool_choice

    body = json.dumps(req_body).encode()
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    last_http_error = None
    last_parse_error = None

    for endpoint in endpoints:
        req = urllib.request.Request(endpoint, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_bytes = resp.read()
                raw_text = raw_bytes.decode('utf-8', errors='ignore').strip()
                if not raw_text:
                    last_parse_error = f'空响应 @ {endpoint}'
                    continue

                try:
                    data = json.loads(raw_text)
                except JSONDecodeError:
                    snippet = raw_text[:200].replace('\n', ' ')
                    last_parse_error = f'非 JSON 响应 @ {endpoint}: {snippet}'
                    continue

                try:
                    message = data['choices'][0]['message']
                    content = _content_to_text(message.get('content'))
                    tool_calls = [normalize_tool_call(item) for item in (message.get('tool_calls') or [])]
                    return {
                        'content': content,
                        'tool_calls': tool_calls,
                    }
                except Exception:
                    preview = json.dumps(data, ensure_ascii=False)[:300]
                    last_parse_error = f'JSON 结构非 OpenAI 格式 @ {endpoint}: {preview}'
                    continue
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8', errors='ignore')
            except Exception:
                detail = ''
            if exc.code == 404:
                last_http_error = f'HTTP 404 Not Found @ {endpoint}'
                continue
            if detail:
                return {'content': f'⚠️ AI 调用失败: HTTP {exc.code} {exc.reason} - {detail[:300]}', 'tool_calls': []}
            return {'content': f'⚠️ AI 调用失败: HTTP {exc.code} {exc.reason}', 'tool_calls': []}
        except Exception as exc:
            return {'content': f'⚠️ AI 调用失败: {exc}', 'tool_calls': []}

    if last_http_error:
        return {'content': f'⚠️ AI 调用失败: {last_http_error}', 'tool_calls': []}
    if last_parse_error:
        return {'content': f'⚠️ AI 调用失败: {last_parse_error}', 'tool_calls': []}
    return {'content': '⚠️ AI 调用失败: 未知错误。', 'tool_calls': []}
