"""자료 품질 검증 모듈

이미지 해상도, 파일 형식, 파일명 규칙 등을 검증한다.
"""

from __future__ import annotations

import io
import os
import tempfile

from config import (
    ACCEPTED_IMAGE_FORMATS,
    PRINT_MIN_DPI,
    RECOMMENDED_FORMATS,
    REJECTED_FILENAME_PATTERNS,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARN,
    WEB_MIN_DPI,
)

try:
    from PIL import Image
except ImportError:
    Image = None


def check_image_dpi(file_path: str, media_type: str = "print") -> dict:
    """이미지 DPI를 검사한다.

    Args:
        file_path: 이미지 파일 경로
        media_type: "print" 또는 "web"
    """
    if Image is None:
        return {
            "type": "dpi",
            "file": os.path.basename(file_path),
            "status": STATUS_WARN,
            "message": "Pillow가 설치되지 않아 DPI 검사를 수행할 수 없습니다.",
        }

    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    # AI, PSD, SVG 등은 Pillow로 열 수 없음
    if ext not in ("png", "jpg", "jpeg", "tif", "tiff", "bmp", "gif", "webp"):
        return {
            "type": "dpi",
            "file": os.path.basename(file_path),
            "status": STATUS_PASS,
            "message": f".{ext} 파일은 DPI 검사 대상이 아닙니다.",
            "dpi": None,
        }

    try:
        with Image.open(file_path) as img:
            dpi_info = img.info.get("dpi", (72, 72))
            dpi = int(min(dpi_info[0], dpi_info[1]))
    except Exception as e:
        return {
            "type": "dpi",
            "file": os.path.basename(file_path),
            "status": STATUS_WARN,
            "message": f"DPI 확인 실패: {e}",
            "dpi": None,
        }

    min_dpi = PRINT_MIN_DPI if media_type == "print" else WEB_MIN_DPI
    if dpi >= min_dpi:
        return {
            "type": "dpi",
            "file": os.path.basename(file_path),
            "status": STATUS_PASS,
            "message": f"DPI: {dpi} (기준: {min_dpi}dpi 이상)",
            "dpi": dpi,
        }
    else:
        return {
            "type": "dpi",
            "file": os.path.basename(file_path),
            "status": STATUS_FAIL,
            "message": f"DPI 미달: {dpi}dpi (기준: {min_dpi}dpi 이상). 고해상도 원본을 업로드해주세요.",
            "dpi": dpi,
        }


def check_file_format(filename: str) -> dict:
    """파일 형식을 검사한다."""
    ext = os.path.splitext(filename)[1].lower().lstrip(".")

    if not ext:
        return {
            "type": "format",
            "file": filename,
            "status": STATUS_WARN,
            "message": "확장자가 없는 파일입니다.",
        }

    if ext in ACCEPTED_IMAGE_FORMATS:
        if ext in RECOMMENDED_FORMATS:
            return {
                "type": "format",
                "file": filename,
                "status": STATUS_PASS,
                "message": f".{ext} — 권장 형식",
            }
        return {
            "type": "format",
            "file": filename,
            "status": STATUS_PASS,
            "message": f".{ext} — 허용 형식",
        }
    else:
        return {
            "type": "format",
            "file": filename,
            "status": STATUS_WARN,
            "message": f".{ext} — 권장 형식이 아닙니다. PNG, AI, PSD, SVG 형식을 권장합니다.",
        }


def check_filename(filename: str) -> dict:
    """파일명이 반려 대상 패턴에 해당하는지 검사한다."""
    for pattern in REJECTED_FILENAME_PATTERNS:
        if pattern.search(filename):
            return {
                "type": "filename",
                "file": filename,
                "status": STATUS_FAIL,
                "message": f"반려 대상 파일명 패턴 감지: '{filename}'. 캡처/카톡 전달 이미지는 원본 파일로 교체해주세요.",
            }

    # 너무 짧거나 의미 없는 파일명 경고
    name_part = os.path.splitext(filename)[0]
    if len(name_part) <= 3 or name_part.startswith("IMG_") or name_part.startswith("image"):
        return {
            "type": "filename",
            "file": filename,
            "status": STATUS_WARN,
            "message": f"파일명이 내용을 식별하기 어렵습니다: '{filename}'. (예: 총명공진단_제품사진_정면.png)",
        }

    return {
        "type": "filename",
        "file": filename,
        "status": STATUS_PASS,
        "message": f"파일명 적절: '{filename}'",
    }


def validate_assets(
    image_file_paths: list[str] | None = None,
    image_filenames: list[str] | None = None,
    media_type: str = "print",
) -> list[dict]:
    """자료 파일들의 품질을 일괄 검증한다.

    Args:
        image_file_paths: 로컬에 다운로드된 이미지 파일 경로 목록 (DPI 검사용)
        image_filenames: Drive 내 이미지 파일명 목록 (파일명/형식 검사용)
        media_type: "print" 또는 "web"
    """
    results = []

    # 파일명 & 형식 검사 (Drive 파일명 기반)
    if image_filenames:
        for fname in image_filenames:
            results.append(check_filename(fname))
            results.append(check_file_format(fname))

    # DPI 검사 (로컬 파일 기반)
    if image_file_paths:
        for fpath in image_file_paths:
            results.append(check_image_dpi(fpath, media_type))

    return results
