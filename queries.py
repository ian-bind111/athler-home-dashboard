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

        # 2) 실행 — max_age=0으로 인라인 캐시 결과 비활성화 (반드시 job ID만 받음)
        # 이유: 캐시된 결과를 인라인 JSON으로 받을 때 응답 크기 때문에 ChunkedEncodingError 발생
        exec_resp = requests.post(
            f"{REDASH_URL}/api/queries/{query_id}/results",
            headers=headers,
            json={"max_age": 0},
            timeout=30,
        )
        exec_resp.raise_for_status()
        body = exec_resp.json()

        job = body.get("job", {})
        job_id = job.get("id")
        if not job_id:
            # max_age=0 인데도 인라인 결과가 온 예외 케이스 — 그대로 사용
            if "query_result" in body:
                rows = body.get("query_result", {}).get("data", {}).get("rows", [])
                return pd.DataFrame(rows)
            raise RuntimeError(f"job_id가 없음: {body}")

        # 3) 폴링 — 완료 시 query_result_id 함께 수집
        query_result_id = None
        start = time.time()
        while time.time() - start < timeout:
            j_resp = requests.get(f"{REDASH_URL}/api/jobs/{job_id}", headers=headers, timeout=15)
            j_resp.raise_for_status()
            j = j_resp.json().get("job", {})
            status = j.get("status")
            if status == 3:  # 완료
                query_result_id = j.get("query_result_id")
                break
            if status == 4:  # 실패
                raise RuntimeError(f"쿼리 실패: {j.get('error') or j}")
            time.sleep(2)
        else:
            raise TimeoutError(f"쿼리 제한 시간({timeout}초) 초과")

        # 4) 결과 조회 — urllib3로 직접 받아서 IncompleteRead 우회
        import urllib3, io
        if query_result_id:
            result_url = f"{REDASH_URL}/api/query_results/{query_result_id}.csv"
        else:
            result_url = f"{REDASH_URL}/api/queries/{query_id}/results.csv"
        http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=10, read=120))
        for attempt in range(3):
            try:
                ur = http.request(
                    "GET", result_url,
                    headers={"Authorization": f"Key {REDASH_API_KEY}"},
                    preload_content=True,
                )
                if ur.status >= 400:
                    raise RuntimeError(f"결과 조회 실패 HTTP {ur.status}")
                return pd.read_csv(io.StringIO(ur.data.decode("utf-8")))
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(3)
    finally:
        # 5) 임시 쿼리 정리
        if query_id:
            try:
                requests.delete(f"{REDASH_URL}/api/queries/{query_id}", headers=headers, timeout=10)
            except Exception:
                pass


def run_query_chunked(sql_fn, start_date: date, end_date: date, chunk_days: int = 3) -> pd.DataFrame:
    """
    날짜 범위를 chunk_days씩 나눠서 여러 번 조회 후 합치기.
    응답이 큰 쿼리(노출 등)가 IncompleteRead로 실패하는 경우 사용.
    sql_fn(start, end) → SQL 문자열을 반환하는 callable.
    """
    dfs = []
    cur = start_date
    while cur <= end_date:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end_date)
        df = run_query(sql_fn(cur, chunk_end))
        if not df.empty:
            dfs.append(df)
        cur = chunk_end + timedelta(days=1)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


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
    """
    return run_query(sql)


def get_banner_clicks_by_position(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    기간별 배너 위치(idx)별 클릭 수 조회 (하위 호환용 — 신규 코드는 get_banner_clicks_by_content 사용)
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
ORDER BY 1, 2, 3
    """
    return run_query(sql)


def get_banner_clicks_by_content(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    content_uuid 기준 배너별 클릭 수 조회
    - 배너 교체/이동 시 실제 콘텐츠 단위로 정확하게 추적
    반환 컬럼: event_date, section_uuid, content_uuid, clicks, unique_users
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    element_uuid AS section_uuid,
    content_uuid,
    COUNT(*) AS clicks,
    COUNT(DISTINCT distinct_id) AS unique_users
FROM {TABLE}
WHERE {date_filter}
  AND event = 'click_content'
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
  AND content_uuid IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1, 2, 3
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


def get_page_conversion_stats(start_date: date, end_date: date,
                               page_view_event: str,
                               page_name_filter: str = None) -> dict:
    """
    페이지 방문자 중 동 기간 내 구매 완료한 유저 비율 (Athena 기반).

    - page_visitors: 페이지 진입 이벤트 distinct_id 수
    - purchasers:    그 중 complete_order 이벤트를 발생시킨 distinct_id 수
    - conversion_rate: purchasers / page_visitors × 100

    반환: {"page_visitors": int, "purchasers": int, "conversion_rate": float}
    """
    date_filter = _date_conditions(start_date, end_date)

    pv_filter = f"event = '{page_view_event}'"
    if page_name_filter:
        pv_filter += f" AND page_name = '{page_name_filter}'"

    sql = f"""
WITH visitors AS (
    SELECT DISTINCT distinct_id
    FROM {TABLE}
    WHERE {date_filter}
      AND {pv_filter}
),
buyers AS (
    SELECT DISTINCT distinct_id
    FROM {TABLE}
    WHERE {date_filter}
      AND event = 'complete_order'
)
SELECT
    COUNT(v.distinct_id)                                      AS page_visitors,
    COUNT(b.distinct_id)                                      AS purchasers,
    ROUND(
        COUNT(b.distinct_id) * 100.0 / NULLIF(COUNT(v.distinct_id), 0),
        2
    )                                                         AS conversion_rate
FROM visitors v
LEFT JOIN buyers b ON v.distinct_id = b.distinct_id
    """
    df = run_query(sql)
    if df.empty:
        return {"page_visitors": 0, "purchasers": 0, "conversion_rate": 0.0}
    row = df.iloc[0]
    return {
        "page_visitors":   int(row.get("page_visitors", 0) or 0),
        "purchasers":      int(row.get("purchasers", 0) or 0),
        "conversion_rate": float(row.get("conversion_rate", 0.0) or 0.0),
    }


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
    """
    return run_query(sql)


def get_section_impressions(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    섹션별 노출 수 (content_impressed + product_impressed 이벤트)
    - content_impressed: 일반 섹션 (배너/타이틀/아이콘 등)
    - product_impressed: PRODUCT 타입 섹션 (DUAL_LIST, FLAT_STACK 등)
    반환 컬럼: event_date, section_uuid, impressions, unique_impressed
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    element_uuid                       AS section_uuid,
    COUNT(*)                           AS impressions,
    COUNT(DISTINCT distinct_id)        AS unique_impressed
FROM {TABLE}
WHERE {date_filter}
  AND event IN ('content_impressed', 'product_impressed')
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC
    """
    return run_query(sql)


def get_section_swipe_funnel(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    각 (사용자, 섹션) 쌍에서 사용자가 도달한 max banner_idx의 분포.
    Python에서 reverse cumulative sum으로 'idx N 이상 도달한 사용자 수' funnel 계산.

    SQL 단에서 미리 집계해 데이터 크기 작음 (~수백 행).

    반환 컬럼: section_uuid, max_idx, user_count
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
WITH user_max AS (
    SELECT
        distinct_id,
        element_uuid                AS section_uuid,
        MAX(CAST(idx AS BIGINT))    AS max_idx
    FROM {TABLE}
    WHERE {date_filter}
      AND event IN ('content_impressed', 'product_impressed')
      AND page_name = '{page_name}'
      AND element_uuid IS NOT NULL
      AND idx IS NOT NULL
      AND distinct_id IS NOT NULL
      AND distinct_id <> ''
    GROUP BY distinct_id, element_uuid
)
SELECT
    section_uuid,
    max_idx,
    COUNT(*) AS user_count
FROM user_max
GROUP BY section_uuid, max_idx
ORDER BY section_uuid, max_idx
    """
    return run_query(sql)


def get_user_section_pairs(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    사용자(distinct_id) × 섹션(element_uuid)의 DISTINCT 쌍 추출
    -> 도달 깊이 분포(funnel) 계산용
    각 사용자가 어떤 섹션들을 봤는지 알면, 그 사용자의 max(orderIndex)가 도달 깊이.

    반환 컬럼: distinct_id, section_uuid
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    distinct_id,
    element_uuid AS section_uuid
FROM {TABLE}
WHERE {date_filter}
  AND event IN ('content_impressed', 'product_impressed')
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
  AND distinct_id IS NOT NULL
  AND distinct_id <> ''
GROUP BY distinct_id, element_uuid
LIMIT 500000
    """
    return run_query(sql)


def get_banner_impressions_by_position(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    배너 위치(idx)별 노출 수 (하위 호환용 — 신규 코드는 get_banner_impressions_by_content 사용)
    반환 컬럼: event_date, section_uuid, banner_idx, impressions, unique_impressed
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    element_uuid                       AS section_uuid,
    CAST(idx AS VARCHAR)               AS banner_idx,
    COUNT(*)                           AS impressions,
    COUNT(DISTINCT distinct_id)        AS unique_impressed
FROM {TABLE}
WHERE {date_filter}
  AND event IN ('content_impressed', 'product_impressed')
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
  AND idx IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC
    """
    return run_query(sql)


def get_banner_impressions_by_content(start_date: date, end_date: date, page_name: str = "home") -> pd.DataFrame:
    """
    content_uuid 기준 배너별 노출 수 조회 (3일 청크로 나눠서 조회 — IncompleteRead 방지)
    반환 컬럼: event_date, section_uuid, content_uuid, impressions, unique_impressed
    """
    def sql_fn(s, e):
        date_filter = _date_conditions(s, e)
        return f"""
SELECT
    CONCAT(year, '-', month, '-', day) AS event_date,
    element_uuid                       AS section_uuid,
    content_uuid,
    COUNT(*)                           AS impressions,
    COUNT(DISTINCT distinct_id)        AS unique_impressed
FROM {TABLE}
WHERE {date_filter}
  AND event IN ('content_impressed', 'product_impressed')
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
  AND content_uuid IS NOT NULL
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC
        """
    return run_query_chunked(sql_fn, start_date, end_date, chunk_days=3)


# ──────────────────────────────────────────────────────────────────
# Last-touch GMV2 어트리뷰션 (클릭 후 7일 이내 결제)
#
# 로직:
#   1) Athena: 기간 내 배너 클릭 이벤트(distinct_id, section_uuid, banner_idx, click_time)
#   2) MySQL : 클릭일 ~ 클릭일+7일 이내 결제(channel_hash, ordered_at, payment_amount)
#   3) Python: 각 결제 → 결제 직전 7일 내 마지막 클릭 1개에 GMV2 100% 귀속 (last-touch)
#
# GMV2 정의: 할인·쿠폰·포인트 차감 후 실결제액. 교환·반품·취소·미결제 제외.
# 매핑 키: Athena distinct_id == MySQL users_user.channel_hash (로그인 사용자만)
# ──────────────────────────────────────────────────────────────────

MYSQL_DATA_SOURCE_ID = 1  # Athler MySQL


def get_banner_clicks_for_attribution(start_date: date, end_date: date,
                                        page_name: str = "home") -> pd.DataFrame:
    """
    Athena: 기간 내 홈/아울렛 배너 클릭 이벤트 raw 추출 (last-touch 매칭용)
    user_id로 MySQL users_user.id와 직접 매칭. 비로그인 사용자(user_id 없음)는 제외.

    중요: Athena `time` 컬럼은 epoch 밀리초이므로 1000으로 나눠서 초로 통일.
    MySQL UNIX_TIMESTAMP()는 초 단위이므로 같은 단위로 비교 가능.

    반환 컬럼: user_id, section_uuid, content_uuid, click_time (Unix timestamp, 초)
    """
    date_filter = _date_conditions(start_date, end_date)
    sql = f"""
SELECT
    user_id,
    element_uuid AS section_uuid,
    content_uuid,
    CAST(time / 1000 AS BIGINT) AS click_time
FROM {TABLE}
WHERE {date_filter}
  AND event = 'click_content'
  AND page_name = '{page_name}'
  AND element_uuid IS NOT NULL
  AND content_uuid IS NOT NULL
  AND user_id IS NOT NULL
  AND user_id <> ''
ORDER BY user_id, time
LIMIT 200000
    """
    return run_query(sql, data_source_id=ATHENA_DATA_SOURCE_ID)


def get_purchases_for_attribution(start_date: date, end_date: date,
                                    attribution_window_days: int = 7) -> pd.DataFrame:
    """
    MySQL: 교환·반품·취소 제외 GMV2 + user_id 추출
    구매 윈도우는 클릭 시작일 ~ 클릭 종료일+7일까지로 확장 (클릭 후 7일 내 구매 포착)

    Athena 이벤트 로그의 user_id와 동일 키이므로 users_user JOIN 불필요.
    timezone 혼란 방지를 위해 UNIX_TIMESTAMP로 직접 받아 Athena click_time과 정수 비교.

    반환 컬럼: user_id, ordered_at_ts (Unix sec), order_item_id, payment_amount
    """
    purchase_start = start_date.strftime("%Y-%m-%d")
    purchase_end   = (end_date + timedelta(days=attribution_window_days)).strftime("%Y-%m-%d")

    sql = f"""
SELECT
    o.user_id,
    UNIX_TIMESTAMP(o.ordered_at) AS ordered_at_ts,
    oi.id                        AS order_item_id,
    oi.payment_amount
FROM orders_orderitem oi
JOIN orders_order o
  ON oi.order_id = o.id
WHERE o.ordered_at BETWEEN '{purchase_start} 00:00:00'
                       AND '{purchase_end} 23:59:59'
  AND oi.status NOT IN (
      'CANCELED',
      'CANCEL_REQUESTED',
      'REFUND_APPROVED',
      'REFUNDED',
      'PENDING_PAYMENT',
      'EXCHANGE_APPROVED',
      'EXCHANGE_CONFIRMED'
  )
  AND oi.is_exchange = 0
  AND o.user_id IS NOT NULL
ORDER BY o.ordered_at
LIMIT 200000
    """
    return run_query(sql, data_source_id=MYSQL_DATA_SOURCE_ID)


def compute_banner_last_touch_gmv2(clicks_df: pd.DataFrame,
                                     purchases_df: pd.DataFrame,
                                     attribution_window_days: int = 7) -> pd.DataFrame:
    """
    Last-touch 어트리뷰션 매칭:
      각 결제(order_item)마다 결제 직전 N일(=7) 이내 마지막으로 클릭한 배너에 GMV2 100% 귀속.

    매칭 키: user_id (Athena event log의 user_id == MySQL users_user.id)
    timezone 혼란 방지를 위해 둘 다 Unix timestamp(초) 정수로 직접 비교.

    clicks_df    : user_id, section_uuid, content_uuid, click_time (Unix sec)
    purchases_df : user_id, ordered_at_ts (Unix sec), order_item_id, payment_amount

    반환 컬럼: section_uuid, content_uuid, attributed_gmv2, attributed_orders, attributed_users
    """
    empty_cols = ["section_uuid", "content_uuid",
                  "attributed_gmv2", "attributed_orders", "attributed_users"]
    if clicks_df is None or clicks_df.empty or purchases_df is None or purchases_df.empty:
        return pd.DataFrame(columns=empty_cols)

    clicks = clicks_df.copy()
    clicks["click_time"] = pd.to_numeric(clicks["click_time"], errors="coerce")
    clicks = clicks.dropna(subset=["click_time"])
    clicks["user_id"]     = clicks["user_id"].astype(str).str.strip()
    clicks["content_uuid"] = clicks["content_uuid"].astype(str)
    clicks = clicks[clicks["user_id"] != ""]

    purchases = purchases_df.copy()
    if "ordered_at_ts" in purchases.columns:
        purchases["ordered_ts"] = pd.to_numeric(purchases["ordered_at_ts"], errors="coerce")
    else:
        # 폴백: ordered_at 문자열을 KST로 가정하고 Unix sec으로 변환
        ordered_dt = pd.to_datetime(purchases.get("ordered_at"), errors="coerce")
        try:
            ordered_dt = ordered_dt.dt.tz_localize("Asia/Seoul")
        except (TypeError, AttributeError):
            pass
        purchases["ordered_ts"] = ordered_dt.astype("int64") // 10**9
    purchases = purchases.dropna(subset=["ordered_ts"])
    purchases["user_id"]        = purchases["user_id"].astype(str).str.strip()
    purchases["payment_amount"] = pd.to_numeric(
        purchases["payment_amount"], errors="coerce"
    ).fillna(0)

    window_seconds = attribution_window_days * 86400  # 7일 = 604800초

    # user_id → 클릭 묶음 (시간순 정렬, Unix timestamp 그대로)
    clicks_by_user = {
        uid: grp.sort_values("click_time")
        for uid, grp in clicks.groupby("user_id")
    }

    results = []
    for _, p in purchases.iterrows():
        uid = p["user_id"]
        if uid not in clicks_by_user:
            continue
        order_ts = float(p["ordered_ts"])
        user_clicks = clicks_by_user[uid]
        # candidates: 결제 시각 이전 + 7일 이내
        diff = order_ts - user_clicks["click_time"]
        mask = (diff >= 0) & (diff <= window_seconds)
        candidates = user_clicks[mask]
        if candidates.empty:
            continue
        last = candidates.iloc[-1]  # sort_values("click_time") 했으므로 마지막이 최신
        results.append({
            "section_uuid":  last["section_uuid"],
            "content_uuid":  last["content_uuid"],
            "gmv2":          float(p["payment_amount"]),
            "user_id":       uid,
            "order_item_id": p["order_item_id"],
        })

    if not results:
        return pd.DataFrame(columns=empty_cols)

    attr = pd.DataFrame(results)
    summary = (
        attr.groupby(["section_uuid", "content_uuid"])
        .agg(
            attributed_gmv2   = ("gmv2",          "sum"),
            attributed_orders = ("order_item_id", "count"),
            attributed_users  = ("user_id",       "nunique"),
        )
        .reset_index()
        .sort_values("attributed_gmv2", ascending=False)
    )
    return summary


def get_banner_last_touch_gmv2(start_date: date, end_date: date,
                                 page_name: str = "home",
                                 attribution_window_days: int = 7) -> pd.DataFrame:
    """
    통합 진입점: Athena 클릭 + MySQL 구매를 받아 배너별 last-touch GMV2 반환.
    반환 컬럼: section_uuid, content_uuid, attributed_gmv2, attributed_orders, attributed_users
    """
    clicks_df    = get_banner_clicks_for_attribution(start_date, end_date, page_name)
    purchases_df = get_purchases_for_attribution(start_date, end_date, attribution_window_days)
    return compute_banner_last_touch_gmv2(clicks_df, purchases_df, attribution_window_days)
