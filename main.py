import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="천안·아산 읍면동 인구 및 연령대별 대시보드",
    page_icon="🏙️",
    layout="wide",
)

st.title("🏙️ 천안시·아산시 읍·면·동 인구 및 연령·성별 구조 분석")
st.markdown(
    "충청남도 **천안시 및 아산시**의 읍·면·동별 **남녀, 아이(0~14세), 어른(15~64세), 노인(65세 이상)** 인구를 분석합니다."
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리 (천안·아산 전용)
# -----------------------------------------------------------------------------
@st.cache_data
def load_cheonan_asan_data():
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/../population_yearly.csv.gz"
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

    # GeoJSON 수신
    response = requests.get(geojson_url)
    response.raise_for_status()
    geojson_data = response.json()

    # 인구 데이터 로드 (행정동 코드는 문자열)
    df = pd.read_csv(
        "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz",
        dtype={"코드": str},
    )

    # 가장 최근 연도 데이터 추출
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    # 충청남도 천안시(동남구/서북구) 및 아산시 데이터만 필터링
    df_filtered = df_latest[
        (df_latest["시도"] == "충청남도")
        & (df_latest["시군구"].str.contains("천안|아산"))
    ].copy()

    # 도시구분 (천안시 / 아산시)
    df_filtered["도시명"] = df_filtered["시군구"].apply(
        lambda x: "천안시" if "천안시" in x else "아산시"
    )

    # 연령대별 컬럼 분리
    child_cols = []
    adult_cols = []
    elderly_cols = []
    male_cols = [c for c in df_filtered.columns if c.startswith("남_")]
    female_cols = [c for c in df_filtered.columns if c.startswith("여_")]
    total_cols = [c for c in df_filtered.columns if c.startswith("계_")]

    for col in total_cols:
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit():
            age = int(age_str)
            if age <= 14:
                child_cols.append(col)
            elif 15 <= age <= 64:
                adult_cols.append(col)
            else:
                elderly_cols.append(col)
        elif "100" in col:
            elderly_cols.append(col)

    # 읍면동별 인구 집계
    df_filtered["총인구"] = df_filtered[total_cols].sum(axis=1)
    df_filtered["남성인구"] = df_filtered[male_cols].sum(axis=1)
    df_filtered["여성인구"] = df_filtered[female_cols].sum(axis=1)
    df_filtered["아이인구"] = df_filtered[child_cols].sum(axis=1)
    df_filtered["어른인구"] = df_filtered[adult_cols].sum(axis=1)
    df_filtered["노인인구"] = df_filtered[elderly_cols].sum(axis=1)

    # 비율 계산 (%)
    df_filtered["고령화율"] = round(
        (df_filtered["노인인구"] / df_filtered["총인구"]) * 100, 1
    ).fillna(0)
    df_filtered["여성비율"] = round(
        (df_filtered["여성인구"] / df_filtered["총인구"]) * 100, 1
    ).fillna(0)
    df_filtered["아이비율"] = round(
        (df_filtered["아이인구"] / df_filtered["총인구"]) * 100, 1
    ).fillna(0)

    # 지역 전체 이름 생성 (예: 천안시 동남구 목천읍)
    df_filtered["지역명"] = (
        df_filtered["도시명"]
        + " "
        + df_filtered["시군구"]
        + " "
        + df_filtered["동"]
    )

    # 지도의 5자리 시군구 코드 매칭용
    df_filtered["sigungu_code"] = df_filtered["코드"].str[:5]

    return df_filtered, geojson_data, latest_year


try:
    with st.spinner("천안·아산 인구 데이터를 로드하는 중입니다..."):
        df_ca, geojson_kr, data_year = load_cheonan_asan_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 사이드바 설정 (도시 필터 & 지표 선택)
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 조회 조건 설정")

# 도시 선택 (전체, 천안시, 아산시)
city_list = ["전체 (천안+아산)", "천안시", "아산시"]
selected_city = st.sidebar.selectbox("도시 선택", city_list)

# 데이터 필터링
if selected_city == "천안시":
    filtered_df = df_ca[df_ca["도시명"] == "천안시"].copy()
elif selected_city == "아산시":
    filtered_df = df_ca[df_ca["도시명"] == "아산시"].copy()
else:
    filtered_df = df_ca.copy()

# 지도 및 표 표현 지표 선택
metric_options = {
    "고령화율 (%)": "고령화율",
    "총인구 (명)": "총인구",
    "아이 인구 (0~14세)": "아이인구",
    "어른 인구 (15~64세)": "어른인구",
    "노인 인구 (65세 이상)": "노인인구",
    "여성 비율 (%)": "여성비율",
}
selected_metric_name = st.sidebar.selectbox(
    "조회 지표 선택", list(metric_options.keys())
)
selected_metric_col = metric_options[selected_metric_name]

# -----------------------------------------------------------------------------
# 4. 요약 지표 (KPI Cards)
# -----------------------------------------------------------------------------
st.caption(f"기준 연도: **{data_year}년** | 선택 지역: **{selected_city}**")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
total_pop = int(filtered_df["총인구"].sum())
male_pop = int(filtered_df["남성인구"].sum())
female_pop = int(filtered_df["여성인구"].sum())
child_pop = int(filtered_df["아이인구"].sum())
adult_pop = int(filtered_df["어른인구"].sum())
elderly_pop = int(filtered_df["노인인구"].sum())

kpi1.metric("👥 총인구", f"{total_pop:,}명")
kpi2.metric("👨 남성 / 👩 여성", f"{male_pop:,} / {female_pop:,}")
kpi3.metric(
    "👶 아이(0~14세)",
    f"{child_pop:,}명",
    f"{round(child_pop/total_pop*100, 1) if total_pop > 0 else 0}%",
)
kpi4.metric("🧑 어른(15~64세)", f"{adult_pop:,}명")
kpi5.metric(
    "👵 노인(65세 이상)",
    f"{elderly_pop:,}명",
    f"{round(elderly_pop/total_pop*100, 1) if total_pop > 0 else 0}%",
)

st.divider()

# -----------------------------------------------------------------------------
# 5. Plotly 지도 시각화 (천안·아산 중심)
# -----------------------------------------------------------------------------
st.subheader(f"🗺️ {selected_city} {selected_metric_name} 지도")

# 지도 중심점 좌표 설정 (천안/아산 인근)
center_lat, center_lon = 36.81, 127.05

fig = px.choropleth_mapbox(
    filtered_df,
    geojson=geojson_kr,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color=selected_metric_col,
    color_continuous_scale="Reds"
    if "고령" in selected_metric_name or "노인" in selected_metric_name
    else "Blues",
    hover_name="동",
    hover_data={
        "sigungu_code": False,
        "시군구": True,
        "총인구": ":,명",
        "남성인구": ":,명",
        "여성인구": ":,명",
        "아이인구": ":,명",
        "어른인구": ":,명",
        "노인인구": ":,명",
        "고령화율": ":.1f%",
    },
    mapbox_style="white-bg",
    center={"lat": center_lat, "lon": center_lon},
    zoom=10,
    opacity=0.8,
)

fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    height=600,
)
fig.update_traces(marker_line_width=0.8, marker_line_color="#444444")

st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 6. 세부 읍·면·동 순위 데이터표
# -----------------------------------------------------------------------------
st.subheader(f"📊 {selected_city} 읍·면·동별 {selected_metric_name} 순위")

df_sorted = filtered_df.sort_values(by=selected_metric_col, ascending=False)

top_10 = df_sorted.head(10)[
    ["시군구", "동", "총인구", "아이인구", "어른인구", "노인인구", "고령화율"]
].reset_index(drop=True)
bottom_10 = (
    df_sorted.tail(10)
    .sort_values(by=selected_metric_col, ascending=True)[
        ["시군구", "동", "총인구", "아이인구", "어른인구", "노인인구", "고령화율"]
    ]
    .reset_index(drop=True)
)

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"### 🔴 {selected_metric_name} 높은 읍·면·동 Top 10")
    st.dataframe(
        top_10.style.format(
            {
                "총인구": "{:,}명",
                "아이인구": "{:,}명",
                "어른인구": "{:,}명",
                "노인인구": "{:,}명",
                "고령화율": "{:.1f}%",
            }
        ),
        use_container_width=True,
    )

with col2:
    st.markdown(f"### 🔵 {selected_metric_name} 낮은 읍·면·동 Top 10")
    st.dataframe(
        bottom_10.style.format(
            {
                "총인구": "{:,}명",
                "아이인구": "{:,}명",
                "어른인구": "{:,}명",
                "노인인구": "{:,}명",
                "고령화율": "{:.1f}%",
            }
        ),
        use_container_width=True,
    )
