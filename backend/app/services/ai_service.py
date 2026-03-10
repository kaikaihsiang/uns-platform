"""
AI Service — Gemini LLM + MCP Tools (in-process)

核心邏輯：
1. 接收 user message + history
2. 定義 MCP tools 為 Gemini function declarations
3. 呼叫 Gemini API (with tool definitions)
4. 如果 Gemini 回傳 tool_call → 執行對應的 MCP 函式 → 回傳結果給 Gemini
5. 重複直到 Gemini 回傳純文字回覆
6. 回傳 reply + tools_used
"""
import json
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("uns.ai")

# ─── System Prompt ────────────────────────────────────────────

SYSTEM_PROMPT = """你是 UNS Platform AI 助手，專門協助工廠工程師查詢和分析工廠資料。

你可以使用以下工具查詢工廠資料：
- browse_namespace: 瀏覽 Namespace 結構（ISA-95 階層：Enterprise → Site → Area → Line → Equipment → Topic）
- query_telemetry: 查詢 Tag 歷史時序資料（溫度、壓力等連續參數）
- get_latest_values: 批次查詢多個 Tag 的最新值

回答問題時，請依據工具回傳的實際資料回覆。若無相關資料，請如實告知。
使用繁體中文回覆。保持簡潔、專業、有條理。
"""


# ─── MCP Tool Wrappers (in-process, via REST) ────────────────


async def _browse_namespace(path: str = "") -> str:
    """Browse namespace — calls the backend REST API."""
    import httpx
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        resp = await client.get("/api/v1/namespace/tree")
        resp.raise_for_status()
        tree = resp.json()

    if not path:
        result = [
            {
                "node_id": n["node_id"],
                "name": n["name"],
                "node_type": n["node_type"],
                "full_path": n["full_path"],
                "children_count": len(n.get("children", [])),
            }
            for n in tree
        ]
        return json.dumps(result, indent=2, ensure_ascii=False)

    def find_node(nodes, target_path):
        for n in nodes:
            if n["full_path"] == target_path:
                return n
            found = find_node(n.get("children", []), target_path)
            if found:
                return found
        return None

    node = find_node(tree, path)
    if not node:
        return json.dumps({"error": f"Path '{path}' not found"}, ensure_ascii=False)

    children = node.get("children", [])
    result = {
        "current": {
            "node_id": node["node_id"],
            "name": node["name"],
            "node_type": node["node_type"],
            "full_path": node["full_path"],
        },
        "children": [
            {
                "node_id": c["node_id"],
                "name": c["name"],
                "node_type": c["node_type"],
                "full_path": c["full_path"],
                "children_count": len(c.get("children", [])),
            }
            for c in children
        ],
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def _query_telemetry(tag_id: int, start: str | None = None, end: str | None = None, limit: int = 100) -> str:
    """Query tag telemetry — calls the backend REST API."""
    import httpx
    params: dict[str, Any] = {"limit": limit}
    if start:
        params["from"] = start
    if end:
        params["to"] = end

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        resp = await client.get(f"/api/v1/tags/{tag_id}/values", params=params)
        resp.raise_for_status()
        data = resp.json()

    tag_info = data.get("tag", {})
    points = data.get("data", [])
    result = {
        "tag": {
            "tag_id": tag_info.get("tag_id"),
            "display_name": tag_info.get("display_name"),
            "asset_path": tag_info.get("asset_path"),
            "unit": tag_info.get("unit"),
        },
        "count": len(points),
        "data": points[:20],  # Limit to 20 points for LLM context
    }
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


async def _get_latest_values(tag_ids: list[int]) -> str:
    """Get latest values for tags — calls the backend REST API."""
    import httpx
    results = []
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=10.0) as client:
        for tid in tag_ids:
            try:
                resp = await client.get(f"/api/v1/tags/{tid}/latest")
                resp.raise_for_status()
                data = resp.json()
                tag_info = data.get("tag", {})
                latest = data.get("latest")
                results.append({
                    "tag_id": tid,
                    "display_name": tag_info.get("display_name"),
                    "unit": tag_info.get("unit"),
                    "latest_value": latest.get("value") if latest else None,
                    "latest_time": latest.get("time") if latest else None,
                })
            except Exception as e:
                results.append({"tag_id": tid, "error": str(e)})
    return json.dumps(results, indent=2, ensure_ascii=False, default=str)


# Tool dispatch table
TOOL_FUNCTIONS = {
    "browse_namespace": _browse_namespace,
    "query_telemetry": _query_telemetry,
    "get_latest_values": _get_latest_values,
}


# ─── Gemini Chat ──────────────────────────────────────────────


async def chat(message: str, history: list[dict]) -> dict:
    """
    Send message to Gemini with MCP tools, return reply + tools_used.
    Falls back to a mock response if gemini_api_key is not configured.
    """
    if not settings.gemini_api_key:
        return await _mock_chat(message, history)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("google-genai not installed, falling back to mock")
        return await _mock_chat(message, history)

    # Configure client
    client = genai.Client(api_key=settings.gemini_api_key)

    # Define tools
    tool_declarations = types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="browse_namespace",
            description="瀏覽 Namespace 的子節點。給定 path 回傳子節點列表，留空回傳根節點。",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(type="STRING", description="Namespace 路徑，例如 'TaiwanPrecision/Taoyuan/SMT'。留空回傳根節點。"),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="query_telemetry",
            description="查詢 Tag 的歷史時序資料。用 tag_id 查詢，可指定時間範圍。",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "tag_id": types.Schema(type="INTEGER", description="Tag ID"),
                    "start": types.Schema(type="STRING", description="起始時間 ISO 8601"),
                    "end": types.Schema(type="STRING", description="結束時間 ISO 8601"),
                    "limit": types.Schema(type="INTEGER", description="回傳筆數上限"),
                },
                required=["tag_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_latest_values",
            description="批次查詢多個 Tag 的最新值。",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "tag_ids": types.Schema(
                        type="ARRAY",
                        items=types.Schema(type="INTEGER"),
                        description="Tag ID 列表",
                    ),
                },
                required=["tag_ids"],
            ),
        ),
    ])

    # Build conversation history
    contents = []
    for h in history:
        role = "user" if h["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=h["content"])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

    tools_used = []
    max_rounds = 5  # Prevent infinite tool-call loops

    for _ in range(max_rounds):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[tool_declarations],
            ),
        )

        # Check for tool calls
        candidate = response.candidates[0]
        has_tool_call = False

        for part in candidate.content.parts:
            if part.function_call:
                has_tool_call = True
                fc = part.function_call
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                logger.info(f"Tool call: {tool_name}({tool_args})")

                # Execute tool
                tool_fn = TOOL_FUNCTIONS.get(tool_name)
                if tool_fn:
                    try:
                        tool_result = await tool_fn(**tool_args)
                    except Exception as e:
                        tool_result = json.dumps({"error": str(e)})
                else:
                    tool_result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                tools_used.append({
                    "name": tool_name,
                    "args": tool_args,
                    "result": tool_result[:2000],  # Truncate for response
                })

                # Feed tool result back to Gemini
                contents.append(candidate.content)
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_result},
                    )],
                ))

        if not has_tool_call:
            # Final text response
            reply = candidate.content.parts[0].text if candidate.content.parts else "（無回覆）"
            return {"reply": reply, "tools_used": tools_used}

    # Max rounds exceeded
    reply = candidate.content.parts[0].text if candidate.content.parts else "（工具呼叫次數超出上限）"
    return {"reply": reply, "tools_used": tools_used}


async def _mock_chat(message: str, history: list[dict]) -> dict:
    """
    Mock chat for when gemini_api_key is not configured.
    Actually calls browse_namespace to show real data in the response.
    """
    tools_used = []

    # If the message mentions namespace or listing, actually browse
    if any(kw in message for kw in ["列出", "瀏覽", "namespace", "節點", "設備", "工廠"]):
        result = await _browse_namespace("")
        tools_used.append({
            "name": "browse_namespace",
            "args": {"path": ""},
            "result": result[:2000],
        })
        reply = f"⚠️ AI 助手目前在 Mock 模式（未設定 gemini_api_key）。\n\n以下是透過 browse_namespace 工具查詢到的根節點：\n\n```json\n{result}\n```"
    else:
        reply = (
            "⚠️ AI 助手目前在 Mock 模式（伺服器未設定 `gemini_api_key` 環境變數）。\n\n"
            "要啟用完整 AI 功能，請在 `backend/.env` 中設定：\n"
            "```\ngemini_api_key=your-api-key-here\n```\n\n"
            f"你的訊息是：「{message}」"
        )

    return {"reply": reply, "tools_used": tools_used}
