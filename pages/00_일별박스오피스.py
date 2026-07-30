import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 어제의 박스오피스")

# 비밀 금고에서 인증키 꺼내기 (코드에는 키를 적지 않는다)
KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 한국 시간 기준 어제 날짜를 여덟 자리로 (배포 서버 시계는 외국 기준일 수 있다)
yesterday = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")
st.caption(f"조회 기준일(어제): {yesterday.strftime('%Y-%m-%d')}")

url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

# KOBIS는 키가 틀려도 상태코드 200을 준다. 대신 faultInfo 상자가 온다.
if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("그날 자료가 없습니다. 날짜를 하루 더 앞으로 옮겨 보세요.")
    st.stop()

df = pd.DataFrame(box_list)

# 글자로 온 숫자들을 진짜 숫자로 바꾸기
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])

# 1위 영화 지표 카드 세 장
top = df.sort_values("rank").iloc[0]
c1, c2, c3 = st.columns(3)
c1.metric("어제 1위", top["movieNm"])
c2.metric("어제 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객", f"{top['audiAcc']:,}명")

# 표를 한국어 열 이름으로 정리
table = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
table.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
table = table.sort_values("순위").reset_index(drop=True)

st.subheader("📋 박스오피스 TOP 10")
st.dataframe(table)

st.subheader("📈 관객수 상위 5편")
top5 = table.sort_values("관객수", ascending=False).head(5)
st.bar_chart(top5.set_index("영화명")["관객수"])


# ─────────────────────────────────────────────────────────────
# 💰 현재 상영작 손익분기점(BEP) & 흥행 성공률
# ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("💰 현재 상영작 손익분기점(BEP) & 흥행 성공률")

st.info(
    "KOBIS 오픈API는 영화별 실제 제작비(총 제작+마케팅비)를 제공하지 않습니다. "
    "아래 표에 제작비(순제작비+마케팅비 합산, 단위: 억원)를 직접 입력하면, "
    "평균 티켓 가격과 배급/투자사 정산율을 가정하여 BEP 관객수와 흥행 성공률을 추정합니다. "
    "결과는 참고용 추정치이며 실제 손익과 다를 수 있습니다."
)

# 사이드바에서 계산 가정치 조절
with st.sidebar:
    st.header("⚙️ BEP 계산 가정치")
    ticket_price = st.number_input(
        "평균 티켓 가격(원)", min_value=1000, max_value=30000, value=11000, step=500
    )
    settlement_rate = st.slider(
        "제작/투자사 정산율(%)",
        min_value=10, max_value=90, value=50, step=5,
        help="극장/배급사 수수료를 제외하고 제작·투자사가 실제로 배분받는 비율입니다.",
    )
    st.caption("실제 값은 영화·배급 계약마다 다릅니다. 필요에 맞게 조절하세요.")

# BEP 계산용 입력 테이블 준비 (기본 제작비 0 → 사용자가 직접 입력)
bep_base = table[["순위", "영화명", "누적관객"]].copy()
bep_base["제작비(억원)"] = 0.0

edited = st.data_editor(
    bep_base,
    column_config={
        "제작비(억원)": st.column_config.NumberColumn(
            "제작비(억원)", min_value=0.0, step=1.0, format="%.1f"
        )
    },
    disabled=["순위", "영화명", "누적관객"],
    hide_index=True,
    use_container_width=True,
    key="bep_editor",
)

has_budget = edited["제작비(억원)"] > 0

if not has_budget.any():
    st.warning("위 표에 제작비(억원)를 1편 이상 입력하면 BEP와 흥행 성공률이 계산됩니다.")
else:
    bep_df = edited[has_budget].copy()

    # 순수익 배분 기준 1인당 회수 단가
    net_per_admission = ticket_price * (settlement_rate / 100)

    # BEP 관객수 = 제작비(원) / 1인당 회수 단가
    bep_df["BEP 관객수"] = (bep_df["제작비(억원)"] * 100_000_000) / net_per_admission
    bep_df["BEP 관객수"] = bep_df["BEP 관객수"].round(0).astype(int)

    # 흥행 성공률(%) = 누적관객 / BEP 관객수 * 100
    bep_df["흥행 성공률(%)"] = (bep_df["누적관객"] / bep_df["BEP 관객수"] * 100).round(1)
    bep_df["상태"] = bep_df["흥행 성공률(%)"].apply(
        lambda x: "✅ 손익분기 돌파" if x >= 100 else "🔻 미달"
    )

    st.markdown("#### 📊 영화별 BEP 대비 흥행 성공률")

    for _, row in bep_df.sort_values("흥행 성공률(%)", ascending=False).iterrows():
        progress_value = min(row["흥행 성공률(%)"] / 100, 1.0)
        label = (
            f"**{row['영화명']}** · 누적 {row['누적관객']:,}명 / "
            f"BEP {row['BEP 관객수']:,}명 · {row['흥행 성공률(%)']}% · {row['상태']}"
        )
        st.write(label)
        st.progress(progress_value)

    st.markdown("#### 📋 상세 표")
    display_cols = ["영화명", "제작비(억원)", "BEP 관객수", "누적관객", "흥행 성공률(%)", "상태"]
    st.dataframe(bep_df[display_cols].reset_index(drop=True), use_container_width=True)

    st.markdown("#### 📈 누적관객 vs BEP 관객수 비교")
    chart_df = bep_df.set_index("영화명")[["누적관객", "BEP 관객수"]]
    st.bar_chart(chart_df)
