import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from ticker_list import sp500_list, nikkei225_list
from screening import MA_SHORT, MA_MID, MA_LONG, SLOPE_THRESHOLD, SLOPE_PERIOD
from screening import get_data_and_screen_advanced

st.set_page_config(page_title="株式スクリーニング", page_icon="📈", layout="wide")

st.title("📈 株式スクリーニング＆ヒートマップ分析")
st.markdown("""
このアプリは移動平均線を使った**押し目買い戦略**のスクリーニングツールです。  
強いトレンドの中で一時的に調整した銘柄を自動検出します。
""")

# --- サイドバー ---
st.sidebar.header("スクリーニング設定")
use_sp500 = st.sidebar.checkbox("S&P 500（米国株）", value=True)
use_nikkei = st.sidebar.checkbox("日経225（日本株）", value=False)

# 銘柄リストの決定（辞書のリストとして）
stock_list = []
if use_sp500:
    stock_list += sp500_list
if use_nikkei:
    stock_list += nikkei225_list

# --- スクリーニング ---
st.header("🔍 スクリーニング実行")

if not stock_list:
    st.warning("⚠️ 市場を選択してください（サイドバー）")
elif st.button("スクリーニング開始！"):
    with st.spinner(f"分析中...（対象: {len(stock_list)}銘柄）"):
        df = get_data_and_screen_advanced(stock_list)

    if df.empty:
        st.warning("❌ 条件に該当する銘柄がありませんでした")
        st.info(f"""
        **スクリーニング条件:**
        - MA{MA_SHORT} < MA{MA_MID} < MA{MA_LONG}（押し目形成）
        - MA{MA_MID}の傾き ≥ {SLOPE_THRESHOLD}%（強いトレンド）
        - 直近価格 > MA{MA_SHORT}（反転シグナル）
        """)
    else:
        st.success(f"✅ {len(df)} 銘柄がヒット！")

        # 表示
        st.subheader("📊 スクリーニング結果")
        st.caption("""
        **Slope_MA20**: MA20の5日間変化率（%）  
        **C1～C4**: 各条件の充足状況（✓=True）  
        **All_Signal**: 全条件クリア（買いシグナル）
        """)
        st.dataframe(df, use_container_width=True)

        # 統計サマリー
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("全条件クリア", f"{df['All_Signal'].sum()}銘柄")
        with col2:
            st.metric("強トレンド（C1）", f"{df['C1_Trend'].sum()}銘柄")
        with col3:
            st.metric("平均傾き", f"{df['Slope_MA20'].mean():.2f}%")

        # ヒートマップ表示
        st.header("🔥 条件充足ヒートマップ")
        st.caption("濃い色ほど条件を満たしています。数値はMA20の傾き（%）")

        # 上位30銘柄に絞る
        display_df = df.head(30)
        heatmap_df = display_df.set_index("Code")[[
            "Slope_MA20", "C1_Trend", "C2_Long", "C3_Pullback", "C4_Trigger"
        ]]

        # True/False を 1/0 に変換
        hm_numeric = heatmap_df.replace({True: 1, False: 0})

        fig, ax = plt.subplots(figsize=(12, max(6, len(display_df) * 0.3)))
        sns.heatmap(
            hm_numeric,
            annot=heatmap_df.values,
            fmt="",
            cmap="RdYlGn",
            linewidths=0.5,
            cbar_kws={'label': '条件充足度'},
            ax=ax
        )
        ax.set_xlabel("条件項目", fontsize=12)
        ax.set_ylabel("銘柄コード", fontsize=12)
        plt.tight_layout()
        st.pyplot(fig)

        # 銘柄選択
        st.header("📌 注目銘柄の選択")
        selected = st.multiselect(
            "バックテストしたい銘柄を選んでください（今後実装予定）",
            df["Code"].tolist(),
            default=df[df["All_Signal"] == True]["Code"].tolist()[:5]
        )
        if selected:
            selected_info = df[df["Code"].isin(selected)][["Code", "Name", "Slope_MA20", "All_Signal"]]
            st.dataframe(selected_info, use_container_width=True)
            st.info("💡 これらの銘柄で過去のパフォーマンスを検証するバックテスト機能を開発予定です")

        # CSV ダウンロード
        st.header("💾 データのエクスポート")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 結果をCSVでダウンロード",
            data=csv,
            file_name=f"screening_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )