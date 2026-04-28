# -*- coding: utf-8 -*-
"""
athler.kr 페이지 메타 정보 (섹션 / 배너) 새로고침
- Playwright로 페이지 열어 API 응답 가로채서 sections/banners CSV 갱신
"""

import csv
from pathlib import Path
from typing import Dict


def refresh_meta(page_url: str, sections_csv: str, banners_csv: str) -> Dict[str, int]:
    """
    athler.kr 페이지를 열어서 섹션/배너 메타 정보를 다시 추출하여 CSV 저장.

    Returns:
        {"section_count": N, "banner_count": M}
    """
    from playwright.sync_api import sync_playwright

    api_responses = []

    def handle_response(response):
        url = response.url
        if "athler" not in url and "api" not in url.lower():
            return
        ct = response.headers.get("content-type", "")
        if "json" not in ct:
            return
        try:
            api_responses.append({"url": url, "body": response.json()})
        except Exception:
            pass

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.on("response", handle_response)
        page.goto(page_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        browser.close()

    # 메인 페이지 구조 API 찾기 (/api/v3/pages/home/temp)
    home = None
    for r in api_responses:
        if "/api/v3/pages/home/temp" in r["url"]:
            home = r["body"]
            break

    if not home:
        raise RuntimeError(
            f"athler.kr 페이지({page_url})의 메인 API 응답(/api/v3/pages/home/temp)을 찾을 수 없습니다."
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
# - Streamlit asyncio 루프와 충돌 회피용
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import io
    import json
    import sys
    import traceback

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    if len(sys.argv) < 4:
        print(json.dumps({"error": "usage: meta_refresh.py <url> <sections_csv> <banners_csv>"}))
        sys.exit(1)
    try:
        out = refresh_meta(sys.argv[1], sys.argv[2], sys.argv[3])
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({"error": str(e), "trace": traceback.format_exc()}))
        sys.exit(2)
