import json
from typing import Generator
from openai import OpenAI

from .utils import _get_base_url, _content_to_text


# ── 公开 API ───────────────────────────────────────────────────────────────────

def build_openai_messages(history: list[dict]) -> list[dict]:
    """将内部 history（含 ts 等字段）转换成 OpenAI messages 格式"""
    messages: list[dict] = []
    for item in history:
        role = item.get('role')
        if role in ('system', 'user', 'tool'):
            msg: dict = {'role': role, 'content': item.get('content') or ''}
            # tool 消息需要附带 tool_call_id
            if role == 'tool' and item.get('tool_call_id'):
                msg['tool_call_id'] = item['tool_call_id']
            messages.append(msg)
        elif role in ('assistant', 'assistant_with_tool_calls'):
            # assistant 消息需要检查是否有 tool_calls
            msg: dict = {'role': 'assistant', 'content': item.get('content') or None}
            if item.get('tool_calls'):
                msg['tool_calls'] = item['tool_calls']
            messages.append(msg)
    return messages


def call_openai_chat_completion(messages: list[dict], cfg: dict) -> dict:
    ai_cfg = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model   = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    base_url = _get_base_url(api_url)

    if not base_url:
        return {'content': '⚠️ AI 接口未配置，请在设置中填写 api_url。'}

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    try:
        response = client.chat.completions.create(model=model, messages=messages)
        if not response.choices:
            return {'content': '⚠️ AI 返回为空'}
        message = response.choices[0].message
        if message is None:
            return {'content': '⚠️ AI 返回消息为空'}
        content = _content_to_text(message.content)
        return {'content': content}
    except Exception as e:
        return {'content': f'⚠️ AI 调用失败: {e}'}


def stream_openai_chat_completion(
    messages: list[dict],
    cfg: dict,
) -> Generator[tuple[str, str], None, None]:
    """
    流式调用（无工具），每项为 (chunk_content, error_message)。
    """
    ai_cfg   = cfg.get('ai', {})
    api_url  = ai_cfg.get('api_url', '')
    api_key  = ai_cfg.get('api_key', '')
    model    = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout  = int(ai_cfg.get('timeout', 60))
    base_url = _get_base_url(api_url)

    if not base_url:
        yield ('', '⚠️ AI 接口未配置，请在设置中填写 api_url。')
        return

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    try:
        response = client.chat.completions.create(
            model=model, messages=messages, stream=True
        )
        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta is not None and delta.content:
                yield (delta.content, '')
    except Exception as e:
        yield ('', f'⚠️ AI 调用失败: {e}')


def stream_openai_chat_with_tools(
    messages: list[dict],
    cfg: dict,
    tools: list[dict] | None = None,
) -> Generator[tuple[str, str, dict | None], None, None]:
    """
    支持 function calling 的流式对话。
    每项为 (chunk_content, error_message, tool_call | None)。

    当 AI 请求调用工具时，chunk_content / error_message 均为空，
    tool_call 为 {'id': str, 'name': str, 'arguments': dict}。

    正常文本流时，tool_call 为 None。
    """
    ai_cfg   = cfg.get('ai', {})
    api_url  = ai_cfg.get('api_url', '')
    api_key  = ai_cfg.get('api_key', '')
    model    = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout  = int(ai_cfg.get('timeout', 60))
    base_url = _get_base_url(api_url)

    if not base_url:
        yield ('', '⚠️ AI 接口未配置，请在设置中填写 api_url。', None)
        return

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    kwargs: dict = {'model': model, 'messages': messages, 'stream': True}
    if tools:
        kwargs['tools'] = tools
        kwargs['tool_choice'] = 'auto'

    try:
        response = client.chat.completions.create(**kwargs)

        # 用于累积 tool_calls（delta 是增量，需要拼接）
        pending_tool_calls: dict[int, dict] = {}   # index -> {id, name, arguments_str}
        finish_reason = None

        for chunk in response:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            finish_reason = choice.finish_reason or finish_reason
            delta = choice.delta

            # ── 普通文本内容 ────────────────────────────────────────────────
            if delta is not None and delta.content:
                yield (delta.content, '', None)

            # ── 工具调用增量 ────────────────────────────────────────────────
            if delta is not None and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in pending_tool_calls:
                        pending_tool_calls[idx] = {
                            'id': '',
                            'name': '',
                            'arguments_str': '',
                        }
                    tc = pending_tool_calls[idx]
                    if tc_delta.id:
                        tc['id'] += tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            tc['name'] += tc_delta.function.name
                        if tc_delta.function.arguments:
                            tc['arguments_str'] += tc_delta.function.arguments

        # ── 流结束，若有工具调用则 yield ────────────────────────────────────
        # 兼容性处理：只要收集到了工具调用信息，就应该执行，不完全依赖 finish_reason
        if (finish_reason == 'tool_calls' or finish_reason == 'function_call' or len(pending_tool_calls) > 0) and pending_tool_calls:
            for tc in pending_tool_calls.values():
                try:
                    arguments = json.loads(tc['arguments_str'] or '{}')
                except json.JSONDecodeError:
                    arguments = {'raw': tc['arguments_str']}
                yield ('', '', {
                    'id': tc['id'],
                    'name': tc['name'],
                    'arguments': arguments,
                })

    except Exception as e:
        yield ('', f'⚠️ AI 调用失败: {e}', None)
