"""AI 기반 문구 검수 모듈 (Claude API)

PPT에서 추출한 문구를 교정교열하고 브랜드명, 법적 표기 등을 검수한다.
"""

from __future__ import annotations

import json
import os

import anthropic

REVIEW_SYSTEM_PROMPT = """당신은 한국어 문구 교정교열 전문가이자 디자인 제작물 검수 담당자입니다.
아래 디자인 기획서에서 추출한 문구를 검수하여 문제점을 JSON 형식으로 보고해주세요.

검수 항목:
1. **오탈자/문법**: 오탈자, 글자 누락, 띄어쓰기 오류, 조사 누락
2. **보조용언 일관성**: "준비해주셔서" vs "제공해 줍니다" 등 띄어쓰기 일관성
3. **브랜드명 표기**: 같은 브랜드/상품명이 다르게 표기된 경우 (예: "수멤버스" vs "수 멤버스")
4. **한의학 용어**: 한의학 용어, 한자, 약재명, 처방 구성의 정확성
5. **법적 필수표기**: 식약처 문구, 인증마크 관련 문구, 주의사항 등의 누락 여부
6. **정식 명칭**: 상품/경품/브랜드의 약칭 사용 여부

반드시 아래 JSON 형식으로만 응답해주세요:
{
  "issues": [
    {
      "category": "오탈자" | "보조용언" | "브랜드명" | "한의학용어" | "법적표기" | "정식명칭",
      "severity": "error" | "warning" | "info",
      "original": "원본 텍스트",
      "suggestion": "수정 제안",
      "explanation": "설명"
    }
  ],
  "summary": {
    "total_issues": 0,
    "errors": 0,
    "warnings": 0,
    "overall_quality": "양호" | "보통" | "수정필요"
  }
}"""


def review_text(text: str) -> dict | None:
    """Claude API로 문구를 검수한다.

    Args:
        text: 검수할 전체 문구

    Returns:
        검수 결과 딕셔너리 또는 None (API 키 미설정 시)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)

    user_message = f"""아래는 디자인 제작물 기획서에서 추출한 문구입니다. 검수해주세요.

---
{text}
---

위 문구에 대해 오탈자, 문법, 브랜드명 표기, 법적 표기 등을 검수하여 JSON으로 응답해주세요."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=REVIEW_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    # 응답에서 JSON 추출
    response_text = response.content[0].text.strip()

    # JSON 블록 추출 (코드 블록 안에 있을 수 있음)
    if "```json" in response_text:
        start = response_text.index("```json") + 7
        end = response_text.index("```", start)
        response_text = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.index("```") + 3
        end = response_text.index("```", start)
        response_text = response_text[start:end].strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        return {
            "issues": [],
            "summary": {
                "total_issues": 0,
                "errors": 0,
                "warnings": 0,
                "overall_quality": "파싱 실패",
            },
            "raw_response": response_text,
        }
