# -*- coding: utf-8 -*-
"""
전국 시군구별 고령화 지도
- 65세 이상 인구 비율(고령화율)을 시군구 단위 단계구분도로 표시합니다.
- 인구 데이터(읍·면·동 단위)를 시군구 단위로 합쳐서 계산합니다.
"""

import json

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(page_title="전국 고령화 지도", layout="wide")

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
)
GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
)

# 구간 경계값 (전국 시군구를 실제 값 기준으로 5개 그룹으로 나눈 값)
BINS = [-np.inf, 19, 23, 28, 38, np.inf]
BIN_LABELS = ["19% 미만", "19~23%", "23~28%", "28~38%", "38% 이상"]

# 낮은 값은 옅게, 높은 값은 진하게 (파란색 계열 5단계)
BIN_COLORS = ["#eff3ff", "#bdd7e7", "#6baed6", "#3182bd", "#08519c"]
COLOR_MAP = dict(zip(BIN_LABELS, BIN_COLORS))


# -----------------------------
# 데이터 불러오기 (캐시로 속도 향상)
# -----------------------------
@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    # '코드'는 행정동 코드(10자리)이므로 숫자가 아니라 문자열로 읽어야
    # 앞자리 0이 사라지지 않습니다.
    df = pd.read_csv(POPULATION_URL, compression="gzip", dtype={"코드": str})
    return df


@st.cache_data(show_spinner="지도 경계 데이터를 불러오는 중...")
def load_geojson():
    res = requests.get(GEOJSON_URL, timeout=30)
    res.raise_for_status()
    return res.json()


# -----------------------------
# 나이별 인구 합산 (계_0세 ~ 계_100세 이상)
# -----------------------------
def get_total_and_elderly(df: pd.DataFrame):
    """'계_'로 시작하는 나이별 열을 찾아 전체 인구와 65세 이상 인구를 계산합니다."""
    age_cols = [
        c for c in df.columns
        if c.startswith("계_") and (c.endswith("세") or "이상" in c)
    ]

    elderly_cols = []
    for c in age_cols:
        # '계_65세' -> '65', '계_100세 이상' -> '100'
        age_str = c.replace("계_", "").replace("이상", "").replace("세", "").strip()
        try:
            age = int(age_str)
        except ValueError:
            continue
        if age >= 65:
            elderly_cols.append(c)

    total = df[age_cols].sum(axis=1)
    elderly = df[elderly_cols].sum(axis=1)
    return total, elderly


# -----------------------------
# 데이터 처리
# -----------------------------
pop_df = load_population()
geojson = load_geojson()

# 가장 최신 연도 찾기
latest_year = pop_df["연도"].max()
year_df = pop_df[pop_df["연도"] == latest_year].copy()

# 읍·면·동 단위 전체 인구 / 65세 이상 인구 계산
year_df["전체인구"], year_df["고령인구"] = get_total_and_elderly(year_df)

# '코드' 앞 5자리 = 시군구 코드
year_df["시군구코드"] = year_df["코드"].str[:5]

# 읍·면·동 -> 시군구 단위로 합산
sigungu_df = (
    year_df.groupby("시군구코드")
    .agg(
        시도=("시도", "first"),
        시군구=("시군구", "first"),
        전체인구=("전체인구", "sum"),
        고령인구=("고령인구", "sum"),
    )
    .reset_index()
)

# 고령화율(%) 계산
sigungu_df["고령화율"] = (sigungu_df["고령인구"] / sigungu_df["전체인구"]) * 100

# 5단계 구간 나누기 (범례용 문자열 구간)
sigungu_df["구간"] = pd.cut(
    sigungu_df["고령화율"], bins=BINS, labels=BIN_LABELS, right=False
)

# -----------------------------
# 화면 구성
# -----------------------------
st.title("🗺️ 전국 시군구별 고령화 지도")
st.caption(f"기준 연도: {latest_year}년 · 고령화율 = 65세 이상 인구 ÷ 전체 인구 × 100")

fig = px.choropleth(
    sigungu_df,
    geojson=geojson,
    locations="시군구코드",
    featureidkey="properties.코드",
    color="구간",
    category_orders={"구간": BIN_LABELS},
    color_discrete_map=COLOR_MAP,
    custom_data=["시군구", "시도", "고령화율"],
)

# 마우스를 올렸을 때 시군구 이름 · 시도 · 고령화율(%) 표시
fig.update_traces(
    hovertemplate=(
        "<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
        "고령화율: %{customdata[2]:.1f}%"
        "<extra></extra>"
    ),
    marker_line_color="#555555",
    marker_line_width=0.5,
)

# 배경 지도(타일) 없이 경계선만 보이도록 설정
fig.update_geos(
    visible=False,
    fitbounds="locations",
)

fig.update_layout(
    legend_title_text="고령화율 구간",
    margin=dict(l=0, r=0, t=10, b=0),
    height=700,
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# 상위 10 / 하위 10 표
# -----------------------------
st.subheader("고령화율 상위·하위 10개 시군구")

col1, col2 = st.columns(2)

top10 = (
    sigungu_df.sort_values("고령화율", ascending=False)
    .head(10)[["시도", "시군구", "고령화율"]]
    .reset_index(drop=True)
)
top10.index = top10.index + 1
top10["고령화율"] = top10["고령화율"].round(1).astype(str) + "%"

bottom10 = (
    sigungu_df.sort_values("고령화율", ascending=True)
    .head(10)[["시도", "시군구", "고령화율"]]
    .reset_index(drop=True)
)
bottom10.index = bottom10.index + 1
bottom10["고령화율"] = bottom10["고령화율"].round(1).astype(str) + "%"

with col1:
    st.markdown("**고령화율 높은 지역 TOP 10**")
    st.table(top10)

with col2:
    st.markdown("**고령화율 낮은 지역 TOP 10**")
    st.table(bottom10)
