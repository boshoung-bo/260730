import json
import urllib.request
import pandas as pd
import plotly.express as px
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="천안·아산 읍면동 행정지도 시각화",
    page_icon="🗺️",
    layout="wide",
)

st.title("🗺️ 천안시 · 아산시 실제 지도 모양 도형 시각화")
st.markdown(
    "무거운 배경 타일 대신 **실제 읍·면·동 행정구역 경계선(SVG 도형 이미지)**을 직접 그려 인구 정보를 빠르게 확인할 수 있습니다."
)

# -----------------------------------------------------------------------------
# 2. GeoJSON (지도 모양 데이터) & 인구 데이터 로드 및 전처리
# -----------------------------------------------------------------------------
@st.cache_data
def load_geojson():
    # 대한민국 읍면동 경계 GeoJSON URL
    url = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/hangjeongdong_44.json"
    req = urllib.request.urlopen(url)
    geojson_data = json.loads(req.read().decode("utf-8"))

    # 천안시(44131, 44133) 및 아산시(44200) 관련 읍면동 경계만 추출
    ca_features = []
    for feature in geojson_data["features"]:
        code = feature["properties"]["code"]
        # 충남 천안시 동남구(44131), 서북구(44133), 아산시(44200)
        if code.startswith("4413") or code.startswith("4420"):
            ca_features.append(feature)

    geojson_data["features"] = ca_features
    return geojson_data


@st.cache_data
def load_data():
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    df = pd.read_csv(pop_url, dtype={"코드": str})

    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    df_ca = df_latest[
        (df_latest["시도"] == "충청남도")
        & (df_latest["시군구"].str.contains("천안|아산"))
    ].copy()

    df_ca["도시명"] = df_ca["시군구"].apply(
        lambda x: "천안시" if "천안시" in x else "아산시"
    )

    child_cols, adult_cols, elderly_cols = [], [], []
    male_cols = [c for c in df_ca.columns if c.startswith("남_")]
    female_cols = [c for c in df_ca.columns if c.startswith("여_")]
    total_cols = [c for c in df_ca.columns if c.startswith("계_")]

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

    df_ca["총인구"] = df_ca[total_cols].sum(axis=1)
    df_ca["남성인구"] = df_ca[male_cols].sum(axis=1)
    df_ca["여성인구"] = df_ca[female_cols].sum(axis=1)
    df_ca["아이인구"] = df_ca[child_cols].sum(axis=1)
    df_ca["어른인구"] = df_ca[adult_cols].sum(axis=1)
    df_ca["노인인구"] = df_ca[elderly_cols].sum(axis=1)

    df_ca["고령화율"] = round((df_ca["노인인구"] / df_ca["총인구"]) * 100, 1)
    df_ca["아이비율"] = round((df_ca["아이인구"] / df_ca["총인구"]) * 100, 1)
    df_ca["여성비율"] = round((df_ca["여성인구"] / df_ca["총인구"]) * 100, 1)

    df_ca["지역풀네임"] = (
        df_ca["도시명"] + " " + df_ca["시군구"] + " " + df_ca["동"]
    )

    return df_ca, latest_year


with st.spinner("천안·아산 경계선 지도 및 인구 데이터를 불러오는 중입니다..."):
    geojson_data = load_geojson()
    df_ca, latest_year = load_data()

# -----------------------------------------------------------------------------
# 3. 사이드바 필터 설정
# -----------------------------------------------------------------------------
st.sidebar.header("🔍 조회 필터 설정")

city_filter = st.sidebar.selectbox(
    "도시 선택", ["전체 (천안+아산)", "천안시", "아산시"]
)

if city_filter == "천안시":
    filtered_df = df_ca[df_ca["도시명"] == "천안시"].copy()
elif city_filter == "아산시":
    filtered_df = df_ca[df_ca["도시명"] == "아산시"].copy()
else:
    filtered_df = df_ca.copy()

metric_map = {
    "총인구 (명)": "총인구",
    "고령화율 (%)": "고령화율",
    "아이 인구 (0~14세)": "아이인구",
    "어른 인구 (15~64세)": "어른인구",
    "노인 인구 (65세 이상)": "노인인구",
    "여성 비율 (%)": "여성비율",
}
selected_metric_label = st.sidebar.selectbox(
    "도형 지도 색상 지표", list(metric_map.keys())
)
selected_metric_col = metric_map[selected_metric_label]

selected_dong = st.sidebar.selectbox(
    "특정 읍·면·동 상세 검색", ["전체 보기"] + list(filtered_df["동"].unique())
)

if selected_dong != "전체 보기":
    display_df = filtered_df[filtered_df["동"] == selected_dong].copy()
else:
    display_df = filtered_df.copy()

# -----------------------------------------------------------------------------
# 4. 상단 핵심 요약 (KPI Cards)
# -----------------------------------------------------------------------------
st.caption(f"기준 연도: **{latest_year}년** | 대상 읍·면·동 수: **{len(display_df)}개**")

tot_pop = int(display_df["총인구"].sum())
m_pop = int(display_df["남성인구"].sum())
f_pop = int(display_df["여성인구"].sum())
c_pop = int(display_df["아이인구"].sum())
a_pop = int(display_df["어른인구"].sum())
e_pop = int(display_df["노인인구"].sum())

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("👥 총인구", f"{tot_pop:,}명")
c2.metric("👨 남 / 👩 여", f"{m_pop:,} / {f_pop:,}")
c3.metric(
    "👶 아이(0~14세)",
    f"{c_pop:,}명",
    f"{round(c_pop/tot_pop*100, 1) if tot_pop > 0 else 0}%",
)
c4.metric(
    "🧑 어른(15~64세)",
    f"{a_pop:,}명",
    f"{round(a_pop/tot_pop*100, 1) if tot_pop > 0 else 0}%",
)
c5.metric(
    "👵 노인(65세 이상)",
    f"{e_pop:,}명",
    f"{round(e_pop/tot_pop*100, 1) if tot_pop > 0 else 0}%",
)

st.divider()

# -----------------------------------------------------------------------------
# 5. 실제 지도 모양 도형(SVG Polygon) 시각화
# -----------------------------------------------------------------------------
st.subheader(f"🗺️ 천안·아산 실제 지도 경계 모양 ({selected_metric_label})")

fig = px.choropleth(
    display_df,
    geojson=geojson_data,
    locations="동",
    featureidkey="properties.name",
    color=selected_metric_col,
    color_continuous_scale="Reds"
    if "고령" in selected_metric_label or "노인" in selected_metric_label
    else "YlGnBu",
    hover_name="지역풀네임",
    hover_data={
        "동": False,
        "총인구": ":,명",
        "남성인구": ":,명",
        "여성인구": ":,명",
        "아이인구": ":,명",
        "어른인구": ":,명",
        "노인인구": ":,명",
        "고령화율": ":.1f%",
    },
)

# 실제 지도 구역만 깔끔하게 보이고 축/격자선은 숨김 처리
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    height=600,
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 6. 상세 데이터표
# -----------------------------------------------------------------------------
st.subheader("📋 천안·아산 읍·면·동 상세 데이터")

sort_col = st.selectbox(
    "정렬 기준 컬럼",
    ["총인구", "고령화율", "아이인구", "어른인구", "노인인구", "여성비율"],
)
sorted_table = display_df.sort_values(by=sort_col, ascending=False)

table_view = sorted_table[
    [
        "도시명",
        "시군구",
        "동",
        "총인구",
        "남성인구",
        "여성인구",
        "아이인구",
        "어른인구",
        "노인인구",
        "고령화율",
    ]
].reset_index(drop=True)

st.dataframe(
    table_view.style.format(
        {
            "총인구": "{:,}명",
            "남성인구": "{:,}명",
            "여성인구": "{:,}명",
            "아이인구": "{:,}명",
            "어른인구": "{:,}명",
            "노인인구": "{:,}명",
            "고령화율": "{:.1f}%",
        }
    ),
    use_container_width=True,
    height=350,
)
