import io
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 읍면동 인구 및 연령대별 대시보드",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 전국 읍·면·동 인구 및 연령·성별 구조 지도")
st.markdown(
    "전국 읍·면·동별 **남녀, 아이(0~14세), 어른(15~64세), 노인(65세 이상)** 인구 및 고령화율을 지도로 시각화합니다."
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리 (안전한 네트워크 처리 추가)
# -----------------------------------------------------------------------------
@st.cache_data
def load_umd_data():
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"

    # [GEOJSON] 시군구/읍면동 경계 데이터 로드 (에러 방지 처리)
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

    # GeoJSON 안전 수신
    response = requests.get(geojson_url)
    response.raise_for_status()  # 200 OK가 아닐 경우 에러 발생
    geojson_data = response.json()

    # [CSV] 인구 데이터 로드 (행정동 코드는 문자열)
    df = pd.read_csv(pop_url, dtype={"코드": str})

    # 가장 최근 연도 데이터 추출
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    # 연령대별 컬럼 분리
    child_cols = []
    adult_cols = []
    elderly_cols = []
    male_cols = [c for c in df_latest.columns if c.startswith("남_")]
    female_cols = [c for c in df_latest.columns if c.startswith("여_")]
    total_cols = [c for c in df_latest.columns if c.startswith("계_")]

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
    df_latest["총인구"] = df_latest[total_cols].sum(axis=1)
    df_latest["남성인구"] = df_latest[male_cols].sum(axis=1)
    df_latest["여성인구"] = df_latest[female_cols].sum(axis=1)
    df_latest["아이인구"] = df_latest[child_cols].sum(axis=1)
    df_latest["어른인구"] = df_latest[adult_cols].sum(axis=1)
    df_latest["노인인구"] = df_latest[elderly_cols].sum(axis=1)

    # 비율 계산 (%)
    df_latest["고령화율"] = round(
        (df_latest["노인인구"] / df_latest["총인구"]) * 100, 1
    ).fillna(0)
    df_latest["여성비율"] = round(
        (df_latest["여성인구"] / df_latest["총인구"]) * 100, 1
    ).fillna(0)
    df_latest["아이비율"] = round(
        (df_latest["아이인구"] / df_latest["총인구"]) * 100, 1
    ).fillna(0)

    # 행정동 명칭 결합 (예: 서울특별시 종로구 청운효자동)
    df_latest["지역명"] = (
        df_latest["시도"] + " " + df_latest["시군구"] + " " + df_latest["동"]
    )

    # 지도의 경계 코드(5자리)에 맞게 코드 잘라내기
    df_latest["sigungu_code"] = df_latest["코드"].str[:5]

    return df_latest, geojson_data, latest_year


try:
    with st.spinner("전국 인구 지도 데이터를 로드하는 중입니다..."):
        df_emd, geojson_emd, data_year = load_umd_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# 3. 사이드바 설정 (지역 선택 & 조회 지표 선택)
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 조회 조건 설정")

# 시도 필터
sido_list = ["전국"] + list(df_emd["시도"].unique())
selected_sido = st.sidebar.selectbox("시·도 선택", sido_list)

# 데이터 필터링
if selected_sido != "전국":
    filtered_df = df_emd[df_emd["시도"] == selected_sido].copy()
else:
    filtered_df = df_emd.copy()

# 지도 표현 지표 선택
metric_options = {
    "고령화율 (%)": "고령화율",
    "총인구 (명)": "총인구",
    "아이 인구 (0~14세)": "아이인구",
    "어른 인구 (15~64세)": "어른인구",
    "노인 인구 (65세 이상)": "노인인구",
    "여성 비율 (%)": "여성비율",
}
selected_metric_name = st.sidebar.selectbox(
    "지도 표현 지표", list(metric_options.keys())
)
selected_metric_col = metric_options[selected_metric_name]

# -----------------------------------------------------------------------------
# 4. 요약 지표 (KPI) Card
# -----------------------------------------------------------------------------
st.caption(f"기준 연도: **{data_year}년** | 선택 지역: **{selected_sido}**")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
total_pop = int(filtered_df["총인구"].sum())
male_pop = int(filtered_df["남성인구"].sum())
female_pop = int(filtered_df["여성인구"].sum())
child_pop = int(filtered_df["아이인구"].sum())
elderly_pop = int(filtered_df["노인인구"].sum())

kpi1.metric("👥 총인구", f"{total_pop:,}명")
kpi2.metric("👨 남성 / 👩 여성", f"{male_pop:,} / {female_pop:,}")
kpi3.metric(
    "👶 아이(0~14세)",
    f"{child_pop:,}명",
    f"{round(child_pop/total_pop*100, 1) if total_pop > 0 else 0}%",
)
kpi4.metric(
    "🧑 어른(15~64세)",
    f"{int(filtered_df['어른인구'].sum()):,}명",
)
kpi5.metric(
    "👵 노인(65세 이상)",
    f"{elderly_pop:,}명",
    f"{round(elderly_pop/total_pop*100, 1) if total_pop > 0 else 0}%",
)

st.divider()

# -----------------------------------------------------------------------------
# 5. Plotly 지도 시각화
# -----------------------------------------------------------------------------
st.subheader(f"🗺️ 지역별 {selected_metric_name} 지도")

fig = px.choropleth_mapbox(
    filtered_df,
    geojson=geojson_emd,
    locations="sigungu_code",  # 행정동 코드 앞 5자리
    featureidkey="properties.코드",  # GeoJSON의 5자리 시군구 코드
    color=selected_metric_col,
    color_continuous_scale="Reds"
    if "고령" in selected_metric_name or "노인" in selected_metric_name
    else "Blues",
    hover_name="지역명",
    hover_data={
        "sigungu_code": False,
        "총인구": ":,명",
        "남성인구": ":,명",
        "여성인구": ":,명",
        "아이인구": ":,명",
        "어른인구": ":,명",
        "노인인구": ":,명",
        "고령화율": ":.1f%",
    },
    mapbox_style="white-bg",
    center={"lat": 35.9, "lon": 127.8},
    zoom=6 if selected_sido == "전국" else 8,
    opacity=0.8,
)

fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    height=650,
)
fig.update_traces(marker_line_width=0.2, marker_line_color="#888888")

st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 6. 세부 순위 데이터표
# -----------------------------------------------------------------------------
st.subheader(f"📊 {selected_metric_name} 상위 / 하위 10개 읍·면·동")

df_sorted = filtered_df.sort_values(by=selected_metric_col, ascending=False)

top_10 = df_sorted.head(10)[
    ["시도", "시군구", "동", "총인구", "아이인구", "어른인구", "노인인구", "고령화율"]
].reset_index(drop=True)
bottom_10 = (
    df_sorted.tail(10)
    .sort_values(by=selected_metric_col, ascending=True)[
        ["시도", "시군구", "동", "총인구", "아이인구", "어른인구", "노인인구", "고령화율"]
    ]
    .reset_index(drop=True)
)

col1, col2 = st.columns(2)

with col1:
    st.markdown(f"### 🔴 {selected_metric_name} 높은 지역 Top 10")
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
    st.markdown(f"### 🔵 {selected_metric_name} 낮은 지역 Top 10")
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
