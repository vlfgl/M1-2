"""CSV 데이터를 Firestore `data` 컬렉션에 업로드.

실행 (backend 폴더에서):  python -m scripts.seed_firestore [--reset]
  --reset : 기존 data 컬렉션 문서를 모두 삭제 후 업로드
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import DATA, FirestoreStore  # noqa: E402

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "spending_2026.csv"


def main():
    store = FirestoreStore()
    if "--reset" in sys.argv:
        docs = list(store.db.collection(DATA).stream())
        for i in range(0, len(docs), 400):
            batch = store.db.batch()
            for d in docs[i:i + 400]:
                batch.delete(d.reference)
            batch.commit()
        print(f"기존 {len(docs)}건 삭제")

    with CSV_PATH.open(encoding="utf-8") as f:
        rows = [{"date": r["date"], "value": int(r["value"]), "memo": r["memo"]} for r in csv.DictReader(f)]
    print(f"{store.batch_add(DATA, rows)}건 업로드 완료")


if __name__ == "__main__":
    main()
