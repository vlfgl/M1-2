import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import chat, conversations, data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finance-assistant")

app = FastAPI(
    title="개인 재무 관리 AI 비서 API",
    description="소비 지출 시계열 데이터를 요약해 GPT 시스템 프롬프트에 주입하는 AI 비서 백엔드",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # 내부 정보(키, 스택)는 응답에 노출하지 않고 로그로만 남긴다.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "서버 내부 오류가 발생했습니다."})


@app.get("/", tags=["health"])
def root():
    return {"service": "finance-assistant", "docs": "/docs"}


@app.get("/health", tags=["health"], summary="헬스 체크 (콜드스타트 깨우기용)")
def health():
    return {"status": "ok"}
