"""납기 기준 검증 모듈

제작물 유형별 최소 소요일과 희망 납기일을 비교한다.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from config import DEADLINE_FLAT, STATUS_FAIL, STATUS_PASS, STATUS_WARN


def parse_date(date_str: str) -> date | None:
    """날짜 문자열을 파싱한다. YYYY-MM-DD 또는 YYYY.MM.DD 등 지원."""
    date_str = date_str.strip()
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y년 %m월 %d일"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def count_business_days(start: date, end: date) -> int:
    """두 날짜 사이의 영업일(월~금)을 계산한다. start와 end 모두 포함하지 않음."""
    if end <= start:
        return 0
    days = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() < 5:  # 월(0)~금(4)
            days += 1
        current += timedelta(days=1)
    return days


def find_matching_type(product_type: str) -> tuple[str, int | None] | None:
    """입력된 제작물 유형에서 납기 기준 매칭을 찾는다."""
    product_type_lower = product_type.lower().strip()
    for type_name, days in DEADLINE_FLAT.items():
        if type_name.lower() in product_type_lower or product_type_lower in type_name.lower():
            return (type_name, days)
    # 부분 매칭 시도
    keywords = {
        "배너": ("배너 이미지", DEADLINE_FLAT.get("배너 이미지")),
        "상세": ("상세페이지 이미지", DEADLINE_FLAT.get("상세페이지 이미지")),
        "리플렛": ("리플렛", DEADLINE_FLAT.get("리플렛")),
        "리플릿": ("리플렛", DEADLINE_FLAT.get("리플렛")),
        "전단": ("리플렛", DEADLINE_FLAT.get("리플렛")),  # 전단지 ≈ 리플렛 기준
        "x배너": ("X배너", DEADLINE_FLAT.get("X배너")),
        "패키지": ("패키지", DEADLINE_FLAT.get("패키지")),
        "브랜딩": ("브랜딩", DEADLINE_FLAT.get("브랜딩")),
    }
    for kw, (matched_type, matched_days) in keywords.items():
        if kw in product_type_lower:
            return (matched_type, matched_days)
    return None


def validate_deadline(
    product_type: str,
    desired_date_str: str,
    today: date | None = None,
) -> dict:
    """납기 기준을 검증한다.

    Args:
        product_type: 제작물 유형 (기획서에서 추출)
        desired_date_str: 희망 납기일 문자열
        today: 기준일 (기본: 오늘)

    Returns:
        {status, message, type_matched, min_days, business_days, desired_date}
    """
    if today is None:
        today = date.today()

    desired_date = parse_date(desired_date_str)
    if not desired_date:
        return {
            "status": STATUS_WARN,
            "message": f"희망 납기일을 파싱할 수 없습니다: '{desired_date_str}'. YYYY-MM-DD 형식으로 작성해주세요.",
            "type_matched": None,
            "min_days": None,
            "business_days": None,
            "desired_date": desired_date_str,
        }

    match = find_matching_type(product_type)
    if not match:
        return {
            "status": STATUS_WARN,
            "message": (
                f"제작물 유형 '{product_type}'에 해당하는 납기 기준을 찾을 수 없습니다. "
                "수동으로 확인해주세요."
            ),
            "type_matched": None,
            "min_days": None,
            "business_days": count_business_days(today, desired_date),
            "desired_date": desired_date.isoformat(),
        }

    type_name, min_days = match

    if min_days is None:
        return {
            "status": STATUS_WARN,
            "message": (
                f"'{type_name}'은(는) 업무범위가 광범위하여 사전 소통 후 일정을 조율해야 합니다. "
                "디자인센터와 사전 협의해주세요."
            ),
            "type_matched": type_name,
            "min_days": None,
            "business_days": count_business_days(today, desired_date),
            "desired_date": desired_date.isoformat(),
        }

    biz_days = count_business_days(today, desired_date)

    if biz_days >= min_days:
        return {
            "status": STATUS_PASS,
            "message": (
                f"납기 충족: {type_name} 기준 최소 {min_days}영업일 필요, "
                f"희망 납기까지 {biz_days}영업일 남음"
            ),
            "type_matched": type_name,
            "min_days": min_days,
            "business_days": biz_days,
            "desired_date": desired_date.isoformat(),
        }
    else:
        return {
            "status": STATUS_FAIL,
            "message": (
                f"납기 미충족: {type_name} 기준 최소 {min_days}영업일 필요하나 "
                f"희망 납기까지 {biz_days}영업일밖에 남지 않았습니다. "
                "디자인센터와 사전 협의가 필요합니다."
            ),
            "type_matched": type_name,
            "min_days": min_days,
            "business_days": biz_days,
            "desired_date": desired_date.isoformat(),
        }
