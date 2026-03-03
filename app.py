"""기획서 검증 앱 — 디자인 업무요청 기획서 자동 검증 도구

Google Drive 폴더 URL을 입력하면
기획서 PPT + 자료 파일을 자동으로 검증합니다.
"""

from __future__ import annotations

import os
import sys
import tempfile

import streamlit as st

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(__file__))

from config import (
    FOLDER_NAME_PATTERN,
    STATUS_EMOJI,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    VERDICT_ACCEPT,
    VERDICT_REJECT,
    VERDICT_SUPPLEMENT,
)
from validators.asset_quality import validate_assets
from validators.checklist import CheckItem, validate_checklist
from validators.deadline import validate_deadline
from validators.drive import validate_drive_folder
from validators.pptx_parser import check_required_fields, parse_pptx

# ── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(
    page_title="기획서 검증기",
    page_icon="📋",
    layout="wide",
)

# ── 커스텀 CSS ─────────────────────────────────────────────
st.markdown("""
<style>
    .verdict-accept { background: #dcfce7; color: #166534; padding: 1rem; border-radius: 8px; text-align: center; font-size: 1.5rem; font-weight: 700; }
    .verdict-supplement { background: #fef3c7; color: #92400e; padding: 1rem; border-radius: 8px; text-align: center; font-size: 1.5rem; font-weight: 700; }
    .verdict-reject { background: #fecaca; color: #991b1b; padding: 1rem; border-radius: 8px; text-align: center; font-size: 1.5rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


def render_status(status: str) -> str:
    return STATUS_EMOJI.get(status, "❓")


def compute_verdict(items: list[CheckItem]) -> str:
    fail_count = sum(1 for i in items if i.status == STATUS_FAIL)
    warn_count = sum(1 for i in items if i.status == STATUS_WARN)
    if fail_count > 0:
        return VERDICT_REJECT
    if warn_count > 3:
        return VERDICT_SUPPLEMENT
    return VERDICT_ACCEPT


def render_verdict(verdict: str):
    if verdict == VERDICT_ACCEPT:
        st.markdown(f'<div class="verdict-accept">✅ {verdict}</div>', unsafe_allow_html=True)
    elif verdict == VERDICT_SUPPLEMENT:
        st.markdown(f'<div class="verdict-supplement">⚠️ {verdict}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="verdict-reject">❌ {verdict}</div>', unsafe_allow_html=True)


# ── 메인 앱 ────────────────────────────────────────────────
st.title("📋 디자인 업무요청 기획서 검증기")
st.caption("Google Drive 폴더 URL을 입력하면 기획서와 자료를 자동으로 검증합니다.")

# 사이드바
with st.sidebar:
    st.header("설정")
    media_type = st.selectbox(
        "제작물 용도",
        ["print", "web"],
        format_func=lambda x: "인쇄물 (300dpi 기준)" if x == "print" else "웹용 (72dpi 기준)",
    )
    st.divider()
    st.markdown("""
    **검증 항목:**
    - 폴더명 규칙 (`260000_프로젝트명_담당자`)
    - 기획서 PPT 존재 여부
    - PPT 필수 필드 작성 여부
    - 자료 파일 품질 (형식, 파일명)
    - 납기 기준 충족 여부
    - 체크리스트 16개 항목
    """)
    st.divider()
    st.markdown("""
    **사용 흐름:**
    1. Drive에 폴더 생성 & 기획서 작성
    2. 자료 파일 업로드
    3. **이 앱에서 폴더 URL 입력 → 검증**
    4. 통과하면 워크플로 실행
    """)

# ── 입력 영역 ──────────────────────────────────────────────
st.divider()

folder_url = st.text_input(
    "🔗 Google Drive 프로젝트 폴더 URL",
    placeholder="https://drive.google.com/drive/folders/...",
    help="디자인센터 업무요청 Drive에 생성한 프로젝트 폴더 URL을 붙여넣으세요.",
)

run_btn = st.button("🔍 검증 시작", type="primary", use_container_width=True)

if run_btn:
    if not folder_url:
        st.warning("Google Drive 폴더 URL을 입력해주세요.")
        st.stop()

    # ── 1. Drive 폴더 검증 ───────────────────────────────
    with st.spinner("Google Drive 폴더를 확인하는 중..."):
        try:
            drive_result = validate_drive_folder(folder_url)
        except FileNotFoundError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"Drive 접근 오류: {e}")
            # 디버그: 서비스 계정 이메일 표시
            try:
                from validators.drive import get_drive_service
                _, email = get_drive_service()
                st.info(f"현재 인증된 서비스 계정: **{email}**\n\n이 이메일이 Drive 폴더에 **뷰어**로 공유되어 있는지 확인하세요.")
            except Exception:
                st.warning("서비스 계정 인증 자체가 실패했습니다. Secrets 설정을 확인하세요.")
            st.stop()

    # ── 2. PPT 파싱 ──────────────────────────────────────
    parsed_pptx = None
    field_results = []
    if drive_result.local_pptx_path:
        with st.spinner("기획서 PPT를 분석하는 중..."):
            parsed_pptx = parse_pptx(drive_result.local_pptx_path)
            field_results = check_required_fields(parsed_pptx)

    # ── 3. 자료 품질 검증 ────────────────────────────────
    asset_results = []
    image_names = [f.name for f in drive_result.image_files]
    if image_names:
        asset_results = validate_assets(
            image_filenames=image_names,
            media_type=media_type,
        )

    # ── 4. 납기 검증 ────────────────────────────────────
    deadline_result = None
    if parsed_pptx:
        info_slide = parsed_pptx.slides.get("기본정보")
        detail_slide = parsed_pptx.slides.get("제작물상세")

        product_type = ""
        desired_date = ""

        if detail_slide:
            for card in detail_slide.cards:
                if "제작물" in card.label and "유형" in card.label:
                    product_type = card.value
                    break

        if info_slide:
            for card in info_slide.cards:
                if "납기" in card.label:
                    desired_date = card.value
                    break

        if product_type and desired_date:
            deadline_result = validate_deadline(product_type, desired_date)

    # ── 5. 체크리스트 종합 ───────────────────────────────
    checklist_items = validate_checklist(
        drive_result=drive_result,
        parsed_pptx=parsed_pptx,
        field_results=field_results,
        asset_results=asset_results,
        deadline_result=deadline_result,
    )

    # ── 결과 출력 ─────────────────────────────────────────
    st.divider()
    st.header("검증 결과")

    verdict = compute_verdict(checklist_items)
    render_verdict(verdict)

    # 통계
    col1, col2, col3 = st.columns(3)
    pass_count = sum(1 for i in checklist_items if i.status == STATUS_PASS)
    warn_count = sum(1 for i in checklist_items if i.status == STATUS_WARN)
    fail_count = sum(1 for i in checklist_items if i.status == STATUS_FAIL)
    col1.metric("✅ 통과", pass_count)
    col2.metric("⚠️ 경고", warn_count)
    col3.metric("❌ 실패", fail_count)

    if verdict == VERDICT_ACCEPT:
        st.success("검증을 통과했습니다! 워크플로를 실행하여 업무를 접수하세요.")

    st.divider()

    # ── 체크리스트 상세 ───────────────────────────────────
    st.subheader("📝 체크리스트 검증 상세")

    for cat in ["기본", "문구", "자료", "제작물"]:
        cat_items = [i for i in checklist_items if i.category == cat]
        if not cat_items:
            continue
        with st.expander(f"**{cat}** ({sum(1 for i in cat_items if i.status == STATUS_PASS)}/{len(cat_items)} 통과)", expanded=True):
            for item in cat_items:
                emoji = render_status(item.status)
                auto_tag = "" if item.auto else " `수동확인`"
                st.markdown(f"{emoji} **{item.item}**{auto_tag}")
                st.caption(f"  └ {item.message}")

    # ── PPT 필수 필드 상세 ────────────────────────────────
    if field_results:
        st.divider()
        st.subheader("📄 기획서 PPT 필수 필드")
        for fr in field_results:
            emoji = "✅" if fr["status"] == "pass" else "❌"
            val_display = f": {fr['value'][:50]}" if fr.get("value") and fr["status"] == "pass" else ""
            st.markdown(f"{emoji} **[{fr['slide']}]** {fr['field']}{val_display}")
            if fr["status"] != "pass":
                st.caption(f"  └ {fr['message']}")

    # ── 자료 품질 상세 ────────────────────────────────────
    if asset_results:
        st.divider()
        st.subheader("🖼️ 자료 품질 검증")
        for ar in asset_results:
            emoji = render_status(ar["status"])
            st.markdown(f"{emoji} **{ar['file']}** — {ar['message']}")

    # ── 납기 검증 상세 ────────────────────────────────────
    if deadline_result:
        st.divider()
        st.subheader("📅 납기 기준 검증")
        emoji = render_status(deadline_result["status"])
        st.markdown(f"{emoji} {deadline_result['message']}")
        if deadline_result.get("business_days") is not None:
            st.info(f"희망 납기까지 **{deadline_result['business_days']}영업일** 남음")

    # ── 폴더 내 파일 목록 ────────────────────────────────
    if drive_result.all_files:
        st.divider()
        st.subheader("📁 Drive 폴더 내 파일 목록")
        for f in drive_result.all_files:
            icon = "📄" if "presentation" in f.mime_type else "🖼️" if f.mime_type.startswith("image/") else "📎"
            st.text(f"  {icon} {f.name}")
