"""AI 채팅: 데이터 요약을 시스템 프롬프트에 주입(컨텍스트 주입)한 뒤 GPT 호출."""
from typing import Optional

from openai import OpenAI

from app.config import settings
from app.db import CONVERSATIONS, get_store
from app.services import conversation_service, summary_service

SYSTEM_TEMPLATE = """당신은 사용자의 개인 재무 관리 비서입니다.
아래는 사용자의 실제 소비 지출 데이터 요약입니다. 금액 단위는 원(KRW)입니다.

[사용자 지출 데이터 요약]
{summary}

규칙:
- 반드시 위 데이터를 근거로 구체적인 숫자를 들어 답하세요.
- 요약에 없는 정보(예: 특정 날짜의 개별 거래)는 추측하지 말고, 요약으로 알 수 있는 범위를 밝히세요.
- 절약 조언은 카테고리 비중과 추세를 근거로 실천 가능한 형태로 제시하세요.
- 한국어로, 3~6문장 이내로 간결하게 답하세요."""


class ChatError(Exception):
    pass


_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if not settings.OPENAI_API_KEY:
        raise ChatError("OPENAI_API_KEY가 설정되지 않았습니다.")
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=30)
    return _client


def build_system_prompt(summary: dict) -> str:
    return SYSTEM_TEMPLATE.format(summary=summary_service.to_prompt_text(summary))


def chat(message: str, conversation_id: Optional[str] = None) -> dict:
    # 1) 데이터 요약 조회
    summary = summary_service.get_summary()

    # 2) 요약을 시스템 프롬프트에 삽입 + 이전 대화 일부(비용 제한)
    history: list[dict] = []
    if conversation_id:
        conv = get_store().get(CONVERSATIONS, conversation_id)  # 없으면 NotFoundError
        history = conv.get("messages", [])[-settings.CHAT_HISTORY_LIMIT:]
    messages = [{"role": "system", "content": build_system_prompt(summary)}, *history,
                {"role": "user", "content": message}]

    # 3) GPT API 호출
    try:
        resp = _get_client().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_completion_tokens=settings.OPENAI_MAX_TOKENS,
        )
        reply = (resp.choices[0].message.content or "").strip() or "답변을 생성하지 못했습니다."
    except ChatError:
        raise
    except Exception as e:  # 네트워크/인증/쿼터 오류 등
        raise ChatError(f"AI 응답 생성 중 오류: {type(e).__name__}") from e

    # 4) conversations에 자동 저장
    new_msgs = [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
    if conversation_id:
        conversation_service.append_messages(conversation_id, new_msgs)
    else:
        conversation_id = conversation_service.create_conversation(new_msgs)["id"]

    return {"conversation_id": conversation_id, "reply": reply, "summary": summary}
