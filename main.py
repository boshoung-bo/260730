# -*- coding: utf-8 -*-
"""
천안 vs 아산 인구 비교 (2015년~2026년)
- 같은 인구 데이터(population_yearly.csv.gz)를 사용합니다.
- 천안시는 '천안시 동남구' + '천안시 서북구' 두 개 시군구로 나뉘어 있어서
  두 구를 합쳐서 '천안'으로 계산합니다.
- 아산시는 '아산시' 하나로 되어 있습니다.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="천안 vs 아산 인구 비교", layout="wide")

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
)


# -----------------------------
# 데이터 불러오기
# -----------------------------
@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    # '코드'는 숫자가 아니라 이름표이므로 문자열로 읽습니다.
    df = pd.read_csv(POPULATION_URL, compression="gzip", dtype={"코드": str})
    return df


def get_total_population(df: pd.DataFrame) -> pd.Series:
    """'계_'로 시작하는 나이별 열을 모두 더해서 전체 인구를 구합니다."""
    age_cols = [
        c for c in df.columns
        if c.startswith("계_") and (c.endswith("세") or "이상" in c)
    ]
    return df[age_cols].sum(axis=1)


pop_df = load_population()

# 전체 인구 열 추가 (읍·면·동 단위)
pop_df["전체인구"] = get_total_population(pop_df)

# -----------------------------
# 천안 / 아산 데이터만 뽑기
# -----------------------------
# 천안시 동남구 + 천안시 서북구 -> '천안'으로 묶기
# 아산시 -> '아산'으로 묶기
def to_city(sigungu):
    # 시군구 값이 비어있는(NaN) 행이 있을 수 있어서 먼저 걸러줍니다.
    if pd.isna(sigungu):
        return None
    sigungu = str(sigungu)
    if "천안" in sigungu:
        return "천안"
    if "아산" in sigungu:
        return "아산"
    return None


pop_df["도시"] = pop_df["시군구"].apply(to_city)
target_df = pop_df[pop_df["도시"].isin(["천안", "아산"])].copy()

# 연도 · 도시별로 읍·면·동 인구를 합산
yearly_df = (
    target_df.groupby(["연도", "도시"])["전체인구"]
    .sum()
    .reset_index()
    .sort_values(["도시", "연도"])
)

# 2015~2026년 범위만 사용
yearly_df = yearly_df[(yearly_df["연도"] >= 2015) & (yearly_df["연도"] <= 2026)]

# -----------------------------
# 화면 구성
# -----------------------------
st.title("🏙️ 천안 vs 아산 인구 비교 (2015~2026년)")
st.caption("천안시는 동남구·서북구를 합친 값입니다.")

# 1) 선 그래프: 연도별 인구 추이
fig_line = px.line(
    yearly_df,
    x="연도",
    y="전체인구",
    color="도시",
    markers=True,
    labels={"연도": "연도", "전체인구": "인구(명)", "도시": "도시"},
    title="연도별 인구 추이",
)
fig_line.update_layout(
    hovermode="x unified",
    yaxis_tickformat=",",
    margin=dict(l=0, r=0, t=50, b=0),
)
st.plotly_chart(fig_line, use_container_width=True)

# 2) 막대 그래프: 연도별 두 도시 인구 나란히 비교
fig_bar = px.bar(
    yearly_df,
    x="연도",
    y="전체인구",
    color="도시",
    barmode="group",
    labels={"연도": "연도", "전체인구": "인구(명)", "도시": "도시"},
    title="연도별 인구 비교(막대)",
)
fig_bar.update_layout(
    yaxis_tickformat=",",
    margin=dict(l=0, r=0, t=50, b=0),
)
st.plotly_chart(fig_bar, use_container_width=True)

# 3) 최신 연도 기준 인구차 요약
latest_year = yearly_df["연도"].max()
latest = yearly_df[yearly_df["연도"] == latest_year].set_index("도시")["전체인구"]

col1, col2, col3 = st.columns(3)
col1.metric(f"천안 인구 ({latest_year}년)", f"{latest.get('천안', 0):,.0f}명")
col2.metric(f"아산 인구 ({latest_year}년)", f"{latest.get('아산', 0):,.0f}명")
diff = latest.get("천안", 0) - latest.get("아산", 0)
col3.metric("천안 - 아산 인구차", f"{diff:,.0f}명")

# 4) 표로 전체 데이터 보기
st.subheader("연도별 인구 표")
pivot_df = yearly_df.pivot(index="연도", columns="도시", values="전체인구")
pivot_df = pivot_df.round(0).astype("Int64")
st.dataframe(pivot_df, use_container_width=True)
