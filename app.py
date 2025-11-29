# app.py
import streamlit as st
from screening import get_data_and_screen_advanced
from ticker_list import sp500_list, nikkei225_list

st.title("📈 スクリーニング（MA7 / MA20 / MA60 + 傾き）")

market = st.sidebar.selectbox("対象市場", ["S&P500", "Nikkei225"])
if market == "S&P500":
    stock_list = sp500_list
else:
    stock_list = nikkei225_list

if st.button("🔍 スクリーニング実行"):
    df = get_data_and_screen_advanced(stock_list)
    st.dataframe(df)

    if not df.empty:
        df_signal = df[df["All_Signal"] == True]
        st.subheader("🚨 総合シグナル銘柄")
        st.dataframe(df_signal)
