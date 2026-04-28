# athler 홈/아울렛 영역 대시보드

athler.kr 홈 페이지와 아울렛 페이지의 섹션·배너 클릭 분석 Streamlit 대시보드.

## 페이지 구성
- **홈** (`app.py`): athler.kr/home 분석
- **아울렛** (`pages/1_outlet.py`): athler.kr/home-outlet 분석
- 두 페이지는 제목 클릭 또는 우측 버튼으로 서로 이동 가능

## 데이터 소스
- **클릭 / 노출**: AWS Athena (`bind-event-logs.bind_event_log_compacted`)를 Redash API 경유 조회
- **섹션 / 배너 메타**: athler.kr API에서 한 번 추출한 CSV (`data/sections.csv`, `data/banners.csv`, `data/outlet_*.csv`)
  - 우측 상단 "🔄 메타 새로고침" 버튼으로 갱신 (로컬 환경에서 작동)

## 로컬 실행

```
pip install -r requirements.txt
streamlit run app.py
```

`.env.local` 파일에 다음을 작성:
```
REDASH_URL=http://52.79.76.239
REDASH_API_KEY=<API_KEY>
```

## Streamlit Community Cloud 배포

1. 이 repo를 GitHub에 push
2. https://streamlit.io/cloud 에 GitHub 계정으로 로그인
3. **New app** → 이 repo 선택 → **Main file path**: `app.py`
4. **Advanced settings** → **Secrets** 에 다음 입력:
   ```
   REDASH_URL = "http://52.79.76.239"
   REDASH_API_KEY = "여기에-API-키"
   ```
5. **Deploy** 클릭

배포 후 대시보드는 항상 켜져 있으며, 코드 push 시 자동 재배포.

## 한계점
- **노출(impression) 데이터 없음**: 섹션/배너 노출 이벤트가 수집되지 않아 CTR은 "페이지 방문자 대비 클릭률"로 근사.
- **배너 단위 식별**: 로그에 `banner_uuid`가 없고 섹션 내 순서(idx)만 기록됨.
- **메타 새로고침 (Playwright)**: Streamlit Cloud 환경에서는 작동 안 할 수 있음. 메타 갱신이 필요하면 로컬에서 실행 후 CSV 커밋.
