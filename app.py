import streamlit as st
from backtest import TradingRules, SwingTradeBacktest

st.title("📈 Swing Trade Backtest App")

# --- 入力フォーム ---
st.sidebar.header("Backtest Parameters")

ticker = st.sidebar.text_input("Ticker", value="9984.T")
start_date = st.sidebar.date_input("Start Date", value=None)
end_date = st.sidebar.date_input("End Date", value=None)

run_button = st.sidebar.button("🚀 Run Backtest")

# === バックテスト実行 ===
if run_button:

    if start_date is None or end_date is None:
        st.error("日付を入力してください")
        st.stop()

    st.write(f"### バックテスト実行中… ({ticker})")
    rule = TradingRules()
    bt = SwingTradeBacktest(
        ticker,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        rule
    )

    bt.run(show_charts=False, show_detailed=False)

    # 結果表示
    st.subheader("📊 Performance Summary")
    st.json(bt.performance)

    # グラフ表示（matplotlib → streamlit）
    st.subheader("📈 Charts")
    bt.plot_results()
    st.pyplot()
