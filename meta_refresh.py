# -*- coding: utf-8 -*-
"""
athler.kr 페이지 메타 정보 (섹션 / 배너) 새로고침
- athler.co.kr API를 직접 호출해서 sections/banners CSV 갱신
- requests만 사용하므로 Streamlit Cloud에서도 작동 (Playwright 의존성 제거)

API 엔드포인트:
  https://athler.co.kr/api/v3/pages/{page_name}/temp
  - page_name='home'    → 홈 영역
  - page_name='outlet'  → 아울렛 영역
"""

import csv
from pathlib import Path
from typing import Dict

import requests


API_BASE = "https://athler.co.kr/api/v3/pages"
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def refresh_meta(page_name: str, sections_csv: str, banners_csv: str,
                 timeout: int = 20) -> Dict[str, int]:
    """
    athler.co.kr 페이지 API를 호출하여 섹션/배너 메타 정보를 CSV로 저장.

    Args:
        page_name: 'home' 또는 'outlet'
        sections_csv: 섹션 CSV 저장 경로
        banners_csv: 배너 CSV 저장 경로

    Returns:
        {"section_count": N, "banner_count": M}
    """
    url = f"{API_BASE}/{page_name}/temp"
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(
            f"athler API 호출 실패 ({url}): HTTP {resp.status_code} — {resp.text[:200]}"
        )
    try:
        home = resp.json()
    except ValueError as e:
        raise RuntimeError(f"API 응답이 JSON이 아닙니다: {e}")

    if not isinstance(home, dict) or "content" not in home:
        raise RuntimeError(
            f"예상한 응답 구조가 아닙니다 (content 필드 누락): {str(home)[:200]}"
        )

    # 섹션 / 배너 추출
    section_rows = []
    banner_rows = []
    for sec in home.get("content", []):
        section_rows.append({
            "section_id": sec.get("id"),
            "section_uuid": sec.get("uuid"),
            "elementType": sec.get("elementType"),
            "uiType": sec.get("uiType"),
            "memo": sec.get("memo"),
            "orderIndex": sec.get("orderIndex"),
            "banner_count": len(sec.get("banners", []) or []),
        })
        for b in sec.get("banners", []) or []:
            action = b.get("action") or {}
            banner_rows.append({
                "section_id": sec.get("id"),
                "section_uuid": sec.get("uuid"),
                "section_memo": sec.get("memo"),
                "banner_uuid": b.get("uuid"),
                "banner_title": b.get("title"),
                "banner_orderIndex": b.get("orderIndex"),
                "imageUrl": b.get("imageUrl"),
                "action_type": action.get("type") if isinstance(action, dict) else None,
                "action_target": (
                    action.get("value")
                    or action.get("targetUrl")
                    or action.get("url")
                ) if isinstance(action, dict) else None,
                "exposureStartAt": b.get("exposureStartAt"),
                "exposureEndAt": b.get("exposureEndAt"),
            })

    # CSV 저장 (utf-8-sig로 엑셀에서 한글 깨지지 않게)
    Path(sections_csv).parent.mkdir(parents=True, exist_ok=True)
    Path(banners_csv).parent.mkdir(parents=True, exist_ok=True)

    if section_rows:
        with open(sections_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(section_rows[0].keys()))
            w.writeheader()
            w.writerows(section_rows)
    if banner_rows:
        with open(banners_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(banner_rows[0].keys()))
            w.writeheader()
            w.writerows(banner_rows)

    return {
        "section_count": len(section_rows),
        "banner_count": len(banner_rows),
    }


# ──────────────────────────────────────────────
# CLI 진입점 (subprocess로 호출됨)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import io
    import json
    import sys
    import traceback

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    if len(sys.argv) < 4:
        print(json.dumps({"error": "usage: meta_refresh.py <page_name> <sections_csv> <banners_csv>"}))
        sys.exit(1)
    try:
        out = refresh_meta(sys.argv[1], sys.argv[2], sys.argv[3])
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({"error": str(e), "trace": traceback.format_exc()}))
        sys.exit(2)
