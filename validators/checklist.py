"""체크리스트 항목 검증 모듈

MD 가이드 섹션 10 기반 16개 항목을 자동 검증한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config import STATUS_FAIL, STATUS_PASS, STATUS_WARN
from validators.pptx_parser import ParsedPPTX


@dataclass
class CheckItem:
    """체크리스트 검증 항목"""
    category: str      # 기본 / 문구 / 자료 / 제작물
    item: str          # 항목 설명
    status: str        # pass / warn / fail
    message: str       # 상세 메시지
    auto: bool = True  # 자동 판별 가능 여부


def validate_checklist(
    drive_result: Any,
    parsed_pptx: ParsedPPTX | None,
    field_results: list[dict] | None = None,
    asset_results: list[dict] | None = None,
    deadline_result: dict | None = None,
) -> list[CheckItem]:
    """전체 체크리스트를 검증한다.

    Args:
        drive_result: Drive 폴더 검증 결과
        parsed_pptx: 파싱된 PPT 기획서
        field_results: PPT 필수 필드 검증 결과
        asset_results: 자료 품질 검증 결과
        deadline_result: 납기 검증 결과
    """
    items: list[CheckItem] = []

    # ── 기본 (6항목) ────────────────────────────────────
    # 1. 폴더 생성
    items.append(CheckItem(
        category="기본",
        item="업무요청 Drive에 프로젝트 폴더를 생성했는가?",
        status=drive_result.folder_name_status,
        message=drive_result.folder_name_message or "Drive 폴더가 존재합니다.",
    ))

    # 2. 기획서 템플릿 사본
    items.append(CheckItem(
        category="기본",
        item="기획서 템플릿을 사본 떠서 기획서를 작성했는가?",
        status=drive_result.pptx_status,
        message=drive_result.pptx_message,
    ))

    # 3. 관련 자료 정리
    items.append(CheckItem(
        category="기본",
        item="관련 자료(이미지, 로고, 참고자료)를 같은 폴더에 정리했는가?",
        status=drive_result.asset_status,
        message=drive_result.asset_message,
    ))

    # 4. 워크플로 접수 준비
    # 이 항목은 앱에서 자동 판별 불가 → 항상 경고로 안내
    items.append(CheckItem(
        category="기본",
        item="워크플로를 통해 접수할 준비가 되었는가?",
        status=STATUS_WARN,
        message="워크플로 접수 여부는 자동 확인할 수 없습니다. 직접 확인해주세요.",
        auto=False,
    ))

    # 5. 최종 컨펌자
    has_confirmer = False
    if field_results:
        for fr in field_results:
            if "최종 컨펌자" in fr.get("field", "") and fr["status"] == "pass":
                has_confirmer = True
                break
    items.append(CheckItem(
        category="기본",
        item="최종 컨펌자 1인을 지정했는가?",
        status=STATUS_PASS if has_confirmer else STATUS_FAIL,
        message="최종 컨펌자가 지정되어 있습니다." if has_confirmer else "기획서에 최종 컨펌자가 지정되지 않았습니다.",
    ))

    # 6. 납기일 충족
    if deadline_result:
        items.append(CheckItem(
            category="기본",
            item="납기일은 최소 소요일을 충족하는가?",
            status=deadline_result.get("status", STATUS_WARN),
            message=deadline_result.get("message", "납기 검증 결과를 확인해주세요."),
        ))
    else:
        items.append(CheckItem(
            category="기본",
            item="납기일은 최소 소요일을 충족하는가?",
            status=STATUS_WARN,
            message="납기 검증이 수행되지 않았습니다.",
            auto=False,
        ))

    # ── 문구 (3항목) ────────────────────────────────────
    # AI 검수 결과가 있으면 반영, 없으면 수동 확인 안내
    items.append(CheckItem(
        category="문구",
        item="문구는 교정교열을 완료한 최종 확정 상태인가?",
        status=STATUS_WARN,
        message="AI 문구 검수 결과를 확인해주세요. (별도 AI 검수 섹션 참조)",
        auto=False,
    ))

    items.append(CheckItem(
        category="문구",
        item="상품/경품/브랜드명은 정식 명칭으로 기재했는가?",
        status=STATUS_WARN,
        message="AI 문구 검수 결과를 확인해주세요. (별도 AI 검수 섹션 참조)",
        auto=False,
    ))

    items.append(CheckItem(
        category="문구",
        item="법적 필수표기(식약처 문구, 인증마크 등)를 확인했는가?",
        status=STATUS_WARN,
        message="AI 문구 검수 결과를 확인해주세요. (별도 AI 검수 섹션 참조)",
        auto=False,
    ))

    # ── 자료 (3항목) ────────────────────────────────────
    if asset_results:
        # 이미지 품질
        quality_fails = [r for r in asset_results if r.get("status") == STATUS_FAIL]
        if quality_fails:
            items.append(CheckItem(
                category="자료",
                item="이미지/로고 자료는 품질 기준에 맞게 Drive에 업로드했는가?",
                status=STATUS_FAIL,
                message=f"품질 미달 파일 {len(quality_fails)}개 발견. 상세 내용은 자료 품질 검증 섹션 참조.",
            ))
        else:
            items.append(CheckItem(
                category="자료",
                item="이미지/로고 자료는 품질 기준에 맞게 Drive에 업로드했는가?",
                status=STATUS_PASS,
                message="모든 이미지 파일이 품질 기준을 충족합니다.",
            ))

        # 파일명 규칙
        name_warns = [r for r in asset_results if r.get("type") == "filename" and r.get("status") != STATUS_PASS]
        if name_warns:
            items.append(CheckItem(
                category="자료",
                item="파일명은 내용을 알 수 있게 정리했는가?",
                status=STATUS_WARN,
                message=f"파일명 규칙 경고 {len(name_warns)}건. 상세 내용은 자료 품질 검증 섹션 참조.",
            ))
        else:
            items.append(CheckItem(
                category="자료",
                item="파일명은 내용을 알 수 있게 정리했는가?",
                status=STATUS_PASS,
                message="파일명이 적절하게 작성되어 있습니다.",
            ))
    else:
        items.append(CheckItem(
            category="자료",
            item="이미지/로고 자료는 품질 기준에 맞게 Drive에 업로드했는가?",
            status=STATUS_WARN,
            message="자료 품질 검증이 수행되지 않았습니다.",
            auto=False,
        ))
        items.append(CheckItem(
            category="자료",
            item="파일명은 내용을 알 수 있게 정리했는가?",
            status=STATUS_WARN,
            message="자료 품질 검증이 수행되지 않았습니다.",
            auto=False,
        ))

    # 특수 작업 도구
    has_tool = False
    if field_results:
        for fr in field_results:
            if "작업 도구" in fr.get("field", "") or "작업도구" in fr.get("field", ""):
                has_tool = fr["status"] == "pass"
                break
    items.append(CheckItem(
        category="자료",
        item="특수 작업 도구(InDesign 등)가 필요한 경우 명시했는가?",
        status=STATUS_PASS if has_tool else STATUS_WARN,
        message="작업 도구가 명시되어 있습니다." if has_tool else "작업 도구 지정이 필요한 경우 기획서에 명시해주세요.",
    ))

    # ── 제작물 (4항목) ──────────────────────────────────
    # 사이즈/수량/형식
    size_ok = False
    if field_results:
        for fr in field_results:
            if fr.get("field") in ("사이즈", "수량", "파일 형식"):
                if fr["status"] == "pass":
                    size_ok = True
    items.append(CheckItem(
        category="제작물",
        item="제작물 사이즈, 수량, 파일 형식을 명시했는가?",
        status=STATUS_PASS if size_ok else STATUS_FAIL,
        message="사이즈/수량/파일 형식이 작성되어 있습니다." if size_ok else "기획서에 사이즈, 수량, 파일 형식을 작성해주세요.",
    ))

    # 인쇄 일정
    has_print_schedule = False
    if parsed_pptx:
        slide = parsed_pptx.slides.get("제작물상세")
        if slide:
            for key in slide.fields:
                if "인쇄" in key and ("일정" in key or "제작" in key):
                    has_print_schedule = bool(slide.fields[key].strip())
                    break
    items.append(CheckItem(
        category="제작물",
        item="인쇄물이라면 인쇄 일정과 발주처를 확인했는가?",
        status=STATUS_PASS if has_print_schedule else STATUS_WARN,
        message="인쇄 일정이 기재되어 있습니다." if has_print_schedule else "인쇄물인 경우 인쇄 일정과 발주처를 확인해주세요.",
    ))

    # 예상 단가 범위
    has_cost = False
    if field_results:
        for fr in field_results:
            if "예상 단가" in fr.get("field", "") and fr["status"] == "pass":
                has_cost = True
                break
    items.append(CheckItem(
        category="제작물",
        item="인쇄물/패키지라면 예상 단가 범위를 확인했는가?",
        status=STATUS_PASS if has_cost else STATUS_WARN,
        message="예상 단가 범위가 기재되어 있습니다." if has_cost else "인쇄물/패키지인 경우 예상 단가 범위를 기재해주세요.",
    ))

    # 패키지 규격
    has_package_spec = False
    if parsed_pptx:
        all_text = parsed_pptx.all_text.lower()
        if "가로" in all_text and "세로" in all_text and "높이" in all_text:
            has_package_spec = True
    items.append(CheckItem(
        category="제작물",
        item="패키지라면 규격(가로x세로x높이)과 적재 수량을 명시했는가?",
        status=STATUS_PASS if has_package_spec else STATUS_WARN,
        message="패키지 규격이 기재되어 있습니다." if has_package_spec else "패키지인 경우 규격(가로x세로x높이)과 적재 수량을 명시해주세요.",
    ))

    return items
