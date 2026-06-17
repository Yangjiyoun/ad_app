##### 기본 정보 불러오기 #####
# Streamlit 패키지 추가
import streamlit as st
# 데이터 처리 패키지
import pandas as pd
# 금융 데이터 수집 패키지
import yfinance as yf
# 날짜 처리
import datetime as dt

##### 비교 대상 정의 #####
# 라벨: (티커, 단위 설명)
ASSETS = {
    "금 시세 (Gold, USD/oz)": ("GC=F", "USD/oz"),
    "달러 환율 (USD/KRW)": ("KRW=X", "원"),
    "미국 주가 (S&P 500)": ("^GSPC", "pt"),
    "한국 주가 (KOSPI)": ("^KS11", "pt"),
}


##### 기능 구현 함수 #####
@st.cache_data(ttl=60 * 60, show_spinner=False)
def load_prices(tickers, start, end):
    """선택한 티커들의 종가(Close)를 한 번에 받아 DataFrame으로 반환합니다."""
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
    )
    if raw is None or raw.empty:
        return pd.DataFrame()

    # 다중 티커면 'Close' 레벨을, 단일 티커면 'Close' 컬럼을 추출합니다.
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:
        close = raw[["Close"]]
        close.columns = tickers

    # 결측치는 직전 값으로 채우고, 모두 비어있는 행은 제거합니다.
    close = close.ffill().dropna(how="all")
    return close


def normalize(df):
    """각 시리즈를 시작 시점 = 100 으로 환산하여 서로 다른 단위를 비교 가능하게 만듭니다."""
    result = pd.DataFrame(index=df.index)
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue
        base = series.iloc[0]
        result[col] = df[col] / base * 100
    return result


##### 메인 함수 #####
def main():
    st.set_page_config(page_title="10년 금융자산 비교", page_icon="📈", layout="wide")

    st.header("📈 지난 10년 금융자산 비교")
    st.caption("금 시세 · 달러 환율 · 미국 주가(S&P500) · 한국 주가(KOSPI)를 한눈에 비교합니다.")
    st.markdown("---")

    with st.sidebar:
        st.subheader("⚙️ 설정")

        years = st.slider("조회 기간 (년)", min_value=1, max_value=20, value=10)
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=365 * years)

        st.caption(f"기간: {start_date} ~ {end_date}")

        selected_labels = st.multiselect(
            "비교할 자산",
            options=list(ASSETS.keys()),
            default=list(ASSETS.keys()),
        )

        normalized = st.toggle(
            "정규화 비교 (시작=100)",
            value=True,
            help="단위가 서로 다른 자산을 공정하게 비교하기 위해 시작 시점을 100으로 맞춥니다.",
        )

    if not selected_labels:
        st.warning("사이드바에서 비교할 자산을 1개 이상 선택하세요.")
        return

    # 선택한 라벨 -> 티커 매핑
    label_by_ticker = {ASSETS[label][0]: label for label in selected_labels}
    tickers = list(label_by_ticker.keys())

    with st.spinner("금융 데이터를 불러오는 중..."):
        try:
            prices = load_prices(tickers, start_date, end_date)
        except Exception as e:  # 네트워크/소스 오류 등
            prices = pd.DataFrame()
            fetch_error = str(e)
        else:
            fetch_error = None

    if prices.empty:
        st.error(
            "데이터를 불러오지 못했습니다. 인터넷(Yahoo Finance) 연결을 확인해 주세요.\n\n"
            "이 앱은 `query1.finance.yahoo.com` 등 야후 파이낸스 호스트에 접속할 수 있어야 합니다."
        )
        if fetch_error:
            st.caption(f"상세: {fetch_error}")
        return

    # 티커 컬럼을 사람이 읽기 쉬운 라벨로 변경
    prices = prices.rename(columns=label_by_ticker)
    # 선택 순서에 맞춰 컬럼 정렬
    ordered_cols = [c for c in selected_labels if c in prices.columns]
    prices = prices[ordered_cols]

    ##### 핵심 지표: 기간 수익률 #####
    st.subheader("기간 수익률")
    metric_cols = st.columns(len(ordered_cols))
    for col, label in zip(metric_cols, ordered_cols):
        series = prices[label].dropna()
        if series.empty:
            col.metric(label, "—")
            continue
        first, last = series.iloc[0], series.iloc[-1]
        change = (last / first - 1) * 100
        col.metric(label, f"{last:,.1f}", f"{change:+.1f}%")

    st.markdown("---")

    ##### 비교 차트 #####
    if normalized:
        st.subheader("정규화 비교 (시작 시점 = 100)")
        chart_df = normalize(prices)
        st.line_chart(chart_df, height=420)
        st.caption("같은 출발선(100)에서 각 자산의 상대적 성장률을 비교합니다.")
    else:
        st.subheader("실제 값 비교")
        st.info("자산별 단위(원/포인트/USD)가 달라 개별 차트로 표시합니다. 직접 비교는 정규화 모드를 사용하세요.")
        for label in ordered_cols:
            unit = ASSETS[label][1]
            st.markdown(f"**{label}** ({unit})")
            st.line_chart(prices[[label]], height=240)

    ##### 원본 데이터 #####
    with st.expander("📊 원본 데이터 보기 / 다운로드"):
        st.dataframe(prices.tail(250), use_container_width=True)
        csv = prices.to_csv().encode("utf-8-sig")
        st.download_button(
            "CSV 다운로드",
            data=csv,
            file_name="finance_compare.csv",
            mime="text/csv",
        )

    st.caption("데이터 출처: Yahoo Finance (yfinance). 투자 참고용이며 정확성을 보장하지 않습니다.")


if __name__ == "__main__":
    main()
