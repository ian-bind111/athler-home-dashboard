# -*- coding: utf-8 -*-
"""
Redash API를 통해 배너/섹션 이벤트 데이터를 조회하는 모듈

page_uuid: 486908c0-908d-4359-8e2c-419ce14cd0d7 (athler.kr 홈)
page_uuid: ca14a954-d190-464a-a77b-1cbfcf8c042e (athler.kr/home-outlet)

실제 확인된 이벤트 구조 (2026-04-27 기준):
- 테이블: "bind-event-logs"."bind_event_log_compacted" (Athena, 데이터소스 2번)
- 섹션 클릭: event = 'click_content', page_name = 해당 페이지, element_uuid = 섹션 UUID
- 배너 클릭: event = 'click_content', page_name = 해당 페이지, element_uuid = 섹션 UUID + idx = 배너 순서
- 홈 방문: event = 'view_home'
- 아울렛 방문: event = 'content_impressed', page_name = 'outlet' (view_* 이벤트 없음)
- 파티션: year, month (2자리), day (2자리)
"""

import os
import time
import requests
import pandas as pd
from datetime import date, timedelta
from pathlib import Path


def _load_env_local():
    """.env.local 파일이 있으면 환경변수로 자동 로드 (로컬 개발용)"""
    env_path = Path(__file__).parent / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and v and not os.environ.get(k):
            os.environ[k] = v


def _get_secret(key: str, default: str = "") -> str:
    """우선순위: 환경변수(.env.local 또는 시스템) → Streamlit Cloud secrets"""
    val = os.environ.get(key, "").strip()
    if val:
        return val
    try:
        import streamlit as st
        return str(st.secrets.get(key, default))
    except Exception:
        return default


_load_env_local()

# Redash 연결 설정
REDASH_URL = _get_secret("REDASH_URL", "").rstrip("/")
REDASH_API_KEY = _get_secret("REDASH_API_KEY", "")
ATHENA_DATA_SOURCE_ID = 2  # AWS Athena

# 테이블명
TABLE = '"bind-event-logs"."bind_event_log_compacted"'


def run_query(sql: str, data_source_id: int = ATHENA_DATA_SOURCE_ID, timeout: int = 180) -> pd.DataFrame:
    """
    Redash API로 ad-hoc SQL 쿼리를 실행하여 DataFrame으로 반환.
    절차:
    1) POST /api/queries        - 임시 쿼리 생성
    2) POST /api/queries/{id}/results - 실행 (job)
    3) GET /api/jobs/{job_id}    - 완료까지 폴링
    4) GET /api/queries/{id}/results - 결과 조회
    5) DELETE /api/queries/{id}  - 정리
    """
    if not REDASH_URL or not REDASH_API_KEY:
        raise ConnectionError("REDASH_URL 또는 REDASH_API_KEY 환경 변수가 설정되지 않았습니다.")

    headers = {"Authorization": f"Key {REDASH_API_KEY}", "Content-Type": "application/json"}
    query_id = None
    try:
        # 1) 임시 쿼리 생성
        create_resp = requests.post(
            f"{REDASH_URL}/api/queries",
            headers=headers,
            json={
                "data_source_id": data_source_id,
                "query": sql,
                "name": f"bind-ai-dashboard-{int(time.time())}",
                "description": "athler 홈/아울렛 영역 대시보드 ad-hoc",
            },
            timeout=30,
        )
        create_resp.raise_for_status()
        query_id = create_resp.json().get("id")
        if not query_id:
            raise RuntimeError(f"쿼리 생성 응답에 id가 없습니다: {create_resp.text[:300]}")

        # 2) 실행 (job 받음)
        exec_resp = requests.post(
            f"{REDASH_URL}/api/queries/{query_id}/results",
            headers=headers,
            json={},
            timeout=30,
        )
        exec_resp.raise_for_status()
        body = exec_resp.json()

        # 캐시된 결과가 바로 올 수도 있음
        if "query_result" in body:
            rows = body.get("query_result", {}).get("data", {}).get("rows", [])
            return pd.DataFrame(rows)

        job = body.get("job", {})
        job_id = job.get("id")
        if not job_id:
            raise RuntimeError(f"job_id가 없음: {body}")

        # 3) 폴링
        start = time.time()
        while time.time() - start < timeout:
            j_resp = requests.get(f"{REDASH_URL}/api/jobs/{job_id}", headers=headers, timeout=15)
            j_resp.raise_for_status()
            j = j_resp.json().get("job", {})
            status = j.get("status")
            if status == 3:  # 완료
                break
            if status == 4:  # 실패
                raise RuntimeError(f"쿼리 실패: {j.get('error') or j}")
            time.sleep(2)
        else:
            raise TimeoutError(f"쿼리 제한 시간({timeout}초) 초과")

        # 4) 결과 조회
        res_resp = requests.get(
            f"{REDASH_URL}/api/queries/{query_id}/results",
            headers=headers,
            timeout=30,
        )
        res_resp.raise_for_status()
        rows = res_resp.json().get("query_result", {}).get("data", {}).get("rows", [])
        return pd.DataFrame(rows)
    finally:
        # 5) 임시 쿼리 정리
        if query_id:
            try:
                requests.delete(f"{REDASH_URL}/api/queries/{query_id}", headers=headers, timeout=10)
            except Exception:
                pass


def _date_conditions(start_date: date, end_date: date) -> str:
    """
    Athena 파티션 필터 생성 (year/month/day 컬럼 기준)
    날짜 범위가 넓으면 월 단위로 압축하여 성능 최적화
    """
    conditions = []
    cur = start_date
    while cur <= end_date:
        conditions.append(
            f"(year='{cur.year}' AND month='{cur.month:02d}' AND day='{cur.day:02d}')"
        )
        cur += timedelta(days=1)
    return "(" + " OR ".join(conditions) + ")"


def get_section_clicks(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    기간별 섹션별 클릭 수 조회
    - event = 'click_content', page_name = 지정한 페이지
    - element_uuid → 섹션 UUID (sections.csv의 section_uuid와 매칭)
    반환 컬럼: event_date, section_uuid, clicks, unique_users
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    element_uuid AS section_uuid,
    COUNT(*) AS clicks,
    COUNT(DISTINCT distinct_id) AS unique_users
FROM {TABLE}
WHERE {date_filter}
  AND event = 'click_content'
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
LIMIT 1000
    """
    return run_query(sql)


def get_banner_clicks_by_position(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    기간별 배너 위치(idx)별 클릭 수 조회
    - 배너는 section_uuid + idx(순서) 조합으로 식별
    반환 컬럼: event_date, section_uuid, banner_idx, clicks, unique_users
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    element_uuid AS section_uuid,
    CAST(idx AS VARCHAR) AS banner_idx,
    COUNT(*) AS clicks,
    COUNT(DISTINCT distinct_id) AS unique_users
FROM {TABLE}
WHERE {date_filter}
  AND event = 'click_content'
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
  AND idx IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC
LIMIT 1000
    """
    return run_query(sql)


def get_page_visitors(start_date: date, end_date: date, view_event_name: str = "view_home",
                      page_name: str = None) -> pd.DataFrame:
    """
    페이지 방문자 수 조회 (CTR 분모)
    - 홈: event = 'view_home'
    - 아울렛: page_name = 'outlet', event = 'content_impressed' 로 distinct 집계
    반환 컬럼: event_date, page_views, unique_visitors
    """
    date_filter = _date_conditions(start_date, end_date)

    if page_name:
        # 아울렛처럼 page_name 기반으로 방문 집계 (content_impressed 이벤트)
        sql = f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    COUNT(*) AS page_views,
    COUNT(DISTINCT distinct_id) AS unique_visitors
FROM {TABLE}
WHERE {date_filter}
  AND event = '{view_event_name}'
  AND page_name = '{page_name}'
GROUP BY 1
ORDER BY 1 DESC
LIMIT 100
        """
    else:
        # 홈처럼 view_event 이름으로 바로 집계
        sql = f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    COUNT(*) AS page_views,
    COUNT(DISTINCT distinct_id) AS unique_visitors
FROM {TABLE}
WHERE {date_filter}
  AND event = '{view_event_name}'
GROUP BY 1
ORDER BY 1 DESC
LIMIT 100
        """
    return run_query(sql)


# 하위 호환성: 기존 코드에서 get_home_visitors 를 직접 import 하던 경우 대응
def get_home_visitors(start_date: date, end_date: date) -> pd.DataFrame:
    """홈 방문자 수 조회 (하위 호환 래퍼)"""
    return get_page_visitors(start_date, end_date, view_event_name="view_home")


def get_section_clicks_summary(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    기간 합산 섹션별 클릭 요약 (빠른 조회용)
    반환 컬럼: section_uuid, clicks, unique_users
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    element_uuid AS section_uuid,
    COUNT(*) AS clicks,
    COUNT(DISTINCT distinct_id) AS unique_users
FROM {TABLE}
WHERE {date_filter}
  AND event = 'click_content'
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 200
    """
    return run_query(sql)
