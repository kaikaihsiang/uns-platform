"""
UNS Platform — MCP Server

獨立 Python process，透過 stdio transport 提供 MCP Protocol。
呼叫 Backend REST API 來查詢工廠資料。

Tools:
  - browse_namespace(path)  → 瀏覽 Namespace 子節點
  - query_telemetry(tag_id, start, end) → 查詢歷史時序資料
  - get_latest_values(tag_ids) → 批次查詢最新值

Resources:
  - uns://namespace/tree → Namespace 全貌（快取）

Usage:
  python server.py
"""
import json
import logging
from datetime import datetime

import httpx
from mcp.server.fastmcp import FastMCP

# ─── Config ───────────────────────────────────────────────────

BACKEND_URL = "http://localhost:8000"
LOG_LEVEL = logging.INFO

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s [MCP] %(message)s")
logger = logging.getLogger("uns-mcp")

# ─── MCP Server ───────────────────────────────────────────────

mcp = FastMCP("UNS Platform")

# Shared HTTP client
_client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0)


# ─── Resource ─────────────────────────────────────────────────


@mcp.resource("uns://namespace/tree")
async def namespace_tree() -> str:
    """
    UNS Namespace 完整樹狀結構。
    包含所有 Enterprise / Site / Area / Line / Equipment / Topic 節點。
    """
    resp = await _client.get("/api/v1/namespace/tree")
    resp.raise_for_status()
    return json.dumps(resp.json(), indent=2, ensure_ascii=False)


# ─── Tools ────────────────────────────────────────────────────


@mcp.tool()
async def browse_namespace(path: str = "") -> str:
    """
    瀏覽 Namespace 的子節點。

    給定一個 path（例如 "TaiwanPrecision/Taoyuan"），回傳該路徑下的所有直接子節點。
    如果 path 為空，回傳所有根節點。

    回傳資訊包含：node_id, name, node_type (structural/topic), full_path, children 數量。

    Args:
        path: Namespace 路徑，例如 "TaiwanPrecision/Taoyuan/SMT"。留空則回傳根節點。
    """
    resp = await _client.get("/api/v1/namespace/tree")
    resp.raise_for_status()
    tree = resp.json()

    if not path:
        # 回傳根節點
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

    # 找到指定 path 的節點
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


@mcp.tool()
async def query_telemetry(
    tag_id: int,
    start: str | None = None,
    end: str | None = None,
    limit: int = 100,
) -> str:
    """
    查詢 Tag 的歷史時序資料。

    回傳指定 tag_id 的時序資料，可指定時間範圍。
    即使設備搬遷（Live Migration），用 tag_id 查詢仍可取得完整的連續歷史。

    Args:
        tag_id: Tag 的唯一識別碼（永久不變，跨 migration 連續）。
        start: 起始時間，ISO 8601 格式，例如 "2026-03-01T00:00:00Z"。
        end: 結束時間，ISO 8601 格式。
        limit: 回傳筆數上限，預設 100。
    """
    params = {"limit": limit}
    if start:
        params["from"] = start
    if end:
        params["to"] = end

    resp = await _client.get(f"/api/v1/tags/{tag_id}/values", params=params)
    resp.raise_for_status()
    data = resp.json()

    # 格式化成 LLM 容易讀的格式
    tag_info = data.get("tag", {})
    points = data.get("data", [])

    result = {
        "tag": {
            "tag_id": tag_info.get("tag_id"),
            "display_name": tag_info.get("display_name"),
            "asset_path": tag_info.get("asset_path"),
            "category": tag_info.get("category"),
            "data_point": tag_info.get("data_point"),
            "unit": tag_info.get("unit"),
        },
        "count": len(points),
        "data": points,
    }
    return json.dumps(result, indent=2, ensure_ascii=False, default=str)


@mcp.tool()
async def get_latest_values(tag_ids: list[int]) -> str:
    """
    批次查詢多個 Tag 的最新值。

    適合用來「看一下現在生產線的狀態」或「比較多個設備的溫度」。

    Args:
        tag_ids: Tag ID 列表，例如 [1, 2, 3]。
    """
    results = []
    for tid in tag_ids:
        try:
            resp = await _client.get(f"/api/v1/tags/{tid}/latest")
            resp.raise_for_status()
            data = resp.json()
            tag_info = data.get("tag", {})
            latest = data.get("latest")

            results.append({
                "tag_id": tid,
                "display_name": tag_info.get("display_name"),
                "asset_path": tag_info.get("asset_path"),
                "unit": tag_info.get("unit"),
                "latest_value": latest.get("value") if latest else None,
                "latest_time": latest.get("time") if latest else None,
                "quality": latest.get("quality") if latest else None,
            })
        except Exception as e:
            results.append({
                "tag_id": tid,
                "error": str(e),
            })

    return json.dumps(results, indent=2, ensure_ascii=False, default=str)


# ─── Entry point ──────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("Starting UNS MCP Server (stdio transport)")
    logger.info(f"Backend URL: {BACKEND_URL}")
    mcp.run(transport="stdio")
