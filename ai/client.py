import json
from typing import Generator
from openai import OpenAI
def _get_base_url(raw_url: str) -> str:
    url = (raw_url or '').strip().rstrip('/')
    if not url:
        return ''
    # 直接添加 /v1
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


def build_openai_messages(history: list[dict]) -> list[dict]:
    messages: list[dict] = []
    for item in history:
        role = item.get('role')
        if role in ('system', 'user', 'assistant'):
            messages.append({
                'role': role,
                'content': item.get('content') or '',
            })
    return messages


def call_openai_chat_completion(messages: list[dict], cfg: dict) -> dict:
    ai_cfg = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    base_url = _get_base_url(api_url)

    if not base_url:
        return {'content': '⚠️ AI 接口未配置，请在设置中填写 api_url。'}

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
        content = _content_to_text(response.choices[0].message.content)
        return {'content': content}
    except Exception as e:
        return {'content': f'⚠️ AI 调用失败: {e}'}


def stream_openai_chat_completion(
    messages: list[dict],
    cfg: dict
) -> Generator[tuple[str, str], None, None]:
    """
    流式调用 OpenAI-compatible 接口
    返回生成器，每项为 (chunk_content, error_message)
    """
    ai_cfg = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    base_url = _get_base_url(api_url)

    if not base_url:
        yield ('', '⚠️ AI 接口未配置，请在设置中填写 api_url。')
        return

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True
        )
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield (delta.content, '')
    except Exception as e:
        yield ('', f'⚠️ AI 调用失败: {e}')
