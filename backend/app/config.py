"""환경 변수 로딩. 키/시크릿은 절대 코드에 하드코딩하지 않는다."""
import os
from dotenv import load_dotenv

load_dotenv()


def _list(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


class Settings:
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # 비용 제한: 답변 최대 토큰, 프롬프트에 포함할 이전 메시지 수
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "500"))
    CHAT_HISTORY_LIMIT: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))

    # 둘 중 하나: JSON 문자열(Render 권장) 또는 파일 경로(로컬)
    FIREBASE_SERVICE_ACCOUNT_JSON: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    FIREBASE_SERVICE_ACCOUNT_PATH: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "")

    # firestore(기본) | memory(로컬 테스트용, 재시작 시 초기화)
    DB_BACKEND: str = os.getenv("DB_BACKEND", "firestore").lower()

    ALLOWED_ORIGINS: list[str] = _list(
        os.getenv("ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000")
    )


settings = Settings()
