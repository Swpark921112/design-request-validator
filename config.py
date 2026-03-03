"""기획서 검증 앱 설정값"""

from __future__ import annotations

import re

# ── 납기 기준 (영업일) ──────────────────────────────────────
# None = 협의 필요 (자동 판정 불가)
DEADLINE_RULES: dict[str, dict[str, int | None]] = {
    "온라인": {
        "배너 이미지": 2,
        "상세페이지 이미지": 2,
    },
    "오프라인": {
        "리플렛": 14,
        "X배너": 7,
    },
    "기타": {
        "기존 데이터 간단 수정": 2,
        "제작 데이터 및 사양 변경": 2,
        "패키지": None,
        "브랜딩": None,
    },
}

# 제작물 유형 → 카테고리 역매핑 (플랫 딕셔너리)
DEADLINE_FLAT: dict[str, int | None] = {}
for _cat, _items in DEADLINE_RULES.items():
    for _type, _days in _items.items():
        DEADLINE_FLAT[_type] = _days

# ── 자료 품질 기준 ──────────────────────────────────────────
PRINT_MIN_DPI = 300
WEB_MIN_DPI = 72

ACCEPTED_IMAGE_FORMATS = {"png", "jpg", "jpeg", "ai", "psd", "svg", "pdf", "tif", "tiff"}
RECOMMENDED_FORMATS = {"png", "ai", "psd", "svg"}

# 반려 대상 파일명 패턴 (카톡 전달, 캡처 등)
REJECTED_FILENAME_PATTERNS = [
    re.compile(r"kakaotalk", re.IGNORECASE),
    re.compile(r"screenshot", re.IGNORECASE),
    re.compile(r"capture", re.IGNORECASE),
    re.compile(r"스크린샷", re.IGNORECASE),
    re.compile(r"캡처", re.IGNORECASE),
]

# ── 폴더명 규칙 ────────────────────────────────────────────
# 260000_프로젝트명_담당자
FOLDER_NAME_PATTERN = re.compile(r"^\d{6}_.+_.+$")

# ── PPT 슬라이드 매핑 ──────────────────────────────────────
# 0-indexed 슬라이드 번호
SLIDE_INDEX = {
    "표지": 0,
    "기본정보": 1,
    "제작물상세": 2,
    "콘텐츠1": 3,
    "콘텐츠2": 4,
    "참고": 5,
    "체크리스트": 6,
}

# 슬라이드별 필수 필드 (플레이스홀더 텍스트 기반 감지)
REQUIRED_FIELDS = {
    "기본정보": [
        "요청자",
        "최종 컨펌자",
        "프로젝트명",
        "희망 납기일",
        "사용 채널",
    ],
    "제작물상세": [
        "제작물 유형",
        "사이즈",
        "수량",
        "파일 형식",
        "예상 단가 범위",
    ],
}

# 플레이스홀더 감지 키워드 (이 텍스트가 그대로 남아있으면 미작성)
PLACEHOLDER_KEYWORDS = [
    "작성해주세요",
    "입력해주세요",
    "선택해주세요",
    "기재해주세요",
    "ex.",
    "예시",
    "여기에",
]

# ── 검증 결과 상태 ──────────────────────────────────────────
STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"

STATUS_EMOJI = {
    STATUS_PASS: "✅",
    STATUS_WARN: "⚠️",
    STATUS_FAIL: "❌",
}

# ── 종합 판정 기준 ──────────────────────────────────────────
VERDICT_ACCEPT = "접수 가능"
VERDICT_SUPPLEMENT = "보완 필요"
VERDICT_REJECT = "반려 예상"
