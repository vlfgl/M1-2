"""Pydantic 스키마: 요청 검증과 응답 형태를 한 곳에서 정의한다."""
from datetime import date as Date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

MAX_AMOUNT = 100_000_000  # 1억 원: 오타로 인한 비정상 입력 방지


# ---------- 데이터 ----------
class DataCreate(BaseModel):
    date: Date = Field(..., description="지출 날짜 (YYYY-MM-DD)", examples=["2026-10-30"])
    value: int = Field(..., gt=0, le=MAX_AMOUNT, description="지출 금액(원)", examples=[12000])
    memo: str = Field("", max_length=200, description='"카테고리 | 설명" 형식 권장', examples=["식비 | 점심 식사"])

    @field_validator("memo")
    @classmethod
    def strip_memo(cls, v: str) -> str:
        return v.strip()


class DataUpdate(BaseModel):
    """부분 수정: 보낸 필드만 변경된다."""
    date: Optional[Date] = None
    value: Optional[int] = Field(None, gt=0, le=MAX_AMOUNT)
    memo: Optional[str] = Field(None, max_length=200)


class DataOut(BaseModel):
    id: str
    date: str
    value: int
    memo: str = ""


class Metrics(BaseModel):
    total: int
    average: int = Field(..., description="건당 평균 지출")
    daily_average: int = Field(..., description="일평균 지출(기간 전체 일수 기준)")
    monthly_average: int
    max: dict
    min: dict


class Summary(BaseModel):
    period: str
    count: int
    metrics: Metrics
    trend: str
    current_month: dict
    monthly_totals: dict[str, int]
    top_categories: list[dict]


# ---------- 대화 ----------
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    messages: list[Message] = Field(..., min_length=1)


class ConversationListItem(BaseModel):
    """목록 응답에는 messages를 포함하지 않는다(가볍게). 전체는 GET /api/conversations/{id}."""
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


class ConversationDetail(ConversationListItem):
    messages: list[Message]


# ---------- 채팅 ----------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, examples=["이번 달 지출 어때?"])
    conversation_id: Optional[str] = Field(None, description="이어서 대화할 경우 기존 대화 ID")

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("메시지가 비어 있습니다.")
        return v.strip()


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    summary: Summary
