# -*- coding: utf-8 -*-
"""
athler 홈 / 아울렛 영역 대시보드 (멀티페이지)
- app.py: 홈 페이지 대시보드 (메인 엔트리)
- pages/1_홈_아울렛.py: 아울렛 페이지 대시보드

page_uuid (홈):    486908c0-908d-4359-8e2c-419ce14cd0d7
page_uuid (아울렛): ca14a954-d190-464a-a77b-1cbfcf8c042e
"""

import io
import os
import warnings
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

warnings.filterwarnings("ignore")


def _load_env_local():
    """.env.local 파일을 환경변수로 자동 로드 (python-dotenv 없이)"""
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


_load_env_local()

# ──────────────────────────────────────────────
# 페이지 설정 상수
# ──────────────────────────────────────────────
PAGE_HOME = {
    "label": "홈",
    "title": "athler 홈 영역 대시보드",
    "icon": "📊",
    "page_uuid": "486908c0-908d-4359-8e2c-419ce14cd0d7",
    "page_name": "home",
    "view_event": "view_home",
    "view_page_name": None,  # view_event 직접 사용
    "sections_csv": "data/sections.csv",
    "banners_csv": "data/banners.csv",
    "page_url": "https://athler.kr/home",
    "nav_label": "아울렛으로",
    "nav_page": "pages/1_outlet.py",
    "nav_url": "/outlet",  # streamlit 멀티페이지 URL 패턴
    "nav_icon": "🛍️",
    "color": "#3182F6",
    "section_count": 28,
    "banner_count": 56,
}

PAGE_OUTLET = {
    "label": "아울렛",
    "title": "athler 아울렛 영역 대시보드",
    "icon": "🛍️",
    "page_uuid": "ca14a954-d190-464a-a77b-1cbfcf8c042e",
    "page_name": "outlet",
    "view_event": "content_impressed",  # outlet은 view_* 없음 → content_impressed 사용
    "view_page_name": "outlet",         # page_name 필터 추가
    "sections_csv": "data/outlet_sections.csv",
    "banners_csv": "data/outlet_banners.csv",
    "page_url": "https://athler.kr/home-outlet",
    "nav_label": "홈으로",
    "nav_page": "app.py",
    "nav_url": "/",  # streamlit 멀티페이지 entry URL
    "nav_icon": "🏠",
    "color": "#FF9F43",
    "section_count": 19,
    "banner_count": 36,
}

# ──────────────────────────────────────────────
# 0. 페이지 초기화 (각 페이지 entry에서 호출)
#    - st.set_page_config (페이지당 1번만 가능)
#    - 토스 스타일 글로벌 CSS
#    이전에는 모듈 레벨이었지만, 멀티페이지에서 import 시점에 실행되면
#    pages/* 의 자체 set_page_config 와 충돌했음.
# ──────────────────────────────────────────────
def init_page(page_config: dict):
    """페이지 설정 + 글로벌 CSS 주입. 각 페이지 entry에서 호출."""
    st.set_page_config(
        page_title=page_config.get("title", "athler 대시보드"),
        page_icon=page_config.get("icon", "📊"),
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)


_GLOBAL_CSS = """
    <style>
    /* Pretendard 웹폰트 + Material Symbols (아이콘용) */
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded');

    html, body, [class*="css"], .stApp, .main, p, div, span, h1, h2, h3, h4, h5, h6,
    .stMarkdown, .stTextInput, .stSelectbox, label, button, .stButton, .stRadio,
    .stMultiSelect, .stDataFrame, .stMetric, table {
        font-family: "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI",
                     "Apple SD Gothic Neo", "Malgun Gothic", sans-serif !important;
    }

    /* 아이콘 폰트는 Material Symbols 보존 (Pretendard 덮어쓰기 방지) */
    [data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    .material-icons,
    .material-symbols-outlined,
    .material-symbols-rounded,
    [class*="material-symbols"],
    [class*="MaterialIcon"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                     'Material Icons' !important;
    }

    /* 메인 배경 */
    .stApp { background: #17171C; color: #F2F4F6; }
    .main .block-container { padding-top: 2rem; padding-bottom: 4rem; max-width: 1400px; }

    /* 헤더 */
    h1 { letter-spacing: -0.02em; font-weight: 700; color: #F8F9FA !important; }
    h2, h3 { letter-spacing: -0.01em; font-weight: 600; color: #F2F4F6 !important; }
    .stCaption, .caption, [data-testid="stCaptionContainer"] { color: #8B95A1 !important; }

    /* 카드형 컨테이너 */
    [data-testid="stMetric"] {
        background: #1F1F26;
        padding: 18px 22px;
        border-radius: 16px;
        border: 1px solid #2A2A33;
        box-shadow: 0 1px 0 rgba(255,255,255,0.02);
    }
    [data-testid="stMetricLabel"] { color: #8B95A1 !important; font-size: 0.85rem; }
    [data-testid="stMetricValue"] { color: #F8F9FA !important; font-weight: 700; letter-spacing: -0.02em; }

    /* 라디오 / 셀렉트 / 멀티셀렉트 */
    .stRadio > label, .stSelectbox > label, .stMultiSelect > label,
    .stDateInput > label, .stTextInput > label {
        color: #C9CDD2 !important; font-weight: 500;
    }

    /* 알림 박스 (info / success / warning / error) */
    .stAlert {
        border-radius: 12px;
        border: 1px solid #2A2A33;
    }

    /* 탭 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: transparent;
        border-bottom: 1px solid #2A2A33;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #8B95A1;
        border-radius: 10px 10px 0 0;
        padding: 10px 18px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        color: #3182F6 !important;
        background: transparent;
        border-bottom: 2px solid #3182F6;
    }

    /* 버튼 */
    .stButton > button {
        background: #3182F6;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 8px 18px;
        font-weight: 600;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        background: #1B64DA;
        transform: translateY(-1px);
    }

    /* 데이터프레임 */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #2A2A33;
    }

    /* 구분선 */
    hr { border-color: #2A2A33 !important; }

    /* 사이드바 + 토글 버튼만 숨기기 (Deploy 버튼은 보이게 유지) */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    [data-testid="stExpandSidebarButton"] { display: none !important; }
    /* 사이드바가 차지하던 공간 회수 */
    .main { margin-left: 0 !important; }
    section[data-testid="stSidebar"] + section { margin-left: 0 !important; }
    /* 헤더는 유지 (Deploy / 메뉴 버튼이 보이도록) — 배경만 페이지와 동일 */
    header[data-testid="stHeader"] { background: transparent !important; }

    /* 제목 자체를 page_link로 만든 부분 — 큰 제목처럼 보이게 */
    .dashboard-title-link [data-testid="stPageLink-NavLink"] {
        text-decoration: none !important;
        padding: 0 !important;
        background: transparent !important;
        border: none !important;
    }
    .dashboard-title-link [data-testid="stPageLink-NavLink"]:hover {
        background: rgba(49, 130, 246, 0.05) !important;
        border-radius: 8px;
    }
    .dashboard-title-link [data-testid="stPageLink-NavLink"] p {
        font-size: 2rem !important;
        font-weight: 700 !important;
        color: #F8F9FA !important;
        margin: 0 !important;
        letter-spacing: -0.02em;
    }
    .dashboard-title-link [data-testid="stPageLink-NavLink"] svg {
        color: #8B95A1 !important;
    }

    /* 셀렉트박스 인풋 */
    [data-baseweb="select"] > div {
        background: #1F1F26 !important;
        border-color: #2A2A33 !important;
        border-radius: 10px !important;
    }

    /* 코드 inline */
    code {
        background: #2A2A33 !important;
        color: #6BA8FF !important;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.85em;
    }

    /* 페이지 링크 버튼 스타일 */
    [data-testid="stPageLink"] a {
        border: 1px solid #2A2A33;
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 0.85rem;
        color: #8B95A1 !important;
        text-decoration: none;
        display: inline-block;
        transition: all 0.15s;
    }
    [data-testid="stPageLink"] a:hover {
        border-color: #3182F6;
        color: #3182F6 !important;
        background: rgba(49,130,246,0.08);
    }
    </style>
"""


# ──────────────────────────────────────────────
# 1. 색상 (토스 팔레트)
# ──────────────────────────────────────────────
C_BLUE   = "#3182F6"   # 토스 메인 블루
C_ORANGE = "#FF9F43"
C_GREEN  = "#10B981"
C_GRAY   = "#8B95A1"
C_PURPLE = "#A855F7"
C_RED    = "#EF4444"

# Plotly 다크 테마 기본 적용
PLOTLY_TEMPLATE = "plotly_dark"
PLOTLY_BG = "#17171C"
PLOTLY_PAPER = "#1F1F26"

import plotly.io as pio
pio.templates["toss_dark"] = pio.templates["plotly_dark"].update(
    layout=dict(
        paper_bgcolor=PLOTLY_PAPER,
        plot_bgcolor=PLOTLY_PAPER,
        font=dict(family="Pretendard, sans-serif", color="#F2F4F6", size=12),
        colorway=["#3182F6", "#10B981", "#FF9F43", "#A855F7", "#EF4444",
                  "#06B6D4", "#F59E0B", "#EC4899", "#84CC16", "#6366F1"],
        xaxis=dict(gridcolor="#2A2A33", linecolor="#2A2A33", zerolinecolor="#2A2A33"),
        yaxis=dict(gridcolor="#2A2A33", linecolor="#2A2A33", zerolinecolor="#2A2A33"),
    )
)
pio.templates.default = "toss_dark"

# ──────────────────────────────────────────────
# 2. 경로 설정
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


# ──────────────────────────────────────────────
# 3. 메타데이터 로드 (CSV)
# ──────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_sections(csv_filename: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, csv_filename.replace("data/", ""))
    df = pd.read_csv(path, encoding="utf-8")
    df.columns = df.columns.str.lstrip("﻿")  # BOM 제거
    if "orderIndex" in df.columns:
        df = df.sort_values("orderIndex").reset_index(drop=True)
    df["section_uuid"] = df["section_uuid"].astype(str)
    return df


@st.cache_data(ttl=600)
def load_banners(csv_filename: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, csv_filename.replace("data/", ""))
    df = pd.read_csv(path, encoding="utf-8")
    df.columns = df.columns.str.lstrip("﻿")  # BOM 제거
    df["section_uuid"] = df["section_uuid"].astype(str)
    df["banner_uuid"] = df["banner_uuid"].astype(str)
    # banner_orderIndex: 1부터 시작 → 이벤트 로그 idx는 0부터. 맞춰서 0-기반 컬럼 추가
    if "banner_orderIndex" in df.columns:
        df["banner_idx"] = (df["banner_orderIndex"].astype(float) - 1).astype(int).astype(str)
    return df


# ──────────────────────────────────────────────
# 4. Redash 연결 확인
# ──────────────────────────────────────────────
def redash_configured() -> bool:
    return bool(
        os.environ.get("REDASH_URL", "").strip() and
        os.environ.get("REDASH_API_KEY", "").strip()
    )


# ──────────────────────────────────────────────
# 5. 실시간 데이터 로드 (Redash)
# ──────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner="Redash에서 데이터를 불러오는 중입니다...")
def load_live_data(start_date: date, end_date: date, page_config: dict) -> dict:
    try:
        from queries import (
            get_section_clicks,
            get_banner_clicks_by_position,
            get_page_visitors,
        )
        page_name = page_config["page_name"]
        view_event = page_config["view_event"]
        view_page_name = page_config.get("view_page_name")

        sec_clicks   = get_section_clicks(start_date, end_date, page_name=page_name)
        banner_pos   = get_banner_clicks_by_position(start_date, end_date, page_name=page_name)
        visitors     = get_page_visitors(
            start_date, end_date,
            view_event_name=view_event,
            page_name=view_page_name,
        )
        return {
            "section_clicks":   sec_clicks,
            "banner_pos_clicks": banner_pos,
            "home_visitors":    visitors,
            "source": "live",
        }
    except Exception as e:
        return {"source": "error", "error": str(e)}


# ──────────────────────────────────────────────
# 6. 샘플(데모) 데이터 생성
# ──────────────────────────────────────────────
@st.cache_data(ttl=3600)
def make_demo_data(sections_df: pd.DataFrame, banners_df: pd.DataFrame,
                   start_date: date, end_date: date) -> dict:
    import numpy as np
    rng = np.random.default_rng(42)
    days_list = [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range((end_date - start_date).days + 1)
    ]

    # 섹션별 일별 클릭
    sec_rows = []
    for _, s in sections_df.iterrows():
        base = int(rng.integers(200, 8000))
        for d in days_list:
            clicks = max(1, int(base * rng.uniform(0.7, 1.3)))
            sec_rows.append({
                "event_date": d,
                "section_uuid": s["section_uuid"],
                "clicks": clicks,
                "unique_users": int(clicks * rng.uniform(0.7, 0.95)),
            })
    sec_click_df = pd.DataFrame(sec_rows)

    # 배너(위치별) 일별 클릭
    banner_rows = []
    for _, b in banners_df.iterrows():
        base = max(5, int(rng.integers(10, 500)))
        idx_val = str(int(b.get("banner_orderIndex", 1)) - 1)
        for d in days_list:
            clicks = max(1, int(base * rng.uniform(0.6, 1.4)))
            banner_rows.append({
                "event_date": d,
                "section_uuid": b["section_uuid"],
                "banner_idx": idx_val,
                "clicks": clicks,
                "unique_users": int(clicks * rng.uniform(0.7, 0.95)),
            })
    banner_pos_df = pd.DataFrame(banner_rows)

    # 방문자
    visitor_rows = []
    for d in days_list:
        pv = int(rng.integers(80000, 140000))
        visitor_rows.append({
            "event_date": d,
            "page_views": pv,
            "unique_visitors": int(pv * rng.uniform(0.3, 0.5)),
        })
    visitor_df = pd.DataFrame(visitor_rows)

    return {
        "section_clicks": sec_click_df,
        "banner_pos_clicks": banner_pos_df,
        "home_visitors": visitor_df,
        "source": "demo",
    }


# ──────────────────────────────────────────────
# 7. 집계 함수
# ──────────────────────────────────────────────
def build_section_summary(sections_df: pd.DataFrame, sec_click_df: pd.DataFrame,
                           visitor_df: pd.DataFrame) -> pd.DataFrame:
    """섹션별 클릭 합산 + 메타 병합 + CTR 계산"""
    if not sec_click_df.empty and "section_uuid" in sec_click_df.columns:
        agg = (
            sec_click_df.groupby("section_uuid")
            .agg(clicks=("clicks", "sum"), unique_users=("unique_users", "sum"))
            .reset_index()
        )
    else:
        agg = pd.DataFrame(columns=["section_uuid", "clicks", "unique_users"])

    result = sections_df.merge(agg, on="section_uuid", how="left")
    result["clicks"] = result["clicks"].fillna(0).astype(int)
    result["unique_users"] = result["unique_users"].fillna(0).astype(int)

    total_visitors = visitor_df["unique_visitors"].sum() if not visitor_df.empty and "unique_visitors" in visitor_df.columns else 0
    if total_visitors > 0:
        result["CTR(%)"] = (result["clicks"] / total_visitors * 100).round(3)
    else:
        result["CTR(%)"] = 0.0
    return result


def build_banner_summary(banners_df: pd.DataFrame, banner_pos_df: pd.DataFrame,
                          visitor_df: pd.DataFrame) -> pd.DataFrame:
    """배너(위치 기반) 클릭 합산 + 메타 병합 + CTR 계산"""
    if not banner_pos_df.empty and "section_uuid" in banner_pos_df.columns:
        agg = (
            banner_pos_df.groupby(["section_uuid", "banner_idx"])
            .agg(clicks=("clicks", "sum"), unique_users=("unique_users", "sum"))
            .reset_index()
        )
        agg["section_uuid"] = agg["section_uuid"].astype(str)
        agg["banner_idx"] = agg["banner_idx"].astype(str)
    else:
        agg = pd.DataFrame(columns=["section_uuid", "banner_idx", "clicks", "unique_users"])

    result = banners_df.copy()
    result["section_uuid"] = result["section_uuid"].astype(str)
    if "banner_idx" not in result.columns:
        result["banner_idx"] = "0"
    result["banner_idx"] = result["banner_idx"].astype(str)

    result = result.merge(agg, on=["section_uuid", "banner_idx"], how="left")
    result["clicks"] = result["clicks"].fillna(0).astype(int)
    result["unique_users"] = result["unique_users"].fillna(0).astype(int)

    total_visitors = visitor_df["unique_visitors"].sum() if not visitor_df.empty and "unique_visitors" in visitor_df.columns else 0
    if total_visitors > 0:
        result["CTR(%)"] = (result["clicks"] / total_visitors * 100).round(4)
    else:
        result["CTR(%)"] = 0.0
    return result


def get_daily_section(sec_click_df: pd.DataFrame, section_uuid: str) -> pd.DataFrame:
    if sec_click_df.empty or "section_uuid" not in sec_click_df.columns:
        return pd.DataFrame()
    sub = sec_click_df[sec_click_df["section_uuid"] == section_uuid].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["event_date"] = pd.to_datetime(sub["event_date"])
    return sub.groupby("event_date")[["clicks", "unique_users"]].sum().reset_index()


def get_daily_banner(banner_pos_df: pd.DataFrame, section_uuid: str, banner_idx: str) -> pd.DataFrame:
    if banner_pos_df.empty:
        return pd.DataFrame()
    mask = (
        (banner_pos_df["section_uuid"] == section_uuid) &
        (banner_pos_df["banner_idx"].astype(str) == str(banner_idx))
    )
    sub = banner_pos_df[mask].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["event_date"] = pd.to_datetime(sub["event_date"])
    return sub.groupby("event_date")[["clicks", "unique_users"]].sum().reset_index()


# ──────────────────────────────────────────────
# 8. UI 컴포넌트
# ──────────────────────────────────────────────
def kpi_card(col, label: str, value, unit: str = "", color: str = C_BLUE, delta=None):
    with col:
        delta_html = ""
        if delta is not None:
            sign = "+" if delta >= 0 else ""
            arrow = "▲" if delta >= 0 else "▼"
            dc = C_GREEN if delta >= 0 else C_RED
            delta_html = f'<p style="margin:2px 0 0;font-size:0.82rem;color:{dc};">{arrow} {sign}{delta:.1f}%</p>'
        formatted = f"{value:,}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
        st.markdown(
            f"""
            <div style="background:#f8f9fa;border-left:4px solid {color};
                        padding:14px 18px;border-radius:8px;margin-bottom:10px;">
                <p style="margin:0;font-size:0.75rem;color:#6c757d;font-weight:600;letter-spacing:0.3px;">{label}</p>
                <p style="margin:6px 0 0;font-size:1.75rem;font-weight:700;color:#212529;line-height:1.1;">
                    {formatted}<span style="font-size:0.9rem;color:#6c757d;font-weight:400;"> {unit}</span>
                </p>
                {delta_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


def img_html(url: str, width: int = 56) -> str:
    if pd.isna(url) or not str(url).startswith("http"):
        return "<span style='color:#aaa;'>—</span>"
    return (
        f'<img src="{url}" width="{width}" height="{width}" '
        f'style="object-fit:cover;border-radius:4px;border:1px solid #ddd;" '
        f'onerror="this.outerHTML=\'<span style=&quot;color:#aaa;&quot;>X</span>\'">'
    )


# ──────────────────────────────────────────────
# 9. 섹션 드릴다운
# ──────────────────────────────────────────────
def render_section_drilldown(sec_summary, banner_summary, banner_pos_df, page_key="home"):
    """섹션 안의 배너 보기 (드릴다운)"""
    st.markdown("### 섹션 안의 배너 보기")
    st.caption("섹션을 하나 선택하면, 그 섹션에 속한 배너들을 노출 순서대로 보여드려요.")

    sections_with_banners = (
        banner_summary.groupby("section_uuid").size().reset_index(name="cnt")
    )
    sections_with_banners = sections_with_banners[sections_with_banners["cnt"] > 0]
    valid_uuids = set(sections_with_banners["section_uuid"].astype(str))

    sec_for_drill = sec_summary[sec_summary["section_uuid"].astype(str).isin(valid_uuids)].copy()
    if sec_for_drill.empty:
        st.info("배너가 등록된 섹션이 없습니다.")
        return

    def _drill_label(r):
        memo = r.get("memo", "") or "(이름 없음)"
        cnt = int(sections_with_banners.loc[
            sections_with_banners["section_uuid"].astype(str) == str(r["section_uuid"]), "cnt"
        ].iloc[0])
        return f"{memo} — {r['section_id']} (배너 {cnt}개)"

    sec_for_drill["drill_label"] = sec_for_drill.apply(_drill_label, axis=1)
    drill_label_to_uuid = dict(zip(sec_for_drill["drill_label"], sec_for_drill["section_uuid"].astype(str)))

    if "clicks" in sec_for_drill.columns:
        sec_for_drill = sec_for_drill.sort_values("clicks", ascending=False)

    sel_drill_label = st.selectbox(
        "섹션 선택",
        sec_for_drill["drill_label"].tolist(),
        key=f"drill_section_{page_key}",
    )
    sel_uuid = drill_label_to_uuid.get(sel_drill_label, "")
    if not sel_uuid:
        return

    sec_row = sec_summary[sec_summary["section_uuid"].astype(str) == sel_uuid].iloc[0]
    sec_clicks_total = int(sec_row.get("clicks", 0) or 0)
    sec_users = int(sec_row.get("unique_users", 0) or 0)
    sec_ctr = float(sec_row.get("CTR(%)", 0) or 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("섹션명", sec_row.get("memo", "—") or "—")
    m2.metric("섹션 총 클릭", f"{sec_clicks_total:,}")
    m3.metric("섹션 순 클릭자", f"{sec_users:,}")
    m4.metric("섹션 CTR", f"{sec_ctr:.2f}%")

    st.caption(
        f"섹션 ID: `{sec_row['section_id']}` | "
        f"UUID: `{sel_uuid}` | "
        f"유형: {sec_row.get('elementType', '-')} | "
        f"UI: {sec_row.get('uiType', '-')}"
    )

    sec_banners = banner_summary[
        banner_summary["section_uuid"].astype(str) == sel_uuid
    ].copy()

    # 정렬 옵션
    sort_by = st.radio(
        "정렬 기준",
        ["노출 순서", "클릭 많은 순", "CTR 높은 순"],
        horizontal=True,
        key=f"banner_sort_{sel_uuid}",
    )
    if sort_by == "클릭 많은 순":
        sec_banners = sec_banners.sort_values("clicks", ascending=False)
    elif sort_by == "CTR 높은 순" and "CTR(%)" in sec_banners.columns:
        sec_banners = sec_banners.sort_values("CTR(%)", ascending=False)
    else:  # 노출 순서
        if "banner_orderIndex" in sec_banners.columns:
            sec_banners["_order"] = pd.to_numeric(sec_banners["banner_orderIndex"], errors="coerce").fillna(999)
            sec_banners = sec_banners.sort_values("_order").drop(columns=["_order"])

    sec_banners_disp = sec_banners.copy()
    sec_banners_disp["썸네일"] = sec_banners_disp["imageUrl"].apply(img_html) if "imageUrl" in sec_banners_disp.columns else "—"
    sec_banners_disp["순서"] = sec_banners_disp.get("banner_orderIndex", pd.Series(dtype=str))

    def _banner_name(r):
        title = r.get("banner_title", "")
        if pd.isna(title) or not str(title).strip():
            return f"배너 {r.get('banner_orderIndex', '?')}"
        return str(title)

    sec_banners_disp["배너명"] = sec_banners_disp.apply(_banner_name, axis=1)
    sec_banners_disp["링크"] = sec_banners_disp.get("action_target", pd.Series(dtype=str)).fillna("—")
    sec_banners_disp["섹션 내 비중(%)"] = (
        (sec_banners_disp["clicks"] / sec_clicks_total * 100).round(2)
        if sec_clicks_total > 0 else 0.0
    )

    show_cols = ["순서", "썸네일", "배너명", "clicks", "unique_users", "CTR(%)", "섹션 내 비중(%)", "링크"]
    avail_cols = [c for c in show_cols if c in sec_banners_disp.columns]
    rename_d = {"clicks": "클릭 수", "unique_users": "순 클릭자", "CTR(%)": "CTR (%)"}
    final_table = sec_banners_disp[avail_cols].copy()
    final_table.columns = [rename_d.get(c, c) for c in final_table.columns]

    st.markdown(f"**섹션 내 배너 ({len(sec_banners_disp)}개) — {sort_by}**")
    st.write(
        final_table.to_html(escape=False, index=False, table_id="sec-banner-table"),
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <style>
        #sec-banner-table{
            border-collapse:separate; border-spacing:0;
            width:100%; font-size:0.85rem;
            background:#1F1F26; border-radius:12px; overflow:hidden;
            border:1px solid #2A2A33;
        }
        #sec-banner-table th{
            background:#222B36; color:#C9CDD2; font-weight:600;
            padding:10px 12px; text-align:left;
            border-bottom:1px solid #2A2A33;
        }
        #sec-banner-table td{
            padding:10px 12px; color:#F2F4F6;
            border-bottom:1px solid #2A2A33;
            vertical-align:middle;
        }
        #sec-banner-table tr:last-child td{ border-bottom:none; }
        #sec-banner-table tr:hover td{ background:#222B36; }
        #sec-banner-table img{ border-radius:6px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not sec_banners.empty and sec_banners["clicks"].sum() > 0:
        bar_df = sec_banners.copy()

        def _bar_label(r):
            try:
                order = int(float(r.get("banner_orderIndex", 0) or 0))
            except (TypeError, ValueError):
                order = 0
            title = r.get("banner_title", "")
            if pd.isna(title) or not str(title).strip():
                title_disp = "(제목 없음)"
            else:
                title_disp = str(title)[:25] or "(제목 없음)"
            return f"{order}. {title_disp}"

        bar_df["배너"] = bar_df.apply(_bar_label, axis=1)
        fig_b_order = px.bar(
            bar_df, x="배너", y="clicks",
            labels={"clicks": "클릭 수", "배너": "노출 순서"},
            color="clicks", color_continuous_scale="Blues",
            text="clicks",
        )
        fig_b_order.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_b_order.update_layout(
            height=380, showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=20, b=80),
            xaxis_tickangle=-25,
        )
        st.plotly_chart(fig_b_order, use_container_width=True)

    if not banner_pos_df.empty:
        sec_pos = banner_pos_df[banner_pos_df["section_uuid"].astype(str) == sel_uuid].copy()
        if not sec_pos.empty:
            sec_pos["event_date"] = pd.to_datetime(sec_pos["event_date"], errors="coerce")
            sec_pos = sec_pos.dropna(subset=["event_date"])
            sec_pos["배너 순서"] = (sec_pos["banner_idx"].astype(float).astype(int) + 1).astype(str) + "번"
            if not sec_pos.empty:
                fig_b_trend = px.line(
                    sec_pos.sort_values("event_date"),
                    x="event_date", y="clicks",
                    color="배너 순서",
                    labels={"event_date": "날짜", "clicks": "클릭 수"},
                    markers=True,
                )
                fig_b_trend.update_layout(height=360, margin=dict(l=0, r=0, t=20, b=0))
                st.markdown("**배너별 일별 클릭 추이**")
                st.plotly_chart(fig_b_trend, use_container_width=True)


def render_section_perf_table(sec_summary):
    """섹션별 성과 표"""
    st.subheader("섹션별 성과")
    col_map = {
        "section_id": "섹션 ID",
        "memo": "섹션명",
        "elementType": "유형",
        "uiType": "UI 타입",
        "orderIndex": "표시 순서",
        "banner_count": "배너 수",
        "clicks": "클릭 수",
        "unique_users": "순 클릭자",
        "CTR(%)": "CTR (%)",
    }
    avail = [c for c in col_map if c in sec_summary.columns]
    show_df = sec_summary[avail].copy()
    show_df.columns = [col_map[c] for c in avail]
    st.dataframe(
        show_df.sort_values("클릭 수", ascending=False),
        use_container_width=True,
        hide_index=True,
    )


# ──────────────────────────────────────────────
# 10. 메인 대시보드 렌더링 (페이지 설정 인자로 범용화)
# ──────────────────────────────────────────────
def render_dashboard(page_config: dict):
    """
    페이지 설정(page_config)을 받아 홈/아울렛 대시보드를 동일한 구조로 렌더링.
    page_config 키: label, title, page_uuid, page_name, view_event,
                    sections_csv, banners_csv, page_url, nav_label, nav_page, nav_icon, color
    """
    page_key = page_config.get("page_name", "home")
    nav_page = page_config.get("nav_page", "")
    nav_label = page_config.get("nav_label", "")
    nav_icon = page_config.get("nav_icon", "")
    accent = page_config.get("color", C_BLUE)

    # ── 헤더: 제목 + 페이지 이동 링크
    col_t, col_nav = st.columns([5, 1])
    with col_t:
        # 제목 자체를 anchor 링크로 — 클릭 시 다른 페이지로 이동
        nav_url = page_config.get("nav_url", "")
        if nav_url:
            title_html = (
                f'<a href="{nav_url}" target="_self" '
                f'style="text-decoration:none;color:inherit;display:inline-block;'
                f'border-bottom:2px dashed transparent;padding:4px 0 2px 0;'
                f'transition:border-color 0.2s;" '
                f'onmouseover="this.style.borderColor=\'#3182F6\'" '
                f'onmouseout="this.style.borderColor=\'transparent\'" '
                f'title="클릭하면 {nav_label} 이동">'
                f'<div style="font-size:2.2rem;font-weight:700;color:#F8F9FA;'
                f'line-height:1.2;letter-spacing:-0.02em;">'
                f'{page_config["title"]}'
                f'</div>'
                f'</a>'
            )
            st.markdown(title_html, unsafe_allow_html=True)
        else:
            st.markdown(f"# {page_config['title']}")
        st.caption(
            f"athler.kr {page_config['label']} | "
            f"섹션 {page_config.get('section_count', '?')}개 · 배너 {page_config.get('banner_count', '?')}개 클릭 분석  "
            f"| page_uuid: {page_config['page_uuid']}  "
            f"| 💡 제목을 클릭하거나 우측 \"{nav_label}\" 버튼으로 다른 페이지 이동"
        )
    with col_nav:
        st.write("")
        st.write("")
        if nav_page:
            st.page_link(nav_page, label=f"{nav_icon} {nav_label}", use_container_width=True)
        # 메타 새로고침 버튼: athler.kr 페이지를 다시 긁어 섹션명/배너 정보 갱신
        if st.button(
            "🔄 메타 새로고침",
            help=f"{page_config['page_url']} 페이지에서 섹션명/배너 이미지/링크를 다시 가져옵니다 (1~2분 소요).",
            key=f"refresh_meta_{page_key}",
            use_container_width=True,
        ):
            with st.spinner("athler 페이지에서 최신 정보를 가져오는 중... (1~2분)"):
                try:
                    import json as _json
                    import subprocess
                    import sys as _sys
                    sections_path = os.path.join(
                        BASE_DIR, "data",
                        os.path.basename(page_config["sections_csv"]),
                    )
                    banners_path = os.path.join(
                        BASE_DIR, "data",
                        os.path.basename(page_config["banners_csv"]),
                    )
                    # Streamlit asyncio 루프와 Playwright sync API 충돌 회피 위해 subprocess 사용
                    proc = subprocess.run(
                        [
                            _sys.executable,
                            os.path.join(BASE_DIR, "meta_refresh.py"),
                            page_config["page_url"],
                            sections_path,
                            banners_path,
                        ],
                        capture_output=True, text=True, encoding="utf-8",
                        timeout=180,
                    )
                    last_line = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else "{}"
                    try:
                        out = _json.loads(last_line)
                    except Exception:
                        out = {"error": f"응답 파싱 실패: {last_line[:200]}"}
                    if proc.returncode != 0 or "error" in out:
                        err_msg = out.get("error") or proc.stderr[-300:] or "알 수 없는 오류"
                        st.error(f"❌ 새로고침 실패: {err_msg}")
                    else:
                        st.cache_data.clear()
                        st.success(
                            f"✅ 새로고침 완료 — 섹션 {out['section_count']}개, "
                            f"배너 {out['banner_count']}개"
                        )
                        st.rerun()
                except subprocess.TimeoutExpired:
                    st.error("❌ 새로고침 시간 초과 (3분). athler.kr 응답이 너무 느립니다.")
                except Exception as e:
                    st.error(f"❌ 새로고침 실패: {type(e).__name__}: {e}")

    # ──────────────────────────────
    # 기간 필터
    # ──────────────────────────────
    st.markdown("---")
    c_period, c_custom, c_refresh = st.columns([3, 3, 1])
    today = date.today()

    with c_period:
        period = st.radio(
            "조회 기간",
            ["오늘", "어제", "최근 7일", "최근 14일", "최근 30일", "직접 지정"],
            horizontal=True,
            index=2,
            key=f"period_{page_key}",
        )

    if period == "오늘":
        start_date = end_date = today
    elif period == "어제":
        start_date = end_date = today - timedelta(days=1)
    elif period == "최근 7일":
        start_date, end_date = today - timedelta(days=6), today
    elif period == "최근 14일":
        start_date, end_date = today - timedelta(days=13), today
    elif period == "최근 30일":
        start_date, end_date = today - timedelta(days=29), today
    else:
        with c_custom:
            picked = st.date_input(
                "날짜 범위 선택",
                value=(today - timedelta(days=6), today),
                max_value=today,
                key=f"date_pick_{page_key}",
            )
            if isinstance(picked, (list, tuple)) and len(picked) == 2:
                start_date, end_date = picked
            else:
                start_date = end_date = picked if not isinstance(picked, (list, tuple)) else today

    with c_refresh:
        st.write("")
        st.write("")
        if st.button("새로고침", key=f"refresh_{page_key}"):
            st.cache_data.clear()
            st.rerun()

    st.markdown(f"**조회 기간:** {start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')}")
    st.markdown("---")

    # ──────────────────────────────
    # 메타데이터 로드
    # ──────────────────────────────
    sections_df = load_sections(page_config["sections_csv"])
    banners_df  = load_banners(page_config["banners_csv"])

    # ──────────────────────────────
    # 이벤트 데이터 로드
    # ──────────────────────────────
    if redash_configured():
        raw = load_live_data(start_date, end_date, page_config)
    else:
        raw = {"source": "no_config"}

    src = raw.get("source", "error")

    if src == "live":
        st.success(f"실시간 데이터 연결됨 (Redash → AWS Athena) | page_name='{page_config['page_name']}'", icon="✅")
    elif src == "no_config":
        st.info(
            "Redash 연결 정보가 없어 **샘플 데이터**로 표시합니다.  \n"
            "`REDASH_URL` / `REDASH_API_KEY` 환경 변수를 설정하면 실시간 데이터를 볼 수 있어요.",
            icon="ℹ️",
        )
        raw = make_demo_data(sections_df, banners_df, start_date, end_date)
        src = "demo"
    elif src == "error":
        err_msg = raw.get("error", "알 수 없는 오류")
        st.warning(
            f"데이터 로드 중 오류가 발생했습니다: `{err_msg}`  \n샘플 데이터로 표시합니다.",
            icon="⚠️",
        )
        raw = make_demo_data(sections_df, banners_df, start_date, end_date)
        src = "demo"

    if src == "demo":
        st.caption("※ 아래 수치는 실제 데이터가 아닌 예시입니다.")

    sec_click_df   = raw.get("section_clicks",   pd.DataFrame())
    banner_pos_df  = raw.get("banner_pos_clicks", pd.DataFrame())
    visitor_df     = raw.get("home_visitors",     pd.DataFrame())

    # ──────────────────────────────
    # 집계
    # ──────────────────────────────
    sec_summary    = build_section_summary(sections_df, sec_click_df, visitor_df)
    banner_summary = build_banner_summary(banners_df, banner_pos_df, visitor_df)

    # 섹션 labels (재사용)
    section_labels = sec_summary.apply(
        lambda r: f"{r.get('memo', '')} ({r['section_id']})" if r.get("memo") else str(r["section_id"]),
        axis=1,
    ).tolist()
    label_to_uuid = dict(zip(section_labels, sec_summary["section_uuid"].tolist()))

    b_labels = banner_summary.apply(
        lambda r: (str(r.get("banner_title", "")) or f"{r.get('section_memo','?')} #{r.get('banner_orderIndex','?')}")[:40],
        axis=1,
    ).tolist()
    b_sec_uuid_list  = banner_summary["section_uuid"].tolist()
    b_idx_list       = banner_summary["banner_idx"].astype(str).tolist() if "banner_idx" in banner_summary.columns else ["0"] * len(b_labels)
    b_label_to_meta  = {
        label: (suuid, bidx)
        for label, suuid, bidx in zip(b_labels, b_sec_uuid_list, b_idx_list)
    }

    # ──────────────────────────────
    # 탭
    # ──────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["종합 요약", "섹션별 분석", "배너별 분석", "상세 비교"])

    # ════════════════════════════════════════════
    # TAB 1 — 종합 요약
    # ════════════════════════════════════════════
    with tab1:
        st.subheader("핵심 지표")

        total_visitors   = int(visitor_df["unique_visitors"].sum()) if not visitor_df.empty and "unique_visitors" in visitor_df.columns else 0
        total_page_views = int(visitor_df["page_views"].sum()) if not visitor_df.empty and "page_views" in visitor_df.columns else 0
        total_sec_clicks = int(sec_summary["clicks"].sum())
        total_ban_clicks = int(banner_summary["clicks"].sum())
        active_sections  = int((sec_summary["clicks"] > 0).sum())

        visitor_label = "순 방문자" if page_config["page_name"] == "home" else "콘텐츠 노출 유저"
        pv_label = "페이지뷰" if page_config["page_name"] == "home" else "콘텐츠 노출 이벤트"

        k1, k2, k3, k4, k5 = st.columns(5)
        kpi_card(k1, f"{page_config['label']} {visitor_label}", total_visitors, "명", accent)
        kpi_card(k2, pv_label, total_page_views, "회", C_PURPLE)
        kpi_card(k3, "섹션 총 클릭", total_sec_clicks, "회", C_ORANGE)
        kpi_card(k4, "배너 총 클릭", total_ban_clicks, "회", C_RED)
        kpi_card(k5, "클릭 발생 섹션 수", active_sections, "개", C_GREEN)

        st.markdown("---")

        cl, cr = st.columns(2)

        with cl:
            st.markdown(f"**일별 {page_config['label']} 방문자 추이**")
            if not visitor_df.empty and "event_date" in visitor_df.columns:
                vd = visitor_df.copy()
                vd["event_date"] = pd.to_datetime(vd["event_date"])
                vd = vd.sort_values("event_date")
                fig = px.area(
                    vd, x="event_date", y="unique_visitors",
                    labels={"event_date": "날짜", "unique_visitors": visitor_label},
                    color_discrete_sequence=[accent],
                )
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("방문자 데이터가 없습니다.")

        with cr:
            st.markdown("**일별 섹션 클릭 합계 추이**")
            if not sec_click_df.empty and "event_date" in sec_click_df.columns:
                dc = sec_click_df.groupby("event_date")["clicks"].sum().reset_index()
                dc["event_date"] = pd.to_datetime(dc["event_date"])
                dc = dc.sort_values("event_date")
                fig2 = px.bar(
                    dc, x="event_date", y="clicks",
                    labels={"event_date": "날짜", "clicks": "클릭 수"},
                    color_discrete_sequence=[C_ORANGE],
                )
                fig2.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("섹션 클릭 데이터가 없습니다.")

        st.markdown("---")

        cl2, cr2 = st.columns(2)

        with cl2:
            st.markdown("**섹션 유형(elementType)별 클릭 비중**")
            if "elementType" in sec_summary.columns:
                type_agg = (
                    sec_summary.groupby("elementType")["clicks"]
                    .sum().reset_index().query("clicks > 0")
                )
                if not type_agg.empty:
                    fig_pie = px.pie(
                        type_agg, names="elementType", values="clicks", hole=0.45,
                        color_discrete_sequence=px.colors.qualitative.Set2,
                    )
                    fig_pie.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
                    st.plotly_chart(fig_pie, use_container_width=True)

        with cr2:
            st.markdown("**섹션 클릭 TOP 5**")
            top5 = sec_summary.nlargest(5, "clicks")[["memo", "elementType", "clicks", "CTR(%)"]].copy()
            top5.columns = ["섹션명", "타입", "클릭", "CTR(%)"]
            st.dataframe(top5, use_container_width=True, hide_index=True)

        if src == "live":
            with st.expander("데이터 측정 방식 안내"):
                click_note = f"page_name='{page_config['page_name']}'"
                visit_note = (
                    f"event='{page_config['view_event']}'" +
                    (f", page_name='{page_config['view_page_name']}'" if page_config.get('view_page_name') else "")
                )
                st.markdown(
                    f"- **클릭**: `click_content` 이벤트, {click_note} 조건으로 집계\n"
                    f"- **CTR**: 클릭 ÷ 페이지 방문자 ({visit_note})\n"
                    "- **배너**: 섹션 내 배너 순서(0번째, 1번째 ...)로 구분 (배너별 UUID 클릭 미수집)\n"
                    "- 데이터 기준: AWS Athena `bind_event_log_compacted` (KST 일자 기준)"
                )

    # ════════════════════════════════════════════
    # TAB 2 — 섹션별 분석
    # ════════════════════════════════════════════
    with tab2:
        render_section_drilldown(sec_summary, banner_summary, banner_pos_df, page_key=page_key)

        st.markdown("---")

        ca, cb = st.columns(2)

        with ca:
            st.markdown("**클릭 TOP 10 섹션**")
            t10 = sec_summary.nlargest(10, "clicks").copy()
            t10["label"] = t10.apply(
                lambda r: f"{r.get('memo', '')} ({r['section_id']})" if r.get("memo") else str(r["section_id"]),
                axis=1,
            )
            if t10["clicks"].sum() > 0:
                fig_bar = px.bar(
                    t10.sort_values("clicks"),
                    x="clicks", y="label", orientation="h",
                    labels={"clicks": "클릭 수", "label": "섹션"},
                    color="clicks", color_continuous_scale="Blues",
                )
                fig_bar.update_layout(
                    height=420, showlegend=False,
                    coloraxis_showscale=False,
                    margin=dict(l=0, r=0, t=0, b=0),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        with cb:
            st.markdown("**CTR TOP 10 섹션**")
            t10_ctr = sec_summary[sec_summary["clicks"] > 0].nlargest(10, "CTR(%)").copy()
            t10_ctr["label"] = t10_ctr.apply(
                lambda r: f"{r.get('memo', '')} ({r['section_id']})" if r.get("memo") else str(r["section_id"]),
                axis=1,
            )
            if not t10_ctr.empty:
                fig_ctr = px.bar(
                    t10_ctr.sort_values("CTR(%)"),
                    x="CTR(%)", y="label", orientation="h",
                    labels={"CTR(%)": "CTR (%)", "label": "섹션"},
                    color="CTR(%)", color_continuous_scale="Oranges",
                )
                fig_ctr.update_layout(
                    height=420, showlegend=False,
                    coloraxis_showscale=False,
                    margin=dict(l=0, r=0, t=0, b=0),
                )
                st.plotly_chart(fig_ctr, use_container_width=True)

        st.markdown("---")

        st.markdown("**섹션 효율 분포 (클릭 수 vs CTR)**")
        sc_df = sec_summary[sec_summary["clicks"] > 0].copy()
        sc_df["섹션명"] = sc_df.apply(
            lambda r: r.get("memo", str(r["section_id"])) or str(r["section_id"]), axis=1
        )
        if not sc_df.empty:
            fig_sc = px.scatter(
                sc_df,
                x="clicks", y="CTR(%)",
                size="clicks", size_max=50,
                text="섹션명", color="elementType",
                labels={"clicks": "클릭 수", "CTR(%)": "CTR (%)"},
                hover_data={"section_id": True},
                color_discrete_sequence=px.colors.qualitative.Set1,
            )
            fig_sc.update_traces(textposition="top center", textfont_size=9)
            fig_sc.update_layout(height=420, margin=dict(l=0, r=0, t=0, b=0))
            st.plotly_chart(fig_sc, use_container_width=True)

        st.markdown("---")

        st.markdown("**섹션 일별 클릭 추이**")
        sel_secs = st.multiselect(
            "섹션 선택 (최대 5개)",
            section_labels,
            default=section_labels[:min(3, len(section_labels))],
            max_selections=5,
            key=f"sec_select_{page_key}",
        )

        if sel_secs and not sec_click_df.empty:
            trend_rows = []
            for lbl in sel_secs:
                uuid = label_to_uuid.get(lbl, "")
                t = get_daily_section(sec_click_df, uuid)
                if not t.empty:
                    t["섹션"] = lbl
                    trend_rows.append(t)
            if trend_rows:
                trend_all = pd.concat(trend_rows, ignore_index=True)
                fig_tr = px.line(
                    trend_all, x="event_date", y="clicks",
                    color="섹션",
                    labels={"event_date": "날짜", "clicks": "클릭 수"},
                    markers=True,
                )
                fig_tr.update_layout(height=360, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_tr, use_container_width=True)
        else:
            st.info("섹션을 선택하거나 기간 데이터가 없습니다.")

        st.markdown("---")
        render_section_perf_table(sec_summary)

    # ════════════════════════════════════════════
    # TAB 3 — 배너별 분석
    # ════════════════════════════════════════════
    with tab3:
        st.subheader("배너별 성과")
        st.caption(
            "배너는 각 섹션 내 노출 순서(1번, 2번 ...)로 구분됩니다. "
            "클릭 데이터는 해당 위치를 클릭한 횟수입니다."
        )

        b_show = banner_summary.copy()
        b_show["썸네일"] = b_show["imageUrl"].apply(img_html) if "imageUrl" in b_show.columns else "—"
        b_show["배너명"] = b_show.apply(
            lambda r: r.get("banner_title", "") or f"배너 {int(float(r.get('banner_orderIndex', 0)))}", axis=1
        )
        b_show["배너 순서"] = b_show.get("banner_orderIndex", pd.Series(dtype=str))
        b_show["섹션명"]   = b_show.get("section_memo", pd.Series(dtype=str))

        b_display_cols = ["썸네일", "배너명", "섹션명", "배너 순서", "clicks", "unique_users", "CTR(%)"]
        b_avail = [c for c in b_display_cols if c in b_show.columns]
        b_table = b_show[b_avail].copy()
        rename_b = {"clicks": "클릭 수", "unique_users": "순 클릭자", "CTR(%)": "CTR (%)"}
        b_table.columns = [rename_b.get(c, c) for c in b_table.columns]

        st.write(
            b_table.sort_values("클릭 수", ascending=False).to_html(
                escape=False, index=False, table_id="banner-table",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <style>
            #banner-table{
                border-collapse:separate; border-spacing:0;
                width:100%; font-size:0.85rem;
                background:#1F1F26; border-radius:12px; overflow:hidden;
                border:1px solid #2A2A33;
            }
            #banner-table th{
                background:#222B36; color:#C9CDD2; font-weight:600;
                padding:10px 12px; text-align:left;
                border-bottom:1px solid #2A2A33;
            }
            #banner-table td{
                padding:10px 12px; color:#F2F4F6;
                border-bottom:1px solid #2A2A33;
                vertical-align:middle;
            }
            #banner-table tr:last-child td{ border-bottom:none; }
            #banner-table tr:hover td{ background:#222B36; }
            #banner-table img{ border-radius:6px; }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        cc, cd = st.columns(2)

        with cc:
            st.markdown("**클릭 TOP 10 배너**")
            top_b = banner_summary.nlargest(10, "clicks").copy()
            top_b["label"] = top_b.apply(
                lambda r: (str(r.get("banner_title", "")) or f"배너#{r.get('banner_orderIndex','?')}")[:30],
                axis=1,
            )
            if top_b["clicks"].sum() > 0:
                fig_bc = px.bar(
                    top_b.sort_values("clicks"),
                    x="clicks", y="label", orientation="h",
                    labels={"clicks": "클릭 수", "label": "배너"},
                    color="clicks", color_continuous_scale="Reds",
                )
                fig_bc.update_layout(
                    height=420, showlegend=False,
                    coloraxis_showscale=False,
                    margin=dict(l=0, r=0, t=0, b=0),
                )
                st.plotly_chart(fig_bc, use_container_width=True)

        with cd:
            st.markdown(f"**{page_config['label']} 배너 섹션 — 위치별 클릭 수**")
            # 첫 번째 배너 섹션 사용
            first_banner_sec = banner_summary[banner_summary["banner_count"].fillna(0).astype(int) > 0] if "banner_count" in banner_summary.columns else pd.DataFrame()
            if not first_banner_sec.empty:
                first_uuid = first_banner_sec.iloc[0]["section_uuid"]
            else:
                first_uuid = banner_summary["section_uuid"].iloc[0] if not banner_summary.empty else ""

            hb = banner_summary[
                banner_summary["section_uuid"] == first_uuid
            ].copy() if first_uuid else pd.DataFrame()

            if not hb.empty and hb["clicks"].sum() > 0:
                hb = hb.sort_values("banner_orderIndex").copy() if "banner_orderIndex" in hb.columns else hb
                hb["위치"] = hb.get("banner_orderIndex", hb.get("banner_idx", "?")).astype(str) + "번째"
                fig_hb = px.bar(
                    hb, x="위치", y="clicks",
                    labels={"위치": "배너 위치", "clicks": "클릭 수"},
                    color="clicks", color_continuous_scale="RdYlGn",
                    text="clicks",
                )
                fig_hb.update_traces(texttemplate="%{text:,}", textposition="outside")
                fig_hb.update_layout(
                    height=420, coloraxis_showscale=False,
                    margin=dict(l=0, r=0, t=0, b=0),
                )
                st.plotly_chart(fig_hb, use_container_width=True)
            else:
                st.info("배너 섹션 데이터가 없습니다.")

        st.markdown("---")

        st.markdown("**배너 일별 클릭 추이**")
        sel_banners = st.multiselect(
            "배너 선택 (최대 5개)",
            b_labels,
            default=b_labels[:min(3, len(b_labels))],
            max_selections=5,
            key=f"banner_select_{page_key}",
        )

        if sel_banners and not banner_pos_df.empty:
            b_trend_rows = []
            for bl in sel_banners:
                suuid, bidx = b_label_to_meta.get(bl, ("", "0"))
                t = get_daily_banner(banner_pos_df, suuid, bidx)
                if not t.empty:
                    t["배너"] = bl
                    b_trend_rows.append(t)
            if b_trend_rows:
                b_trend_all = pd.concat(b_trend_rows, ignore_index=True)
                fig_bt = px.line(
                    b_trend_all, x="event_date", y="clicks",
                    color="배너",
                    labels={"event_date": "날짜", "clicks": "클릭 수"},
                    markers=True,
                )
                fig_bt.update_layout(height=360, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_bt, use_container_width=True)
        else:
            st.info("배너를 선택하거나 기간 데이터가 없습니다.")

    # ════════════════════════════════════════════
    # TAB 4 — 상세 비교
    # ════════════════════════════════════════════
    with tab4:
        st.subheader("섹션 / 배너 상세 비교")

        comp_type = st.radio("비교 단위", ["섹션", "배너"], horizontal=True, key=f"comp_radio_{page_key}")

        if comp_type == "섹션":
            options  = section_labels
            meta_map = label_to_uuid
            agg_df   = sec_summary.copy()
            agg_df["__uuid"] = agg_df["section_uuid"]
            trend_fn = lambda label: get_daily_section(sec_click_df, meta_map.get(label, ""))
        else:
            options  = b_labels
            meta_map = b_label_to_meta
            agg_df   = banner_summary.copy()
            agg_df["__uuid"] = agg_df["banner_uuid"]
            trend_fn = lambda label: get_daily_banner(banner_pos_df, *b_label_to_meta.get(label, ("", "0")))

        selected = st.multiselect(
            f"{comp_type} 선택 (최대 10개)",
            options,
            default=options[:min(5, len(options))],
            max_selections=10,
            key=f"comp_select_{page_key}",
        )

        if selected:
            st.markdown("**집계 비교**")
            rows = []
            for lbl in selected:
                if comp_type == "섹션":
                    uuid = meta_map.get(lbl, "")
                    row = agg_df[agg_df["section_uuid"] == uuid]
                else:
                    suuid, bidx = meta_map.get(lbl, ("", "0"))
                    row = agg_df[
                        (agg_df["section_uuid"] == suuid) &
                        (agg_df["banner_idx"].astype(str) == str(bidx))
                    ] if "section_uuid" in agg_df.columns else pd.DataFrame()
                if not row.empty:
                    r = row.iloc[0]
                    rows.append({
                        comp_type: lbl,
                        "클릭 수": int(r.get("clicks", 0)),
                        "순 클릭자": int(r.get("unique_users", 0)),
                        "CTR (%)": float(r.get("CTR(%)", 0) or 0),
                    })

            comp_table = pd.DataFrame(rows)
            if not comp_table.empty:
                st.dataframe(comp_table, use_container_width=True, hide_index=True)

                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(
                    name="클릭 수",
                    x=comp_table[comp_type],
                    y=comp_table["클릭 수"],
                    marker_color=accent, yaxis="y",
                ))
                fig_comp.add_trace(go.Scatter(
                    name="CTR (%)",
                    x=comp_table[comp_type],
                    y=comp_table["CTR (%)"],
                    mode="lines+markers",
                    marker=dict(size=9, color=C_ORANGE),
                    yaxis="y2",
                ))
                fig_comp.update_layout(
                    barmode="group",
                    yaxis=dict(title="클릭 수"),
                    yaxis2=dict(title="CTR (%)", overlaying="y", side="right"),
                    height=420,
                    legend=dict(orientation="h", y=1.05),
                    margin=dict(l=0, r=0, t=30, b=0),
                )
                st.plotly_chart(fig_comp, use_container_width=True)

            st.markdown("**일별 클릭 추이 비교**")
            trend_rows_comp = []
            for lbl in selected:
                t = trend_fn(lbl)
                if not t.empty:
                    t["항목"] = lbl
                    trend_rows_comp.append(t)

            if trend_rows_comp:
                all_trend = pd.concat(trend_rows_comp, ignore_index=True)
                fig_ct = px.line(
                    all_trend, x="event_date", y="clicks",
                    color="항목",
                    labels={"event_date": "날짜", "clicks": "클릭 수"},
                    markers=True,
                )
                fig_ct.update_layout(height=380, margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig_ct, use_container_width=True)
            else:
                st.info("선택된 항목의 일별 데이터가 없습니다.")

        st.markdown("---")

        st.markdown("**데이터 내보내기**")
        dl_target = st.selectbox("다운로드 대상", ["섹션 분석 결과", "배너 분석 결과"],
                                  key=f"dl_target_{page_key}")
        dl_df = sec_summary if dl_target == "섹션 분석 결과" else banner_summary
        buf = io.BytesIO()
        dl_df.to_csv(buf, index=False, encoding="utf-8-sig")
        st.download_button(
            label=f"{dl_target} CSV 다운로드",
            data=buf.getvalue(),
            file_name=f"{page_config['label']}_{dl_target.replace(' ', '_')}_{start_date}_{end_date}.csv",
            mime="text/csv",
            key=f"dl_btn_{page_key}",
        )

    # 푸터
    st.markdown("---")
    data_label = "실시간 Redash" if src == "live" else "샘플(데모)"
    st.caption(
        f"athler {page_config['label']} 영역 대시보드 | "
        f"page_uuid: {page_config['page_uuid']} | "
        f"데이터: {data_label} | 이벤트 테이블: bind_event_log_compacted (Athena)"
    )


# ──────────────────────────────────────────────
# 11. 엔트리 포인트 (홈 페이지)
# Streamlit이 app.py를 직접 실행하면 __name__ == "__main__".
# pages/ 파일에서 from app import 할 때는 __name__ == "app" (모듈명).
# ──────────────────────────────────────────────
if __name__ == "__main__":
    init_page(PAGE_HOME)
    render_dashboard(PAGE_HOME)
