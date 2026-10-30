"""시계열 지출 데이터 분석 → 요약 생성 (프롬프트 주입용).

요약은 채팅마다 필요하므로 메모리 캐시를 두고, 데이터가 바뀌면(CRUD) 무효화한다.
→ 매 채팅마다 Firestore 전체 문서를 다시 읽는 비용(읽기 횟수)을 줄인다.
"""
from collections import defaultdict
from datetime import date, timedelta
from threading import Lock
from typing import Optional

from app.db import DATA, get_store

_cache: Optional[dict] = None
_lock = Lock()


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def get_summary() -> dict:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
    rows = get_store().list(DATA, order_by="date")
    result = build_summary(rows)
    with _lock:
        _cache = result
    return result


def _category(memo: str) -> str:
    return memo.split("|")[0].strip() if memo and "|" in memo else (memo.strip() or "기타")


def _pct(a: float, b: float) -> Optional[float]:
    return round((a - b) / b * 100, 1) if b else None


def _trend_label(change: Optional[float], threshold: float = 5.0) -> str:
    if change is None:
        return "판단 불가"
    if change > threshold:
        return "증가"
    if change < -threshold:
        return "감소"
    return "유지"


def build_summary(rows: list[dict]) -> dict:
    if not rows:
        return {
            "period": "데이터 없음", "count": 0,
            "metrics": {"total": 0, "average": 0, "daily_average": 0, "monthly_average": 0, "max": {}, "min": {}},
            "trend": "판단 불가", "current_month": {}, "monthly_totals": {}, "top_categories": [],
        }

    rows = sorted(rows, key=lambda r: r["date"])
    values = [int(r["value"]) for r in rows]
    total = sum(values)
    first, last = date.fromisoformat(rows[0]["date"]), date.fromisoformat(rows[-1]["date"])
    days = (last - first).days + 1

    daily = defaultdict(int)
    monthly = defaultdict(int)
    by_cat = defaultdict(int)
    for r in rows:
        daily[r["date"]] += int(r["value"])
        monthly[r["date"][:7]] += int(r["value"])
        by_cat[_category(r.get("memo", ""))] += int(r["value"])

    max_row = max(rows, key=lambda r: r["value"])
    min_row = min(rows, key=lambda r: r["value"])

    # 최근 30일 vs 직전 30일 (데이터의 마지막 날짜 기준)
    def window_sum(end: date, length: int) -> int:
        start = end - timedelta(days=length - 1)
        return sum(v for d, v in daily.items() if start.isoformat() <= d <= end.isoformat())

    recent = window_sum(last, 30)
    previous = window_sum(last - timedelta(days=30), 30)
    change = _pct(recent, previous)
    trend = f"{_trend_label(change)} (최근 30일 {recent:,}원, 직전 30일 대비 {change:+.1f}%)" if change is not None \
        else "판단 불가 (비교 기간 데이터 부족)"

    # 이번 달(마지막 데이터의 달): 경과 일수 기준 일평균으로 월말 예상치 계산
    cur_key = last.strftime("%Y-%m")
    cur_total = monthly[cur_key]
    full_months = {k: v for k, v in monthly.items() if k != cur_key}
    monthly_avg = sum(full_months.values()) / len(full_months) if full_months else cur_total
    elapsed = last.day
    projected = round(cur_total / elapsed * _days_in_month(last)) if elapsed else cur_total

    top = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "period": f"{first.isoformat()} ~ {last.isoformat()}",
        "count": len(rows),
        "metrics": {
            "total": total,
            "average": round(total / len(rows)),
            "daily_average": round(total / days),
            "monthly_average": round(monthly_avg),
            "max": {"date": max_row["date"], "value": max_row["value"], "memo": max_row.get("memo", "")},
            "min": {"date": min_row["date"], "value": min_row["value"], "memo": min_row.get("memo", "")},
        },
        "trend": trend,
        "current_month": {
            "month": cur_key,
            "total": cur_total,
            "elapsed_days": elapsed,
            "projected_total": projected,
            "vs_monthly_average_pct": _pct(projected, monthly_avg),
        },
        "monthly_totals": dict(sorted(monthly.items())),
        "top_categories": [
            {"category": c, "total": v, "share_pct": round(v / total * 100, 1)} for c, v in top
        ],
    }


def _days_in_month(d: date) -> int:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def to_prompt_text(s: dict) -> str:
    """요약 dict → 시스템 프롬프트에 넣을 짧은 텍스트 (토큰 절약)."""
    if not s["count"]:
        return "- 저장된 지출 데이터가 없습니다."
    m, cm = s["metrics"], s["current_month"]
    monthly = ", ".join(f"{k}: {v:,}원" for k, v in s["monthly_totals"].items())
    cats = ", ".join(f"{c['category']} {c['total']:,}원({c['share_pct']}%)" for c in s["top_categories"])
    return "\n".join([
        f"- 데이터 기간: {s['period']}",
        f"- 총 레코드: {s['count']}건",
        f"- 총 지출: {m['total']:,}원 / 월평균 {m['monthly_average']:,}원 / 일평균 {m['daily_average']:,}원 / 건당 평균 {m['average']:,}원",
        f"- 최대 지출: {m['max']['date']} {m['max']['value']:,}원 ({m['max']['memo']})",
        f"- 최소 지출: {m['min']['date']} {m['min']['value']:,}원 ({m['min']['memo']})",
        f"- 최근 트렌드: {s['trend']}",
        f"- 이번 달({cm['month']}): {cm['elapsed_days']}일 경과, 현재 {cm['total']:,}원, 월말 예상 {cm['projected_total']:,}원 "
        f"(월평균 대비 {cm['vs_monthly_average_pct']:+}%)",
        f"- 월별 지출: {monthly}",
        f"- 카테고리 상위: {cats}",
    ])
