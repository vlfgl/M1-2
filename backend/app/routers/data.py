from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.db import NotFoundError
from app.schemas import DataCreate, DataOut, DataUpdate, Summary
from app.services import data_service, summary_service

router = APIRouter(prefix="/api/data", tags=["data"])


# 고정 경로(/summary)는 경로 변수 라우트보다 먼저 선언한다.
@router.get("/summary", response_model=Summary, summary="데이터 요약 (프롬프트 주입용)")
def get_summary():
    return summary_service.get_summary()


@router.get("", response_model=list[DataOut], summary="데이터 목록 조회")
def list_data(
    start: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="시작일 YYYY-MM-DD"),
    end: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="종료일 YYYY-MM-DD"),
    limit: Optional[int] = Query(None, ge=1, le=1000),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    return data_service.list_data(start, end, limit, descending=(order == "desc"))


@router.post("", response_model=DataOut, status_code=status.HTTP_201_CREATED, summary="새 데이터 추가")
def create_data(payload: DataCreate):
    return data_service.create_data(payload)


@router.put("/{doc_id}", response_model=DataOut, summary="데이터 수정")
def update_data(doc_id: str, payload: DataUpdate):
    try:
        return data_service.update_data(doc_id, payload)
    except NotFoundError:
        raise HTTPException(404, "해당 데이터를 찾을 수 없습니다.")
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT, summary="데이터 삭제")
def delete_data(doc_id: str):
    try:
        data_service.delete_data(doc_id)
    except NotFoundError:
        raise HTTPException(404, "해당 데이터를 찾을 수 없습니다.")
