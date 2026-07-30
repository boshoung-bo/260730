# -*- coding: utf-8 -*-
"""
천안 · 아산 지도 (2015년~2026년)
- 시군구 경계는 실제 GeoJSON 데이터를 사용합니다. (천안시 동남구 / 천안시 서북구 / 아산시)
- ⚠️ 읍·면·동 단위의 실제 경계선(폴리곤) 데이터는 제공되지 않습니다.
  그래서 읍·면·동은 각 시군구 영역 안에 원형으로 흩어 놓은 '위치 표시용 점'으로 표현합니다.
  (실제 동의 지리적 위치가 아니라 근사적인 표시입니다.)
- 지도에 마우스를 올리면 남/여, 아이(0~14세)/어른(15~64세)/노인(65세 이상) 인구를 보여줍니다.
"""

import math

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="천안·아산 인구 지도", layout="wide")

POPULATION_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
)
GEOJSON_URL = (
    "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"
)


# -----------------------------
# 데이터 불러오기
# -----------------------------
@st.cache_data(show_spinner="인구 데이터를 불러오는 중...")
def load_population():
    # '코드'는 숫자가 아니라 이름표이므로 문자열로 읽습니다.
    return pd.read_csv(POPULATION_URL, compression="gzip", dtype={"코드": str})


@st.cache_data(show_spinner="지도 경계 데이터를 불러오는 중...")
def load_geojson():
    res = requests.get(GEOJSON_URL, timeout=30)
    res.raise_for_status()
    return res.json()


def parse_age(col: str) -> int:
    """'계_65세' -> 65, '계_100세 이상' -> 100 처럼 열 이름에서 나이를 뽑아냅니다."""
    age_str = col.split("_", 1)[1].replace("이상", "").replace("세", "").strip()
    return int(age_str)


def add_demographics(df: pd.DataFrame) -> pd.DataFrame:
    """남/여, 아이(0~14)/어른(15~64)/노인(65+) 인구 열을 추가합니다."""
    male_cols = [c for c in df.columns if c.startswith("남_")]
    female_cols = [c for c in df.columns if c.startswith("여_")]
    total_cols = [c for c in df.columns if c.startswith("계_")]

    child_cols = [c for c in total_cols if parse_age(c) <= 14]
    adult_cols = [c for c in total_cols if 15 <= parse_age(c) <= 64]
    elderly_cols = [c for c in total_cols if parse_age(c) >= 65]

    df = df.copy()
    df["남"] = df[male_cols].sum(axis=1)
    df["여"] = df[female_cols].sum(axis=1)
    df["아이"] = df[child_cols].sum(axis=1)
    df["어른"] = df[adult_cols].sum(axis=1)
    df["노인"] = df[elderly_cols].sum(axis=1)
    df["전체인구"] = df["남"] + df["여"]
    return df


def to_city(sigungu):
    """시군구 이름을 보고 '천안' / '아산' / None 으로 분류합니다."""
    if pd.isna(sigungu):
        return None
    sigungu = str(sigungu)
    if "천안" in sigungu:
        return "천안"
    if "아산" in sigungu:
        return "아산"
    return None


def polygon_centroid(geometry: dict):
    """폴리곤(또는 멀티폴리곤) 좌표를 모두 모아 평균 좌표(대략적인 중심점)를 구합니다."""
    coords = []

    def walk(node):
        # 좌표 하나는 [경도, 위도] 형태 (숫자 두 개)
        if isinstance(node[0], (int, float)):
            coords.append(node)
        else:
            for child in node:
                walk(child)

    walk(geometry["coordinates"])
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lons) / len(lons), sum(lats) / len(lats)


# -----------------------------
# 데이터 준비
# -----------------------------
pop_df = load_population()
geojson = load_geojson()

pop_df["도시"] = pop_df["시군구"].apply(to_city)
target_df = pop_df[pop_df["도시"].isin(["천안", "아산"])].copy()
target_df = add_demographics(target_df)
target_df["시군구코드"] = target_df["코드"].str[:5]

st.title("🏙️ 천안 · 아산 인구 지도")
st.caption(
    "시군구 경계는 실제 지도이며, 읍·면·동은 시군구 안에 흩어 놓은 근사 표시입니다. "
    "마우스를 올리면 남/여, 아이(0~14세)/어른(15~64세)/노인(65세 이상) 인구가 보입니다."
)

# 연도 선택 (지도에 표시할 인구 기준 연도)
연도목록 = sorted(target_df["연도"].unique())
선택연도 = st.selectbox("연도 선택", 연도목록, index=len(연도목록) - 1)

year_df = target_df[target_df["연도"] == 선택연도]

# -----------------------------
# 시군구 단위 통계 (천안시 동남구 / 천안시 서북구 / 아산시)
# -----------------------------
sigungu_stats = (
    year_df.groupby(["시군구코드", "시군구", "시도", "도시"])[
        ["전체인구", "남", "여", "아이", "어른", "노인"]
    ]
    .sum()
    .reset_index()
)

target_codes = set(sigungu_stats["시군구코드"])

# 천안 · 아산에 해당하는 시군구 geojson feature만 골라내기
target_features = [
    f for f in geojson["features"] if f["properties"].get("코드") in target_codes
]
target_geojson = {"type": "FeatureCollection", "features": target_features}

# -----------------------------
# 시군구 폴리곤 중심점 계산 (읍·면·동 점을 뿌리기 위한 기준점)
# -----------------------------
centroids = {}
for f in target_features:
    code = f["properties"]["코드"]
    centroids[code] = polygon_centroid(f["geometry"])

# -----------------------------
# 읍·면·동 단위 통계 + 근사 좌표 부여
# -----------------------------
dong_stats = (
    year_df.groupby(["시군구코드", "시군구", "동", "도시"])[
        ["전체인구", "남", "여", "아이", "어른", "노인"]
    ]
    .sum()
    .reset_index()
)

lons, lats = [], []
for code, group in dong_stats.groupby("시군구코드"):
    center_lon, center_lat = centroids.get(code, (127.0, 36.5))
    n = len(group)
    for i in range(n):
        # 해바라기씨 배치(phyllotaxis)처럼 중심에서 조금씩 퍼지도록 점을 흩어 놓습니다.
        angle = i * 137.5 * math.pi / 180
        radius = 0.006 * math.sqrt(i + 1)
        lons.append(center_lon + radius * math.cos(angle))
        lats.append(center_lat + radius * math.sin(angle))

dong_stats = dong_stats.sort_values("시군구코드").reset_index(drop=True)
dong_stats["경도"] = lons
dong_stats["위도"] = lats

# -----------------------------
# 지도 그리기
# -----------------------------
fig = go.Figure()

# 1) 시군구 경계 (천안 동남구 / 천안 서북구 / 아산시)
sigungu_hover = [
    f"<b>{row['시군구']}</b> ({row['시도']})<br>"
    f"전체인구: {row['전체인구']:,.0f}명<br>"
    f"남: {row['남']:,.0f}명 · 여: {row['여']:,.0f}명<br>"
    f"아이: {row['아이']:,.0f}명 · 어른: {row['어른']:,.0f}명 · 노인: {row['노인']:,.0f}명"
    for _, row in sigungu_stats.iterrows()
]

fig.add_trace(
    go.Choropleth(
        geojson=target_geojson,
        locations=sigungu_stats["시군구코드"],
        z=[1] * len(sigungu_stats),  # 색은 도시 구분용으로만 사용 (수치 의미 없음)
        featureidkey="properties.코드",
        colorscale=[[0, "#deebf7"], [1, "#deebf7"]],
        showscale=False,
        marker_line_color="#555555",
        marker_line_width=1,
        text=sigungu_hover,
        hoverinfo="text",
        name="시군구",
    )
)

# 2) 읍·면·동 점 (근사 위치, 인구 규모에 따라 점 크기 변화)
dong_hover = [
    f"<b>{row['동']}</b> ({row['시군구']})<br>"
    f"전체인구: {row['전체인구']:,.0f}명<br>"
    f"남: {row['남']:,.0f}명 · 여: {row['여']:,.0f}명<br>"
    f"아이: {row['아이']:,.0f}명 · 어른: {row['어른']:,.0f}명 · 노인: {row['노인']:,.0f}명"
    for _, row in dong_stats.iterrows()
]

city_colors = {"천안": "#e6550d", "아산": "#2171b5"}

for city, color in city_colors.items():
    sub = dong_stats[dong_stats["도시"] == city]
    hover_sub = [dong_hover[i] for i in sub.index]
    fig.add_trace(
        go.Scattergeo(
            lon=sub["경도"],
            lat=sub["위도"],
            mode="markers",
            marker=dict(
                size=(sub["전체인구"].clip(lower=1)) ** 0.5 / 4,
                sizemin=3,
                color=color,
                line=dict(width=0.5, color="white"),
                opacity=0.85,
            ),
            text=hover_sub,
            hoverinfo="text",
            name=f"{city} 읍·면·동",
        )
    )

# 배경 지도 없이 경계선만, 천안·아산 영역으로 확대
fig.update_geos(
    visible=False,
    fitbounds="locations",
)
fig.update_layout(
    height=650,
    margin=dict(l=0, r=0, t=10, b=0),
    legend_title_text="",
)

st.plotly_chart(fig, use_container_width=True)

st.info(
    "점 하나가 읍·면·동 하나를 나타내며, 점 크기는 그 동의 인구 규모에 비례합니다. "
    "다만 점의 실제 위치는 시군구 안에서 임의로 배치한 것이라 지도상 정확한 동 위치는 아닙니다."
)
