"""
AI Chat API — Gemini + MCP Tools
"""
from pydantic import BaseModel
from fastapi import APIRouter

from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


# ─── Request / Response Models ────────────────────────────────


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ToolUsed(BaseModel):
    name: str
    args: dict
    result: str


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[ToolUsed] = []


# ═══════════════════════════════════════════════════════════════
# Task 6: POST /ai/chat (P0)
# ═══════════════════════════════════════════════════════════════


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(body: ChatRequest):
    """
    AI 對話 — 發送訊息給 Gemini，透過 MCP Tools 查詢工廠資料後回覆。
    """
    history = [{"role": m.role, "content": m.content} for m in body.history]
    result = await ai_service.chat(body.message, history)
    return ChatResponse(**result)
