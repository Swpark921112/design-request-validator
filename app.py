"""기획서 검증 앱 — 디자인 업무요청 기획서 자동 검증 도구

로컬 프로젝트 폴더(기획서 PPT + 자료 파일)를 업로드하면
가이드 기준에 맞는지 자동으로 검증합니다.
검증 통과 후 Google Drive에 업로드하세요.
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
    .upload-guide { background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 1rem; margin: 0.5rem 0; }
    .next-step { background: #ecfdf5; border: 1px solid #6ee7b7; border-radius: 8px; padding: 1.2rem; margin-top: 1rem; }
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
st.caption("프로젝트 폴더의 파일들을 업로드하면 기획서와 자료를 자동으로 검증합니다. 검증 통과 후 Google Drive에 업로드하세요.")

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
    - 폴더명 규칙
    - 기획서 PPT 필수 필드
    - 자료 품질 (해상도, 형식)
    - 납기 기준 충족 여부
    - 체크리스트 16개 항목
    """)
    st.divider()
    st.markdown("""
    **사용 흐름:**
    1. 로컬에서 폴더 준비
    2. 여기서 파일 업로드 & 검증
    3. 통과하면 Drive에 업로드
    4. 워크플로 실행
    """)

# ── 입력 영역 ──────────────────────────────────────────────
st.divider()

st.markdown('<div class="upload-guide">', unsafe_allow_html=True)
st.markdown("""
**📁 프로젝트 폴더 파일을 업로드해주세요**

로컬에 준비한 프로젝트 폴더 안의 파일들을 아래에 업로드합니다.
- **기획서 PPT** (필수) — 기획서 템플릿 사본
- **이미지/자료 파일** (선택) — 제품사진, 로고, 참고자료 등
""")
st.markdown('</div>', unsafe_allow_html=True)

folder_name = st.text_input(
    "프로젝트 폴더명",
    placeholder="260000_프로젝트명_담당자 (예: 260000_총명공진단샘플링_박윤희)",
    help="Drive에 생성할 폴더명을 입력하세요. 규칙: 260000_프로젝트명_담당자",
)

uploaded_pptx = st.file_uploader("기획서 PPT 파일 (필수)", type=["pptx"])

uploaded_assets = st.file_uploader(
    "이미지/자료 파일 (선택 — 여러 파일 가능)",
    type=["png", "jpg", "jpeg", "tif", "tiff", "ai", "psd", "svg", "pdf"],
    accept_multiple_files=True,
)

# ── 검증 실행 ──────────────────────────────────────────────
run_btn = st.button("🔍 검증 시작", type="primary", use_container_width=True)

if run_btn:
    if not uploaded_pptx:
        st.warning("기획서 PPT 파일을 업로드해주세요.")
        st.stop()

    with st.spinner("검증 중..."):
        # 임시 디렉토리에 파일 저장
        tmp_dir = tempfile.mkdtemp(prefix="validator_")
        pptx_path = os.path.join(tmp_dir, uploaded_pptx.name)
        with open(pptx_path, "wb") as f:
            f.write(uploaded_pptx.read())

        image_paths = []
        image_names = []
        if uploaded_assets:
            for asset in uploaded_assets:
                asset_path = os.path.join(tmp_dir, asset.name)
                with open(asset_path, "wb") as f:
                    f.write(asset.read())
                image_paths.append(asset_path)
                image_names.append(asset.name)

        # ── 1. 폴더명 검증 ───────────────────────────────
        folder_name_status = STATUS_FAIL
        folder_name_message = ""
        if not folder_name:
            folder_name_status = STATUS_FAIL
            folder_name_message = "폴더명을 입력해주세요. (규칙: 260000_프로젝트명_담당자)"
        elif FOLDER_NAME_PATTERN.match(folder_name):
            folder_name_status = STATUS_PASS
            folder_name_message = f"폴더명 규칙 충족: {folder_name}"
        else:
            folder_name_status = STATUS_FAIL
            folder_name_message = (
                f"폴더명 규칙 미충족: '{folder_name}'\n"
                "→ 올바른 형식: 260000_프로젝트명_담당자"
            )

        # ── 2. PPT 파싱 ──────────────────────────────────
        parsed_pptx = parse_pptx(pptx_path)
        field_results = check_required_fields(parsed_pptx)

        # ── 3. 자료 품질 검증 ────────────────────────────
        asset_results = []
        if image_paths:
            asset_results = validate_assets(
                image_file_paths=image_paths,
                image_filenames=image_names,
                media_type=media_type,
            )

        # ── 4. 납기 검증 ────────────────────────────────
        deadline_result = None
        info_slide = parsed_pptx.slides.get("기본정보")
        detail_slide = parsed_pptx.slides.get("제작물상세")

        product_type = ""
        desired_date = ""

        if detail_slide:
            for key, val in detail_slide.fields.items():
                if "제작물" in key and "유형" in key:
                    product_type = val
                    break
            if not product_type:
                for card in detail_slide.cards:
                    if "제작물" in card.label and "유형" in card.label:
                        product_type = card.value
                        break

        if info_slide:
            for key, val in info_slide.fields.items():
                if "납기" in key:
                    desired_date = val
                    break
            if not desired_date:
                for card in info_slide.cards:
                    if "납기" in card.label:
                        desired_date = card.value
                        break

        if product_type and desired_date:
            deadline_result = validate_deadline(product_type, desired_date)

        # ── 5. 체크리스트 종합 ───────────────────────────
        # checklist에 전달할 간이 결과 객체
        from dataclasses import dataclass, field as dc_field

        @dataclass
        class LocalResult:
            folder_name: str = ""
            folder_name_status: str = STATUS_FAIL
            folder_name_message: str = ""
            pptx_status: str = STATUS_PASS
            pptx_message: str = ""
            asset_status: str = STATUS_WARN
            asset_message: str = ""
            image_files: list = dc_field(default_factory=list)
            all_files: list = dc_field(default_factory=list)

        local_result = LocalResult(
            folder_name=folder_name or "(미입력)",
            folder_name_status=folder_name_status,
            folder_name_message=folder_name_message,
            pptx_status=STATUS_PASS,
            pptx_message=f"기획서: {uploaded_pptx.name}",
            asset_status=STATUS_PASS if uploaded_assets else STATUS_WARN,
            asset_message=f"자료 파일 {len(uploaded_assets)}개" if uploaded_assets else "자료 파일 없음",
        )

        checklist_items = validate_checklist(
            drive_result=local_result,
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

    # 접수 가능 시 다음 단계 안내
    if verdict == VERDICT_ACCEPT:
        st.markdown("""
        <div class="next-step">
        <strong>🎉 검증을 통과했습니다! 다음 단계를 진행하세요:</strong><br><br>
        1. <a href="https://drive.google.com/drive/folders/10b-tIKBGh7_2J3eTbEkAFO6Dh_nc-yEn" target="_blank">디자인센터 업무요청 Drive</a>에 프로젝트 폴더를 생성하세요<br>
        2. 검증한 기획서와 자료 파일을 폴더에 업로드하세요<br>
        3. 워크플로를 실행하여 업무를 접수하세요
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ── 체크리스트 상세 ───────────────────────────────────
    st.subheader("📝 체크리스트 검증 상세")

    categories = ["기본", "문구", "자료", "제작물"]
    for cat in categories:
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

    # ── 업로드된 파일 목록 ────────────────────────────────
    st.divider()
    st.subheader("📁 업로드된 파일 목록")
    st.text(f"  📄 {uploaded_pptx.name} (기획서)")
    if uploaded_assets:
        for asset in uploaded_assets:
            st.text(f"  🖼️ {asset.name}")
    else:
        st.caption("  (자료 파일 없음)")
