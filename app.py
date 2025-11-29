import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from ticker_list import sp500_list
from screening import MA_SHORT, MA_MID, MA_LONG, SLOPE_THRESHOLD, SLOPE_PERIOD
from screening import get_data_and_screen_advanced

st.title("📈 株式スクリーニング＆ヒートマップ分析")

# --- サイドバー ---
st.sidebar.header("スクリーニング設定")

use_sp500 = st.sidebar.checkbox("S&P 500（米国株）", value=True)
use_nikkei = st.sidebar.checkbox("日経225（日本株）", value=False)

# 銘柄リストの決定
tickers = []
if use_sp500:
    tickers += [item["code"] for item in sp500_list]

# --- スクリーニング ---
st.header("🔍 スクリーニング実行")

if st.button("スクリーニング開始！"):
    with st.spinner("分析中..."):
        df = get_data_and_screen_advanced(tickers)

    if df.empty:
        st.warning("該当銘柄なし…")
    else:
        st.success(f"{len(df)} 銘柄ヒット！")

        # 表示
        st.dataframe(df, use_container_width=True)

        # ================================
        #  ヒートマップ表示
        # ================================
        st.header("🔥 ヒートマップ（条件の強さを可視化）")

        heatmap_df = df.set_index("Code")[[
            "Slope_MA20", "C1_Trend", "C2_Long", "C3_Pullback", "C4_Trigger"
        ]]

        # True/False を 1/0 に変換
        hm_numeric = heatmap_df.replace({True: 1, False: 0})

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(
            hm_numeric,
            annot=heatmap_df["Slope_MA20"].round(2).astype(str),
            fmt="",
            cmap="coolwarm",
            linewidths=.5,
            ax=ax
        )
        st.pyplot(fig)

        # ================================
        #  銘柄選択 → 後でバックテストに使う
        # ================================
        st.header("📌 気になる銘柄を選択")

        selected = st.multiselect(
            "バックテストしたい銘柄を選んでください",
            df["Code"].tolist()
        )

        if selected:
            st.write("選択された銘柄：", selected)
            st.info("次はバックテスト機能を実装します🔥")
