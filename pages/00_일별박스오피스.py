import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import plotly.express as px

st.set_page_config(page_title="박스오피스 & BEP 분석 대시보드", layout="wide")
st.title("🎬 박스오피스 & 손익분기점(BEP) 흥행 분석")

# 비밀 금고에서 인증키 꺼내기
KOBIS_KEY = st.secrets.get("KOBIS_KEY", "")

# 한국 시간 기준 어제 날짜
yesterday = datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")
st.caption(f"📅 조회 기준일: {yesterday.strftime('%Y-%m-%d')}")

if not KOBIS_KEY:
    st.error("KOBIS_KEY가 설정되지 않았습니다. st.secrets에 등록해주세요.")
    st.stop()

# KOBIS API 데이터 호출
url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. Secrets의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("데이터가 없습니다. 날짜를 확인해주세요.")
    st.stop()

df = pd.DataFrame(box_list)

# 숫자 데이터 형변환
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])

# ==========================================
# 🎯 손익분기점(BEP) 추정 데이터 매핑 (단위: 명)
# ==========================================
KNOWN_BEP = {
    "파묘": 3300000,
    "범죄도시4": 3500000,
    "베테랑2": 4000000,
    "하얼빈": 7500000,
    "왕과 사는 남자": 3000000,
    "살목지": 800000,
    "오늘 밤, 세계에서 이 사랑이 사라진다 해도": 720000,
}

# 기본 BEP 값
DEFAULT_BEP = 2000000

# DataFrame에 BEP 관객수 및 달성률 추가
df["bep_audi"] = df["movieNm"].map(KNOWN_BEP).fillna(DEFAULT_BEP)
df["bep_rate"] = (df["audiAcc"] / df["bep_audi"]) * 100

# 1위 영화 지표 카드
top = df.sort_values("rank").iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("어제 1위", top["movieNm"])
c2.metric("어제 관객수", f"{top['audiCnt']:,}명")
c3.metric("누적 관객수", f"{top['audiAcc']:,}명")

top_bep_status = "🎉 손익분기점 돌파!" if top["bep_rate"] >= 100 else f"{top['bep_rate']:.1f}% 달성"
c4.metric("BEP 달성률", f"{top['bep_rate']:.1f}%", delta=top_bep_status)

st.divider()

# ==========================================
# 📊 손익분기점(BEP) 흥행 성공률 시각화
# ==========================================
st.subheader("🎯 박스오피스 TOP 10 손익분기점(BEP) 달성 현황")

# 상위 10개 영화 데이터 정리
top10 = df.sort_values("rank").head(10).copy()

# 시각화용 보조 컬럼 생성 (만 명 단위로 변환 후 소수 첫째 자리 포맷)
top10["bep_status"] = top10["bep_rate"].apply(
    lambda x: "🎉 돌파 완료" if x >= 100 else ("📈 50% 이상 달성" if x >= 50 else "⚠️ 50% 미만")
)
top10["bep_audi_萬"] = (top10["bep_audi"] / 10000).round(1)
top10["audiAcc_萬"] = (top10["audiAcc"] / 10000).round(1)
top10["bep_rate_round"] = top10["bep_rate"].round(1)

# Plotly 가로 바 차트 (소수 첫째 자리 표기)
fig = px.bar(
    top10,
    x="audiAcc_萬",
    y="movieNm",
    orientation="h",
    color="bep_status",
    color_discrete_map={
        "🎉 돌파 완료": "#2ecc71",
        "📈 50% 이상 달성": "#f1c40f",
        "⚠️ 50% 미만": "#e74c3c"
    },
    text_auto=".1f", # 차트 바 안의 숫자를 소수 첫째 자리로 설정
    title="영화별 누적 관객 수 vs 손익분기점 (단위: 만 명)",
    labels={"movieNm": "영화 제목", "audiAcc_萬": "누적 관객 수 (만 명)", "bep_status": "달성 상태"}
)

fig.update_layout(
    yaxis={'categoryorder': 'total ascending'},
    xaxis_title="누적 관객 수 (만 명)",
    height=450
)

st.plotly_chart(fig, use_container_width=True)

# 카드 형태의 프로그레스 바 표시
st.subheader("📌 영화별 흥행 달성률 상세")
cols = st.columns(2)

for idx, row in top10.reset_index(drop=True).iterrows():
    col_idx = idx % 2
    with cols[col_idx]:
        rate = min(row["bep_rate"], 100.0) / 100.0
        status_emoji = "🎉" if row["bep_rate"] >= 100 else "🎬"
        
        st.markdown(f"**{status_emoji} {row['movieNm']}**")
        st.caption(
            f"누적 {row['audiAcc_萬']:.1f}만 명 / 목표 BEP {row['bep_audi_萬']:.1f}만 명 "
            f"**(달성률: {row['bep_rate']:.1f}%)**"
        )
        st.progress(rate)

st.divider()

# ==========================================
# 📋 상세 요약 데이터 프레임
# ==========================================
st.subheader("📋 상세 데이터 및 BEP 현황")
st.info("💡 KOBIS에서 제공하지 않는 손익분기점 정보는 사전 설정된 추정값을 사용합니다.")

table = top10[[
    "rank", "movieNm", "openDt", "audiCnt", "audiAcc_萬", "bep_audi_萬", "bep_rate_round"
]].copy()

table.columns = ["순위", "영화명", "개봉일", "어제관객(명)", "누적관객(만 명)", "목표BEP(만 명)", "달성률(%)"]

# 표 안의 모든 실수값을 소수 첫째 자리 포맷팅 적용
st.dataframe(
    table.style.format({
        "누적관객(만 명)": "{:.1f}",
        "목표BEP(만 명)": "{:.1f}",
        "달성률(%)": "{:.1f}"
    }).highlight_between(left=100.0, right=99999.0, subset=["달성률(%)"], color="#d4edda"),
    use_container_width=True
)
