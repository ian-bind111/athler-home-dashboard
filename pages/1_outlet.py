# -*- coding: utf-8 -*-
"""
athler 아울렛 영역 대시보드 (멀티페이지 - 2번 페이지)
page_uuid: ca14a954-d190-464a-a77b-1cbfcf8c042e
page_name (이벤트 로그): 'outlet'
"""

import os
import sys
from pathlib import Path

# app.py가 있는 부모 디렉토리를 sys.path에 추가 (공용 모듈 import용)
_parent = str(Path(__file__).parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)


# .env.local 로드 (app.py import 전에 먼저)
def _load_env_local():
    env_path = Path(__file__).parent.parent / ".env.local"
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

import streamlit as st

# app.py에서 공용 함수/상수 임포트
# (app.py는 모듈 레벨에서 streamlit 호출을 하지 않으므로 import 시 부작용 없음)
from app import init_page, render_dashboard, PAGE_OUTLET

# 페이지 초기화 (set_page_config + 글로벌 CSS)
init_page(PAGE_OUTLET)

# 아울렛 페이지에서만 CSS가 일부 누락되는 이슈가 있어
# Material Symbols 폰트를 한 번 더 직접 주입 (홈에서는 init_page 만으로 OK)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined');
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
    </style>
    """,
    unsafe_allow_html=True,
)

# 아울렛 대시보드 렌더링
render_dashboard(PAGE_OUTLET)
