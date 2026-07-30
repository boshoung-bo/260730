# -*- coding: utf-8 -*-
"""
천안 · 아산 인구 지도 (2015년~2026년)
- 시군구 경계는 실제 GeoJSON 데이터를 사용합니다. (천안시 동남구 / 천안시 서북구 / 아산시)
- 읍·면·동 위치는 OpenStreetMap의 무료 지오코딩 서비스(Nominatim)로 실제 좌표를
  찾아와서 표시합니다. (같은 이름이 다른 지역에도 있을 수 있어 100% 정확하지는
  않지만, 이전처럼 임의로 원을 그려 흩뿌리는 방식보다 실제 위치에 훨씬 가깝습니다.)
- 지도에 마우스를 올리면 남/여, 아이(0-19세)/어른(20-64세)/노인(65세 이상) 인구를 보여줍니다.
- 첫 실행 시 읍·면·동 위치를 하나씩 찾아오기 때문에(초당 1건, 예의상 서버 정책 준수)
  시간이 좀 걸릴 수 있습니다. 한 번 찾아온 위치는 캐시에 저장되어 다음부터는 빠릅니다.
"""

import time

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
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


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


@st.cache_data(show_spinner="읍·면·동 실제 위치를 찾는 중... (처음 한 번만, 시간이 걸릴 수 있어요)")
def geocode_dongs(dong_list: tuple) -> dict:
    """(시도, 시군구, 동) 튜플들을 받아 {(시군구, 동): (경도, 위도)} 딕셔너리로 돌려줍니다."""
    headers = {"User-Agent": "cheonan-asan-population-map-streamlit-app"}
    coords = {}
    for 시도, 시군구, 동 in dong_list:
        query = f"대한민국 {시도} {시군구} {동}"
        try:
            res = requests.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers=headers,
                timeout=10,
            )
            data = res.json()
            if data:
                lon = float(data[0]["lon"])
                lat = float(data[0]["lat"])
                coords[(시군구, 동)] = (lon, lat)
        except Exception:
            # 위치를 못 찾아도 앱이 멈추지 않도록 그냥 넘어갑니다.
            pass
        # Nominatim 사용 정책: 초당 1건 이하로 요청 (서버에 예의를 지킵니다)
        time.sleep(1)
    return coords


def parse_age(col: str) -> int:
    """'계_65세' -> 65, '계_100세 이상' -> 100 처럼 열 이름에서 나이를 뽑아냅니다."""
    age_str = col.split("_", 1)[1].replace("이상", "").replace("세", "").strip()
    return int(age_str)


def add_demographics(df: pd.DataFrame) -> pd.DataFrame:
    """남/여, 아이(0-19)/어른(20-64)/노인(65+) 인구 열을 추가합니다."""
    male_cols = [c for c in df.columns if c.startswith("남_")]
    female_cols = [c for c in df.columns if c.startswith("여_")]
    total_cols = [c for c in df.columns if c.startswith("계_")]

    child_cols = [c for c in total_cols if parse_age(c) <= 19]
    adult_cols = [c for c in total_cols if 20 <= parse_age(c) <= 64]
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
    "시군구 경계는 실제 지도이며, 읍·면·동은 실제 위치(지오코딩 결과)에 점으로 표시했습니다. "
    "마우스를 올리면 남/여, 아이(0-19세)/어른(20-64세)/노인(65세 이상) 인구가 보입니다."
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
target_features = [
    f for f in geojson["features"] if f["properties"].get("코드") in target_codes
]
target_geojson = {"type": "FeatureCollection", "features": target_features}

# -----------------------------
# 읍·면·동 단위 통계 + 실제 위치(지오코딩) 부여
# -----------------------------
dong_stats = (
    year_df.groupby(["시군구코드", "시군구", "동", "도시", "시도"])[
        ["전체인구", "남", "여", "아이", "어른", "노인"]
    ]
    .sum()
    .reset_index()
)

# 지오코딩은 연도가 바뀌어도 같은 읍·면·동 목록이므로, 전체 데이터 기준 목록으로 한 번만 조회
전체동목록 = tuple(
    sorted(target_df[["시도", "시군구", "동"]].drop_duplicates().itertuples(index=False, name=None))
)
dong_coords = geocode_dongs(전체동목록)

# 좌표를 못 찾은 동은 지도에서 제외 (억지로 임의 위치에 찍지 않습니다)
dong_stats["좌표"] = dong_stats.apply(
    lambda row: dong_coords.get((row["시군구"], row["동"])), axis=1
)
못찾은_개수 = dong_stats["좌표"].isna().sum()
dong_stats = dong_stats.dropna(subset=["좌표"]).copy()
dong_stats["경도"] = dong_stats["좌표"].apply(lambda xy: xy[0])
dong_stats["위도"] = dong_stats["좌표"].apply(lambda xy: xy[1])

# -----------------------------
# 지도 그리기
# -----------------------------
fig = go.Figure()

# 1) 시군구 경계 (천안 동남구 / 천안 서북구 / 아산시)
sigungu_hover = [
    f"<b>{row['시군구']}</b> ({row['시도']})<br>"
    f"전체인구: {row['전체인구']:,.0f}명<br>"
    f"남: {row['남']:,.0f}명 · 여: {row['여']:,.0f}명<br>"
    f"아이(0-19세): {row['아이']:,.0f}명 · 어른(20-64세): {row['어른']:,.0f}명 · "
    f"노인(65세 이상): {row['노인']:,.0f}명"
    for _, row in sigungu_stats.iterrows()
]

fig.add_trace(
    go.Choropleth(
        geojson=target_geojson,
        locations=sigungu_stats["시군구코드"],
        z=[1] * len(sigungu_stats),  # 색은 경계 표시용일 뿐, 수치 의미는 없음
        featureidkey="properties.코드",
        colorscale=[[0, "#f0f0f0"], [1, "#f0f0f0"]],
        showscale=False,
        marker_line_color="#555555",
        marker_line_width=1,
        text=sigungu_hover,
        hoverinfo="text",
        name="시군구",
    )
)

# 2) 읍·면·동 점 (실제 위치, 인구 규모에 따라 점 크기 변화)
dong_stats = dong_stats.reset_index(drop=True)
dong_hover = [
    f"<b>{row['동']}</b> ({row['시군구']})<br>"
    f"전체인구: {row['전체인구']:,.0f}명<br>"
    f"남: {row['남']:,.0f}명 · 여: {row['여']:,.0f}명<br>"
    f"아이(0-19세): {row['아이']:,.0f}명 · 어른(20-64세): {row['어른']:,.0f}명 · "
    f"노인(65세 이상): {row['노인']:,.0f}명"
    for _, row in dong_stats.iterrows()
]

city_colors = {"천안": "#e6550d", "아산": "#2171b5"}

for city, color in city_colors.items():
    idx = dong_stats.index[dong_stats["도시"] == city]
    sub = dong_stats.loc[idx]
    hover_sub = [dong_hover[i] for i in idx]
    fig.add_trace(
        go.Scattergeo(
            lon=sub["경도"],
            lat=sub["위도"],
            mode="markers",
            marker=dict(
                size=(sub["전체인구"].clip(lower=1)) ** 0.5 / 4,
                sizemin=4,
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
fig.update_geos(visible=False, fitbounds="locations")
fig.update_layout(
    height=650,
    margin=dict(l=0, r=0, t=10, b=0),
    legend_title_text="",
)

st.plotly_chart(fig, use_container_width=True)

if 못찾은_개수 > 0:
    st.caption(f"※ 읍·면·동 {못찾은_개수}곳은 위치를 찾지 못해 지도에서 제외했습니다.")

st.caption("점 하나가 읍·면·동 하나이며, 점 크기는 그 동의 인구 규모에 비례합니다.")
