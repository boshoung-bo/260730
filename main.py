import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정 및 스타일 지정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="전국 시군구 고령화 지도",
    page_icon="🗺️",
    layout="wide",  # 화면 전체 너비 활용
)

st.title("🗺️ 대한민국 시군구별 고령화 지도")
st.markdown(
    "전국 읍·면·동 인구 데이터를 기반으로 시군구별 **65세 이상 인구 비율**을 시각화합니다."
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리 (캐싱 적용으로 속도 향상)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    # 데이터 URL
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"
    geojson_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/boundaries/sigungu_kr.geojson"

    # [GEOJSON] 시군구 경계 데이터 로드
    geojson_data = requests.get(geojson_url).json()

    # [CSV] 인구 데이터 로드
    # '코드' 열은 숫자 계산용이 아니라 행정동 고유 코드이므로 반드시 문자열(str)로 읽습니다.
    df = pd.read_csv(pop_url, dtype={"코드": str})

    # 가장 최근 연도 데이터만 필터링
    latest_year = df["연도"].max()
    df_latest = df[df["연도"] == latest_year].copy()

    # '코드' 앞 5자리를 추출하여 시군구 코드로 사용 (예: 1111051500 -> 11110)
    df_latest["sigungu_code"] = df_latest["코드"].str[:5]

    # 65세 이상 컬럼 찾기 ('계_65세'부터 '계_100세 이상'까지)
    # 데이터 컬럼 구조: '계_0세', '남_0세', '여_0세' ...
    total_cols = [c for c in df_latest.columns if c.startswith("계_")]

    # 나이 숫자를 추출하여 65세 이상 컬럼만 구분
    elderly_cols = []
    for col in total_cols:
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(col)
        elif "100" in col:  # '계_100세 이상' 처리
            elderly_cols.append(col)

    # 읍·면·동 단위 인구를 시군구(코드, 시도, 시군구) 단위로 합산
    # 전체 인구('총인구') 계산: 모든 '계_' 컬럼의 합
    df_latest["총인구"] = df_latest[total_cols].sum(axis=1)
    df_latest["고령인구"] = df_latest[elderly_cols].sum(axis=1)

    # 시군구 코드별로 집계
    grouped = (
        df_latest.groupby(["sigungu_code", "시도", "시군구"])[
            ["총인구", "고령인구"]
        ]
        .sum()
        .reset_index()
    )

    # 고령화율(%) 계산 (소수점 첫째 자리까지)
    grouped["고령화율"] = round((grouped["고령인구"] / grouped["총인구"]) * 100, 1)

    # -------------------------------------------------------------------------
    # 5단계 구간 나누기 (범례 표시용)
    # 구간 경계값: 19%, 23%, 28%, 38%
    # -------------------------------------------------------------------------
    bins = [0, 19, 23, 28, 38, 100]
    labels = [
        "19% 미만",
        "19% 이상 ~ 23% 미만",
        "23% 이상 ~ 28% 미만",
        "28% 이상 ~ 38% 미만",
        "38% 이상",
    ]

    grouped["고령화율_구간"] = pd.cut(
        grouped["고령화율"], bins=bins, labels=labels, right=False
    )

    return grouped, geojson_data, latest_year


# 데이터 준비
with st.spinner("데이터를 로드하는 중입니다..."):
    df_sigungu, geojson_kr, data_year = load_data()

st.caption(f" 기준 연도: **{data_year}년** | 총 시군구 수: **{len(df_sigungu)}개**")

# -----------------------------------------------------------------------------
# 3. Plotly 단계구분도(Choropleth) 지도 생성
# -----------------------------------------------------------------------------
# 단계별 색상 지정 (옅은 블루/그린계열 -> 진한 레드/버건디 계열)
color_discrete_map = {
    "19% 미만": "#edf8fb",
    "19% 이상 ~ 23% 미만": "#b2e2e2",
    "23% 이상 ~ 28% 미만": "#66c2a4",
    "28% 이상 ~ 38% 미만": "#2ca25f",
    "38% 이상": "#006d2c",
}

fig = px.choropleth_mapbox(
    df_sigungu,
    geojson=geojson_kr,
    locations="sigungu_code",  # CSV의 시군구 코드
    featureidkey="properties.코드",  # GeoJSON 속성의 시군구 코드 (5자리)
    color="고령화율_구간",  # 색상 처리할 5단계 범주
    color_discrete_map=color_discrete_map,
    category_orders={
        "고령화율_구간": [
            "19% 미만",
            "19% 이상 ~ 23% 미만",
            "23% 이상 ~ 28% 미만",
            "28% 이상 ~ 38% 미만",
            "38% 이상",
        ]
    },
    hover_name="시군구",  # 툴팁 제목
    hover_data={
        "sigungu_code": False,  # 코드는 마우스 호버 시 숨김
        "시도": True,
        "고령화율": ":.1f%",  # 소수점 1자리 + % 표시
        "총인구": ":,명",  # 천 단위 쉼표
        "고령인구": ":,명",
        "고령화율_구간": False,
    },
    mapbox_style="white-bg",  # 배경 타일 제거 (경계선 위주)
    center={"lat": 35.9, "lon": 127.8},  # 대한민국 중심 좌표
    zoom=6.2,  # 초기 확대 비율
    opacity=0.85,
)

# 지도 레이아웃 세부 설정
fig.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 10},
    legend_title_text="고령화율 구간 (65세 이상 비율)",
    legend=dict(yanchor="top", y=0.98, xanchor="left", x=0.01),
    height=650,
)

# 시군구 경계선 색상 및 두께 설정
fig.update_traces(marker_line_width=0.5, marker_line_color="#666666")

# Streamlit 화면에 지도 출력
st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 4. 고령화율 상위 / 하위 10개 지역 표 출력
# -----------------------------------------------------------------------------
st.subheader("📊 시군구 고령화율 순위")

# 표 출력을 위한 데이터 정렬
df_sorted = df_sigungu.sort_values(by="고령화율", ascending=False)

top_10 = df_sorted.head(10)[["시도", "시군구", "고령화율", "총인구", "고령인구"]].reset_index(
    drop=True
)
bottom_10 = (
    df_sorted.tail(10)
    .sort_values(by="고령화율", ascending=True)[
        ["시도", "시군구", "고령화율", "총인구", "고령인구"]
    ]
    .reset_index(drop=True)
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🔴 고령화율 가장 높은 곳 Top 10")
    st.dataframe(
        top_10.style.format(
            {"고령화율": "{:.1f}%", "총인구": "{:,}명", "고령인구": "{:,}명"}
        ),
        use_container_width=True,
    )

with col2:
    st.markdown("### 🔵 고령화율 가장 낮은 곳 Top 10")
    st.dataframe(
        bottom_10.style.format(
            {"고령화율": "{:.1f}%", "총인구": "{:,}명", "고령인구": "{:,}명"}
        ),
        use_container_width=True,
    )
