"""2026년 가상 소비 지출 데이터 생성기.

- 기간: 2026-01-01 ~ 2026-10-30
- 레코드 1건 = 지출 1건 (date, value, memo)
- memo 형식: "카테고리 | 설명"  → 요약 시 카테고리별 집계에 사용
- 재현 가능하도록 seed 고정

실행: python scripts/generate_data.py  →  data/spending_2026.csv
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 2026
START = date(2026, 1, 1)
END = date(2026, 10, 30)
OUT = Path(__file__).resolve().parent.parent / "data" / "spending_2026.csv"

# (카테고리, 설명 후보, 최소금액, 최대금액, 하루 발생확률(평일), 주말 확률)
VARIABLE = [
    ("식비", ["점심 식사", "저녁 외식", "편의점", "배달 주문", "마트 장보기"], 6000, 35000, 0.85, 0.75),
    ("카페", ["아메리카노", "카페 라떼", "디저트"], 3500, 9000, 0.55, 0.45),
    ("교통", ["지하철/버스", "택시"], 1500, 18000, 0.6, 0.25),
    ("쇼핑", ["온라인 쇼핑", "의류 구매", "생활용품"], 12000, 120000, 0.08, 0.2),
    ("문화/여가", ["영화 관람", "전시회", "친구 모임", "운동 클래스"], 10000, 60000, 0.05, 0.25),
    ("의료", ["약국", "병원 진료"], 4000, 30000, 0.03, 0.02),
]

# (매월 일자, 카테고리, 설명, 금액)
FIXED = [
    (1, "주거/통신", "월세", 550000),
    (5, "주거/통신", "휴대폰 요금", 55000),
    (10, "구독", "OTT 구독", 13500),
    (15, "구독", "음악 스트리밍", 10900),
    (25, "주거/통신", "관리비/공과금", 0),  # 계절별로 금액 결정
]


def utility_bill(month: int) -> int:
    # 겨울 난방, 여름 냉방으로 공과금 상승
    base = {1: 160000, 2: 150000, 3: 110000, 7: 120000, 8: 135000, 12: 150000}
    return base.get(month, 85000)


def spending_multiplier(d: date) -> float:
    """최근 몇 달 지출이 서서히 늘어나는 패턴 + 특정 이벤트."""
    m = 1.0 + (d.month - 1) * 0.025  # 월별 완만한 상승
    if d.month == 2 and d.day <= 20:  # 설 연휴 무렵
        m *= 1.15
    if d.month == 12 or (d.month == 10 and d.day >= 1 and d.day <= 9):  # 추석/연휴
        m *= 1.2
    return m


def round100(x: float) -> int:
    return int(round(x / 100.0)) * 100


def generate():
    rng = random.Random(SEED)
    rows = []
    d = START
    while d <= END:
        weekend = d.weekday() >= 5
        mult = spending_multiplier(d)

        for day, cat, desc, amount in FIXED:
            if d.day == day:
                amt = utility_bill(d.month) if desc == "관리비/공과금" else amount
                rows.append((d.isoformat(), amt, f"{cat} | {desc}"))

        for cat, descs, lo, hi, p_wd, p_we in VARIABLE:
            if rng.random() < (p_we if weekend else p_wd):
                amt = rng.uniform(lo, hi) * mult
                rows.append((d.isoformat(), round100(amt), f"{cat} | {rng.choice(descs)}"))

        d += timedelta(days=1)

    # 큰 일회성 지출 몇 건
    rows += [
        ("2026-03-14", 890000, "쇼핑 | 노트북 구매"),
        ("2026-06-21", 420000, "문화/여가 | 제주 여행 숙소"),
        ("2026-08-09", 310000, "문화/여가 | 여름 휴가 항공권"),
    ]
    rows.sort(key=lambda r: r[0])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "value", "memo"])
        w.writerows(rows)
    print(f"{len(rows)}건 생성 → {OUT}")


if __name__ == "__main__":
    generate()
