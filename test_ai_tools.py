import json
from openai import OpenAI
import os

config_path = r'C:\Users\lzx78\Desktop\AimiGuard\config.json'
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

ai_cfg = config.get('ai', {})
api_url = ai_cfg.get('api_url', '')
api_key = ai_cfg.get('api_key', '')
model = ai_cfg.get('model', 'gpt-3.5-turbo')

base_url = api_url
if '/v1' not in base_url:
    if base_url.endswith('/'):
        base_url += 'v1'
    else:
        base_url += '/v1'

client = OpenAI(api_key=api_key, base_url=base_url)

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "The city and state, e.g. San Francisco, CA"}
                },
                "required": ["location"]
            }
        }
    }
]

messages = [{"role": "user", "content": "What's the weather in Shanghai?"}]

print(f"Testing model: {model} with base_url: {base_url} (STREAMING)")

try:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        stream=True
    )
    
    pending_tool_calls = {}
    finish_reason = None
    for chunk in response:
        if not chunk.choices: continue
        choice = chunk.choices[0]
        finish_reason = choice.finish_reason or finish_reason
        delta = choice.delta
        if delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if idx not in pending_tool_calls:
                    pending_tool_calls[idx] = {'id': '', 'name': '', 'arguments_str': ''}
                tc = pending_tool_calls[idx]
                if tc_delta.id: tc['id'] += tc_delta.id
                if tc_delta.function:
                    if tc_delta.function.name: tc['name'] += tc_delta.function.name
                    if tc_delta.function.arguments: tc['arguments_str'] += tc_delta.function.arguments

    print(f"Finish Reason: {finish_reason}")
    print(f"Pending Tool Calls: {pending_tool_calls}")

    if pending_tool_calls:
        print("SUCCESS: Model supports streaming tool calls.")
    else:
        print("FAILURE: Model did not return any streaming tool calls.")
except Exception as e:
    print(f"ERROR: {e}")
