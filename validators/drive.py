"""Google Drive 폴더 검증 모듈"""

from __future__ import annotations

import json
import io
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import FOLDER_NAME_PATTERN, STATUS_FAIL, STATUS_PASS, STATUS_WARN


@dataclass
class DriveFile:
    """Drive 파일 메타데이터"""
    id: str
    name: str
    mime_type: str
    size: int = 0


@dataclass
class DriveValidationResult:
    """Drive 검증 결과"""
    folder_name: str = ""
    folder_name_status: str = STATUS_FAIL
    folder_name_message: str = ""
    service_account_email: str = ""
    pptx_file: DriveFile | None = None
    pptx_status: str = STATUS_FAIL
    pptx_message: str = ""
    image_files: list[DriveFile] = field(default_factory=list)
    all_files: list[DriveFile] = field(default_factory=list)
    asset_status: str = STATUS_WARN
    asset_message: str = ""
    local_pptx_path: str | None = None


def extract_folder_id(url: str) -> str | None:
    """Google Drive 폴더 URL에서 folder ID를 추출한다."""
    patterns = [
        r"folders/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_drive_service():
    """Google Drive API 서비스 객체를 생성한다.

    인증 방법 (우선순위):
    1. Streamlit Secrets (st.secrets["gcp_service_account"]) — Cloud 배포용
    2. 환경변수 GOOGLE_SERVICE_ACCOUNT_KEY (JSON 파일 경로) — 로컬용

    Returns:
        (service, client_email) 튜플
    """
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            creds = service_account.Credentials.from_service_account_info(
                info,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            return build("drive", "v3", credentials=creds), info.get("client_email", "알 수 없음")
    except Exception:
        pass

    # 로컬: 환경변수에서 JSON 파일 경로 읽기
    key_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY", "")
    if key_path and Path(key_path).exists():
        with open(key_path) as f:
            info = json.load(f)
        creds = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        return build("drive", "v3", credentials=creds), info.get("client_email", "알 수 없음")

    raise FileNotFoundError(
        "Google Drive 서비스 계정이 설정되지 않았습니다.\n\n"
        "**Streamlit Cloud:** Settings → Secrets에 gcp_service_account를 추가하세요.\n"
        "**로컬:** .env에 GOOGLE_SERVICE_ACCOUNT_KEY=경로를 설정하세요."
    )


def list_files_in_folder(service, folder_id: str) -> list[DriveFile]:
    """폴더 내 파일 목록을 조회한다."""
    query = f"'{folder_id}' in parents and trashed = false"
    results = (
        service.files()
        .list(
            q=query,
            fields="files(id, name, mimeType, size)",
            pageSize=100,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    files = []
    for f in results.get("files", []):
        files.append(
            DriveFile(
                id=f["id"],
                name=f["name"],
                mime_type=f["mimeType"],
                size=int(f.get("size", 0)),
            )
        )
    return files


def get_folder_name(service, folder_id: str) -> str:
    """폴더명을 조회한다."""
    result = service.files().get(fileId=folder_id, fields="name", supportsAllDrives=True).execute()
    return result.get("name", "")


def download_file(service, file_id: str, dest_path: str) -> str:
    """Drive 파일을 로컬에 다운로드한다."""
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


# Google Slides를 pptx로 내보내기
def export_google_slides(service, file_id: str, dest_path: str) -> str:
    """Google Slides 파일을 pptx로 내보내기한다."""
    request = service.files().export_media(
        fileId=file_id,
        mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    with open(dest_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


IMAGE_MIME_PREFIXES = ("image/",)
PPTX_MIME_TYPES = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.google-apps.presentation",
)


def validate_drive_folder(folder_url: str) -> DriveValidationResult:
    """Google Drive 폴더를 검증한다.

    1. 폴더명 규칙 확인
    2. 기획서 PPT 존재 여부
    3. 이미지/자료 파일 존재 여부
    4. PPT 다운로드
    """
    result = DriveValidationResult()

    folder_id = extract_folder_id(folder_url)
    if not folder_id:
        result.folder_name_status = STATUS_FAIL
        result.folder_name_message = "올바른 Google Drive 폴더 URL이 아닙니다."
        return result

    service, result.service_account_email = get_drive_service()

    # 폴더명 검증
    result.folder_name = get_folder_name(service, folder_id)
    if FOLDER_NAME_PATTERN.match(result.folder_name):
        result.folder_name_status = STATUS_PASS
        result.folder_name_message = f"폴더명 규칙 충족: {result.folder_name}"
    else:
        result.folder_name_status = STATUS_FAIL
        result.folder_name_message = (
            f"폴더명 규칙 미충족: '{result.folder_name}'\n"
            "→ 올바른 형식: 260000_프로젝트명_담당자"
        )

    # 파일 목록 조회
    files = list_files_in_folder(service, folder_id)
    result.all_files = files

    # 기획서 PPT 찾기
    pptx_files = [
        f for f in files
        if f.mime_type in PPTX_MIME_TYPES
        or f.name.lower().endswith(".pptx")
    ]

    if not pptx_files:
        result.pptx_status = STATUS_FAIL
        result.pptx_message = "기획서 PPT 파일이 없습니다. 기획서 템플릿을 사본 떠서 작성해주세요."
    elif len(pptx_files) > 1:
        result.pptx_status = STATUS_WARN
        result.pptx_message = (
            f"PPT 파일이 {len(pptx_files)}개 발견되었습니다. "
            f"첫 번째 파일({pptx_files[0].name})을 기획서로 간주합니다."
        )
        result.pptx_file = pptx_files[0]
    else:
        result.pptx_status = STATUS_PASS
        result.pptx_message = f"기획서 발견: {pptx_files[0].name}"
        result.pptx_file = pptx_files[0]

    # 이미지 파일 분류
    result.image_files = [
        f for f in files if any(f.mime_type.startswith(p) for p in IMAGE_MIME_PREFIXES)
    ]

    if result.image_files:
        result.asset_status = STATUS_PASS
        result.asset_message = f"이미지/자료 파일 {len(result.image_files)}개 발견"
    else:
        result.asset_status = STATUS_WARN
        result.asset_message = "이미지/자료 파일이 없습니다. 필요한 자료가 모두 업로드되었는지 확인해주세요."

    # PPT 다운로드
    if result.pptx_file:
        tmp_dir = tempfile.mkdtemp(prefix="drv_")
        dest = os.path.join(tmp_dir, result.pptx_file.name)
        if not dest.lower().endswith(".pptx"):
            dest += ".pptx"

        if result.pptx_file.mime_type == "application/vnd.google-apps.presentation":
            export_google_slides(service, result.pptx_file.id, dest)
        else:
            download_file(service, result.pptx_file.id, dest)
        result.local_pptx_path = dest

    return result
