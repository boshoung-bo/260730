import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. 페이지 기본 설정
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="천안 vs 아산 인구 비교 분석",
    page_icon="📊",
    layout="wide",
)

st.title("📊 천안시 vs 아산시 인구 및 고령화 비교 (2015~2026)")
st.markdown(
    "동일한 생활권인 **충청남도 천안시와 아산시**의 연도별 인구 변화 추이와 고령화율을 비교합니다."
)


# -----------------------------------------------------------------------------
# 2. 데이터 불러오기 및 전처리
# -----------------------------------------------------------------------------
@st.cache_data
def load_comparison_data():
    pop_url = "https://raw.githubusercontent.com/greatsong/modudata/main/data/population_yearly.csv.gz"

    # 코드 열은 문자열로 로드
    df = pd.read_csv(pop_url, dtype={"코드": str})

    # 충청남도 천안시(동남구/서북구 포함) 및 아산시 데이터 필터링
    df_filtered = df[
        (df["시도"] == "충청남도") & (df["시군구"].str.contains("천안시|아산시"))
    ].copy()

    # 천안시 동남구/서북구를 하나로 묶기 위해 '천안시'로 대표 이름 정리
    df_filtered["도시명"] = df_filtered["시군구"].apply(
        lambda x: "천안시" if "천안시" in x else "아산시"
    )

    # 전체 인구 컬럼('계_') 및 65세 이상 인구 컬럼 추출
    total_cols = [c for c in df_filtered.columns if c.startswith("계_")]

    elderly_cols = []
    for col in total_cols:
        age_str = col.replace("계_", "").replace("세", "").replace(" 이상", "")
        if age_str.isdigit() and int(age_str) >= 65:
            elderly_cols.append(col)
        elif "100" in col:
            elderly_cols.append(col)

    # 읍면동 단위 인구 합산
    df_filtered["총인구"] = df_filtered[total_cols].sum(axis=1)
    df_filtered["고령인구"] = df_filtered[elderly_cols].sum(axis=1)

    # 연도 및 도시별 집계
    grouped = (
        df_filtered.groupby(["연도", "도시명"])[["총인구", "고령인구"]]
        .sum()
        .reset_index()
    )

    # 고령화율(%) 및 청장년·유소년 인구(고령외 인구) 계산
    grouped["고령화율"] = round((grouped["고령인구"] / grouped["총인구"]) * 100, 1)
    grouped["생산/유소년인구"] = grouped["총인구"] - grouped["고령인구"]

    return grouped


with st.spinner("천안·아산 인구 데이터를 분석하는 중입니다..."):
    df_compare = load_comparison_data()

# -----------------------------------------------------------------------------
# 3. 주요 지표 요약 (최신 연도 기준 KPI 카드)
# -----------------------------------------------------------------------------
latest_year = df_compare["연도"].max()
st.subheader(f"📌 {latest_year}년 기준 주요 지표")

latest_df = df_compare[df_compare["연도"] == latest_year]

cheonan_latest = latest_df[latest_df["도시명"] == "천안시"].iloc[0]
asan_latest = latest_df[latest_df["도시명"] == "아산시"].iloc[0]

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="🏢 천안시 총인구",
        value=f"{int(cheonan_latest['총인구']):,}명",
    )
with col2:
    st.metric(
        label="🏭 아산시 총인구",
        value=f"{int(asan_latest['총인구']):,}명",
    )
with col3:
    st.metric(
        label="👵 천안시 고령화율",
        value=f"{cheonan_latest['고령화율']}%",
    )
with col4:
    st.metric(
        label="👴 아산시 고령화율",
        value=f"{asan_latest['고령화율']}%",
    )

st.divider()

# -----------------------------------------------------------------------------
# 4. 시각화 (인구 추이 및 고령화율 비교 그래프)
# -----------------------------------------------------------------------------
st.subheader("📈 연도별 인구 및 고령화율 비교 그래프")

tab1, tab2, tab3 = st.tabs(
    ["👥 총인구 변화 추이", "👴 고령화율(%) 추이", "📊 고령인구 수 비교"]
)

# [탭 1] 총인구 변화
with tab1:
    fig_total = px.line(
        df_compare,
        x="연도",
        y="총인구",
        color="도시명",
        markers=True,
        title="2015~2026년 천안시 vs 아산시 총인구 변화",
        color_discrete_map={"천안시": "#2b5c8f", "아산시": "#d95f02"},
    )
    fig_total.update_traces(hovertemplate="%{x}년 %{legendgroup}: %{y:,}명")
    fig_total.update_layout(
        xaxis=dict(dtick=1),
        yaxis_title="인구수 (명)",
        hovermode="x unified",
    )
    st.plotly_chart(fig_total, use_container_width=True)

# [탭 2] 고령화율(%) 변화
with tab2:
    fig_aging = px.line(
        df_compare,
        x="연도",
        y="고령화율",
        color="도시명",
        markers=True,
        title="2015~2026년 천안시 vs 아산시 65세 이상 인구 비율(%)",
        color_discrete_map={"천안시": "#2b5c8f", "아산시": "#d95f02"},
    )
    fig_aging.update_traces(hovertemplate="%{x}년 %{legendgroup}: %{y}%")
    fig_aging.update_layout(
        xaxis=dict(dtick=1),
        yaxis_title="고령화율 (%)",
        hovermode="x unified",
    )
    st.plotly_chart(fig_aging, use_container_width=True)

# [탭 3] 고령인구 수 비교
with tab3:
    fig_elderly = px.bar(
        df_compare,
        x="연도",
        y="고령인구",
        color="도시명",
        barmode="group",
        title="2015~2026년 천안시 vs 아산시 65세 이상 고령인구 수",
        color_discrete_map={"천안시": "#2b5c8f", "아산시": "#d95f02"},
    )
    fig_elderly.update_traces(hovertemplate="%{x}년 %{legendgroup}: %{y:,}명")
    fig_elderly.update_layout(
        xaxis=dict(dtick=1),
        yaxis_title="고령인구수 (명)",
    )
    st.plotly_chart(fig_elderly, use_container_width=True)

st.divider()

# -----------------------------------------------------------------------------
# 5. 세부 데이터 피벗 테이블 출력
# -----------------------------------------------------------------------------
st.subheader("📋 연도별 상세 데이터표")

# 데이터를 피벗 테이블 형태로 변환하여 한눈에 비교하기 쉽게 구성
pivot_total = df_compare.pivot(index="연도", columns="도시명", values="총인구")
pivot_aging = df_compare.pivot(
    index="연도", columns="도시명", values="고령화율"
)

col_t1, col_t2 = st.columns(2)

with col_t1:
    st.markdown("#### 👥 연도별 총인구 (명)")
    st.dataframe(
        pivot_total.style.format("{:,}"),
        use_container_width=True,
    )

with col_t2:
    st.markdown("#### 👴 연도별 고령화율 (%)")
    st.dataframe(
        pivot_aging.style.format("{:.1f}%"),
        use_container_width=True,
    )
