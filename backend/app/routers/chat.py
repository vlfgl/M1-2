from fastapi import APIRouter, HTTPException

from app.db import NotFoundError
from app.schemas import ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse,
             summary="AI 채팅 (데이터 요약 → 시스템 프롬프트 주입 → GPT → 대화 자동 저장)")
def chat(payload: ChatRequest):
    try:
        return chat_service.chat(payload.message, payload.conversation_id)
    except NotFoundError:
        raise HTTPException(404, "해당 대화를 찾을 수 없습니다.")
    except chat_service.ChatError as e:
        raise HTTPException(502, str(e))
