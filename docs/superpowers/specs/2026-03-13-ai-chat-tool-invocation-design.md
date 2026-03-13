# AI Chat Tool Invocation Design (2026-03-13)

## Context
AimiGuard’s `/api/v1/ai/chat` endpoint currently calls an OpenAI-compatible `/chat/completions` API with only `{model, messages, stream:false}`. It does not send tool definitions and does not parse `tool_calls`/`function_call`. As a result, tool invocation is never triggered in the chat endpoint. Additionally, `nmap_plugin/ai_scanner.py` streams tool calls but parses `function.arguments` immediately per chunk, which fails when arguments arrive in fragments.

## Goals
- Enable tool calling in `/api/v1/ai/chat` for **nmap_scan** with a structure that allows future tools to be added.
- Execute real Nmap scans and persist results to the database when `nmap_scan` is called.
- Fix tool-call streaming parsing in `nmap_plugin/ai_scanner.py` by accumulating argument fragments before JSON parsing.

## Non-Goals
- Building a new endpoint or changing the front-end.
- Introducing asynchronous background job infrastructure.
- Expanding tool set beyond `nmap_scan` in this change.

## Data Contracts
### `_call_ai` return shape
```json
{
  "content": "assistant reply text",
  "tool_calls": [
    {
      "id": "call_123",
      "type": "function",
      "function": {"name": "nmap_scan", "arguments": "{...}"}
    }
  ]
}
```
- `tool_calls` may be empty or omitted when no tool call is requested.
- Preserve `tool_call_id` for subsequent `role=tool` messages.

### Tool execution messages
```json
{"role": "tool", "tool_call_id": "call_123", "name": "nmap_scan", "content": "..."}
```

## Proposed Approach (Approved)
### 1) `/api/v1/ai/chat` tool-calling (sync)
- Introduce a tool schema list in `web/api_v1.py` (initially only `nmap_scan`).
- Implement a tool dispatcher map `{ tool_name: handler_fn }`.
- `_call_ai` will accept optional `tools` and return both assistant content and tool calls.
- `ai_chat` will:
  1. Call `_call_ai(..., tools=tool_defs)`.
  2. If tool calls are present, execute them sequentially (real scan + write DB).
  3. Append assistant message **with tool_calls** and tool result messages with `role=tool` + `tool_call_id`.
  4. Call `_call_ai` again **with full history including tool messages** to get final assistant reply.

### 2) Multi-tool calls handling
- Execute tool calls **sequentially** in the order returned by the model.
- If a tool name is unknown, create a `role=tool` message with an error payload and continue.

### 3) Tool argument validation
- Validate required fields (`target`) before execution.
- If invalid or JSON parse fails, respond with `role=tool` error content and skip execution.

### 4) Tool result truncation
- Truncate tool result payloads (e.g., first 15 host entries) to avoid overly large responses.

### 5) `nmap_plugin/ai_scanner.py` streaming tool-call parsing
- Accumulate tool call arguments by `tool_call.id` (fallback to `index`) across chunks.
- After stream finishes, reconstruct full arguments and then `json.loads` once.
- When echoing assistant tool_calls in follow-up messages, include merged arguments only.

## Data Flow (Chat Tool Call)
1. User → `/api/v1/ai/chat`
2. `_call_ai` with tools → gets `tool_calls`
3. Execute `nmap_scan` → results saved to DB
4. Append `role=tool` results → `_call_ai` second pass
5. Return final assistant reply

## Testing Strategy (TDD)
- Add tests that:
  - Verify `_call_ai` handles `tool_calls` responses.
  - Verify chat flow executes tool handler and returns assistant reply.
  - Verify streaming tool-call accumulation does not throw `JSONDecodeError` on partial chunks.

## Files to Change
- `web/api_v1.py`
- `nmap_plugin/ai_scanner.py`
- Add test files (location TBD based on existing test structure)

## Risks
- Long-running scans could block request thread (acceptable for now per scope).
- Tool results may be large; tool result truncation will be enforced.

## Future Extensions
- Add new tools by extending tool schema list and handler map.
- Introduce async scanning jobs if needed.
