from fastapi import APIRouter, HTTPException, status

from app.db import NotFoundError
from app.schemas import ConversationCreate, ConversationDetail, ConversationListItem
from app.services import conversation_service

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED, summary="대화 저장")
def create_conversation(payload: ConversationCreate):
    msgs = [m.model_dump() for m in payload.messages]
    doc = conversation_service.create_conversation(msgs, payload.title)
    return conversation_service.get_conversation(doc["id"])


@router.get("", response_model=list[ConversationListItem],
            summary="대화 목록 조회 (messages 미포함, 최근 수정순)")
def list_conversations():
    return conversation_service.list_conversations()


@router.get("/{conv_id}", response_model=ConversationDetail, summary="특정 대화 전체 messages 조회")
def get_conversation(conv_id: str):
    try:
        return conversation_service.get_conversation(conv_id)
    except NotFoundError:
        raise HTTPException(404, "해당 대화를 찾을 수 없습니다.")


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT, summary="대화 삭제")
def delete_conversation(conv_id: str):
    try:
        conversation_service.delete_conversation(conv_id)
    except NotFoundError:
        raise HTTPException(404, "해당 대화를 찾을 수 없습니다.")
