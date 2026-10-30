"""DB 접근 계층.

서비스 코드는 `get_store()`가 돌려주는 저장소의 공통 메서드만 사용한다.
- FirestoreStore: 실제 운영 (Firebase Firestore)
- MemoryStore: 키 없이 로컬에서 API 흐름을 검증할 때 사용 (DB_BACKEND=memory)
"""
from __future__ import annotations  # 클래스 내 list 메서드가 내장 list 타입을 가리지 않도록

import json
import uuid
from copy import deepcopy
from functools import lru_cache
from typing import Any, Optional

from app.config import settings

DATA = "data"
CONVERSATIONS = "conversations"


class NotFoundError(Exception):
    pass


class FirestoreStore:
    def __init__(self):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
                info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
                # 환경변수로 넣을 때 개행이 "\\n" 문자열로 들어오는 경우 복원
                if "private_key" in info:
                    info["private_key"] = info["private_key"].replace("\\n", "\n")
                cred = credentials.Certificate(info)
            elif settings.FIREBASE_SERVICE_ACCOUNT_PATH:
                cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
            else:
                raise RuntimeError(
                    "Firebase 자격 증명이 없습니다. FIREBASE_SERVICE_ACCOUNT_JSON 또는 "
                    "FIREBASE_SERVICE_ACCOUNT_PATH를 설정하거나, 테스트용으로 DB_BACKEND=memory를 사용하세요."
                )
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def list(self, collection: str, order_by: Optional[str] = None, descending: bool = False,
             filters: Optional[list[tuple[str, str, Any]]] = None, limit: Optional[int] = None) -> list[dict]:
        from google.cloud.firestore_v1.base_query import FieldFilter
        from firebase_admin import firestore

        q = self.db.collection(collection)
        for field, op, value in filters or []:
            q = q.where(filter=FieldFilter(field, op, value))
        if order_by:
            q = q.order_by(order_by, direction=firestore.Query.DESCENDING if descending else firestore.Query.ASCENDING)
        if limit:
            q = q.limit(limit)
        return [{"id": doc.id, **doc.to_dict()} for doc in q.stream()]

    def get(self, collection: str, doc_id: str) -> dict:
        doc = self.db.collection(collection).document(doc_id).get()
        if not doc.exists:
            raise NotFoundError(doc_id)
        return {"id": doc.id, **doc.to_dict()}

    def add(self, collection: str, data: dict) -> dict:
        ref = self.db.collection(collection).document()
        ref.set(data)
        return {"id": ref.id, **data}

    def update(self, collection: str, doc_id: str, data: dict) -> dict:
        ref = self.db.collection(collection).document(doc_id)
        if not ref.get().exists:
            raise NotFoundError(doc_id)
        ref.update(data)
        return self.get(collection, doc_id)

    def delete(self, collection: str, doc_id: str) -> None:
        ref = self.db.collection(collection).document(doc_id)
        if not ref.get().exists:
            raise NotFoundError(doc_id)
        ref.delete()

    def batch_add(self, collection: str, items: list[dict]) -> int:
        count = 0
        for i in range(0, len(items), 400):  # Firestore 배치 한도 500
            batch = self.db.batch()
            for item in items[i:i + 400]:
                batch.set(self.db.collection(collection).document(), item)
                count += 1
            batch.commit()
        return count


class MemoryStore:
    _OPS = {
        "==": lambda a, b: a == b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, "<": lambda a, b: a < b,
    }

    def __init__(self):
        self.collections: dict[str, dict[str, dict]] = {}

    def _col(self, name: str) -> dict[str, dict]:
        return self.collections.setdefault(name, {})

    def list(self, collection, order_by=None, descending=False, filters=None, limit=None):
        items = [{"id": k, **deepcopy(v)} for k, v in self._col(collection).items()]
        for field, op, value in filters or []:
            items = [x for x in items if field in x and self._OPS[op](x[field], value)]
        if order_by:
            items.sort(key=lambda x: x.get(order_by), reverse=descending)
        return items[:limit] if limit else items

    def get(self, collection, doc_id):
        if doc_id not in self._col(collection):
            raise NotFoundError(doc_id)
        return {"id": doc_id, **deepcopy(self._col(collection)[doc_id])}

    def add(self, collection, data):
        doc_id = uuid.uuid4().hex[:20]
        self._col(collection)[doc_id] = deepcopy(data)
        return {"id": doc_id, **data}

    def update(self, collection, doc_id, data):
        if doc_id not in self._col(collection):
            raise NotFoundError(doc_id)
        self._col(collection)[doc_id].update(deepcopy(data))
        return self.get(collection, doc_id)

    def delete(self, collection, doc_id):
        if doc_id not in self._col(collection):
            raise NotFoundError(doc_id)
        del self._col(collection)[doc_id]

    def batch_add(self, collection, items):
        for item in items:
            self.add(collection, item)
        return len(items)


@lru_cache
def get_store():
    if settings.DB_BACKEND == "memory":
        store = MemoryStore()
        _seed_memory(store)
        return store
    return FirestoreStore()


def _seed_memory(store: MemoryStore) -> None:
    """메모리 모드에서는 CSV를 자동으로 불러와 바로 테스트할 수 있게 한다."""
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "spending_2026.csv"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            rows = [{"date": r["date"], "value": int(r["value"]), "memo": r["memo"]} for r in csv.DictReader(f)]
        store.batch_add(DATA, rows)
