import pandas as pd
import plotly.express as px
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="천안·아산 읍면동 인구 시각화",
    page_icon="📊",
    layout="wide",
)

st.title("📊 천안시 · 아산시 모든 읍·면·동 인구 시각화")
st.markdown(
    "무거운 지도 타일 대신 **경량화된 도형(Treemap 및 위치 버블 차트)**으로 천안·아산의 **모든 읍·면·동 인구 통계**를 빠르게 확인하세요."
)

# 주요 읍면동 상대 위치 좌표 (경량화 위치 표현용)
LOCATION_MAP = {
    # 천안시 동남구
    "목천읍": (36.7788, 127.2289),
    "풍세면": (36.7381, 127.1264),
    "광덕면": (36.6872, 127.0601),
    "북면": (36.8378, 127.2483),
    "성남면": (36.7578, 127.2514),
    "수신면": (36.7533, 127.2953),
    "병천면": (36.7933, 127.3006),
    "동면": (36.8042, 127.3622),
    "중앙동": (36.8028, 127.1472),
    "문성동": (36.8083, 127.1528),
    "원성1동": (36.8067, 127.1628),
    "원성2동": (36.8008, 127.1611),
    "봉명동": (36.8003, 127.1358),
    "일봉동": (36.7903, 127.1389),
    "신방동": (36.7828, 127.1208),
    "청룡동": (36.7806, 127.1672),
    "신안동": (36.8228, 127.1689),
    # 천안시 서북구
    "성환읍": (36.9161, 127.1322),
    "성거읍": (36.8839, 127.1683),
    "직산읍": (36.8722, 127.1494),
    "입장면": (36.9069, 127.2181),
    "성정1동": (36.8153, 127.1383),
    "성정2동": (36.8239, 127.1378),
    "쌍용1동": (36.7967, 127.1228),
    "쌍용2동": (36.7958, 127.1139),
    "쌍용3동": (36.7903, 127.1111),
    "불당1동": (36.8106, 127.1089),
    "불당2동": (36.8180, 127.1030),
    "백석동": (36.8289, 127.1189),
    "부성1동": (36.8406, 127.1389),
    "부성2동": (36.8489, 127.1139),
    # 아산시
    "염치읍": (36.8239, 126.9989),
    "배방읍": (36.7761, 127.0544),
    "송악면": (36.7028, 127.0019),
    "탕정면": (36.8089, 127.0639),
    "음봉면": (36.8489, 127.0208),
    "둔포면": (36.9069, 127.0389),
    "영인면": (36.8819, 126.9369),
    "인주면": (36.8889, 126.8889),
    "선장면": (36.7839, 126.8889),
    "도고면": (36.7589, 126.9139),
    "신창면": (36.7719, 126.9489),
    "온양1동": (36.7869, 127.0008),
    "온양2동": (36.7819, 127.0069),
    "온양3동": (36.7969, 127.0189),
    "온양4동": (36.7719, 126.9808),
    "온양5동": (36.7608, 126.9939),
    "온양6동": (36.7628, 127.0219),
}


# -----------------------------------------------------------------------------
# 2. 데이터 로드 및 전처리
# -----------------------------------------------------------------------------
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

    df_ca["lat"] = df_ca["동"].map(lambda x: LOCATION_MAP.get(x, (36.81, 127.11))[0])
    df_ca["lon"] = df_ca["동"].map(lambda x: LOCATION_MAP.get(x, (36.81, 127.11))[1])

    df_ca["지역풀네임"] = (
        df_ca["도시명"] + " " + df_ca["시군구"] + " " + df_ca["동"]
    )

    return df_ca, latest_year


with st.spinner("데이터를 로딩 중입니다..."):
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
    "도형 색상/크기 표현 지표", list(metric_map.keys())
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
# 4. 상단 핵심 요약
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
# 5. 초경량 도형 이미지 시각화 (Treemap 및 위치 버블 차트)
# -----------------------------------------------------------------------------
st.subheader("🟩 1. 읍·면·동별 인구 비중 (사각형 Treemap)")
st.caption(
    "사각형의 **크기는 총인구 수**, **색상은 선택한 지표**를 나타냅니다."
)

fig_tree = px.treemap(
    display_df,
    path=["도시명", "시군구", "동"],
    values="총인구",
    color=selected_metric_col,
    color_continuous_scale="Reds"
    if "고령" in selected_metric_label or "노인" in selected_metric_label
    else "Viridis",
    hover_data={
        "총인구": ":,명",
        "남성인구": ":,명",
        "여성인구": ":,명",
        "아이인구": ":,명",
        "어른인구": ":,명",
        "노인인구": ":,명",
        "고령화율": ":.1f%",
    },
)

fig_tree.update_layout(margin=dict(t=10, l=10, r=10, b=10), height=450)
st.plotly_chart(fig_tree, use_container_width=True)

st.subheader("🔵 2. 상대 위치 기반 읍·면·동 분포 (원형 좌표 차트)")
st.caption(
    "무거운 지도를 대체하여 **경도/위도 좌표에 도형(Circle Marker)**만 표시하여 렌더링 속도를 대폭 개선했습니다."
)

fig_scatter = px.scatter(
    display_df,
    x="lon",
    y="lat",
    size="총인구",
    color=selected_metric_col,
    text="동",
    size_max=30,
    color_continuous_scale="Reds"
    if "고령" in selected_metric_label or "노인" in selected_metric_label
    else "Viridis",
    hover_name="지역풀네임",
    hover_data={
        "lat": False,
        "lon": False,
        "총인구": ":,명",
        "남성인구": ":,명",
        "여성인구": ":,명",
        "아이인구": ":,명",
        "어른인구": ":,명",
        "노인인구": ":,명",
        "고령화율": ":.1f%",
    },
)

fig_scatter.update_traces(textposition="top center")
fig_scatter.update_layout(
    xaxis_title="경도 (Longitude)",
    yaxis_title="위도 (Latitude)",
    height=500,
    margin=dict(t=20, l=20, r=20, b=20),
)

st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 6. 상세 데이터표
# -----------------------------------------------------------------------------
st.subheader("📋 천안·아산 읍·면·동 상세 인구 표")

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
