import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from ticker_list import sp500_list, nikkei225_list
from screening import MA_SHORT, MA_MID, MA_LONG, SLOPE_THRESHOLD, SLOPE_PERIOD
from screening import get_data_and_screen_advanced

st.set_page_config(page_title="株式スクリーニング", page_icon="📈", layout="wide")

# セッション状態の初期化
if 'screening_done' not in st.session_state:
    st.session_state.screening_done = False
if 'screening_df' not in st.session_state:
    st.session_state.screening_df = None
if 'backtest_done' not in st.session_state:
    st.session_state.backtest_done = False
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None

st.title("📈 株式スクリーニング＆ヒートマップ分析")
st.markdown("""
このアプリは移動平均線を使った**押し目買い戦略**のスクリーニングツールです。  
強いトレンドの中で一時的に調整した銘柄を自動検出します。
""")

# --- サイドバー ---
st.sidebar.header("スクリーニング設定")
use_sp500 = st.sidebar.checkbox("S&P 500（米国株）", value=True)
use_nikkei = st.sidebar.checkbox("日経225（日本株）", value=False)

# 銘柄リストの決定
stock_list = []
if use_sp500:
    stock_list += sp500_list
if use_nikkei:
    stock_list += nikkei225_list

# --- スクリーニング ---
st.header("🔍 スクリーニング実行")

if not stock_list:
    st.warning("⚠️ 市場を選択してください（サイドバー）")
else:
    if st.button("スクリーニング開始！", key="screening_button"):
        with st.spinner(f"分析中...（対象: {len(stock_list)}銘柄）"):
            df = get_data_and_screen_advanced(stock_list)
            
            if df.empty:
                st.session_state.screening_done = False
                st.session_state.screening_df = None
                st.warning("❌ 条件に該当する銘柄がありませんでした")
                st.info(f"""
                **スクリーニング条件:**
                - MA{MA_SHORT} < MA{MA_MID} < MA{MA_LONG}（押し目形成）
                - MA{MA_MID}の傾き ≥ {SLOPE_THRESHOLD}%（強いトレンド）
                - 直近価格 > MA{MA_SHORT}（反転シグナル）
                """)
            else:
                st.session_state.screening_done = True
                st.session_state.screening_df = df
                st.session_state.backtest_done = False  # スクリーニングし直したらバックテスト結果をクリア

# スクリーニング結果の表示
if st.session_state.screening_done and st.session_state.screening_df is not None:
    df = st.session_state.screening_df
    
    st.success(f"✅ {len(df)} 銘柄がヒット！")

    # 表示
    st.subheader("📊 スクリーニング結果")
    st.caption("""
    **Slope_MA20**: MA20の5日間変化率（%）  
    **C1～C4**: 各条件の充足状況  
    **All_Signal**: 全条件クリア（買いシグナル）
    """)
    
    # 表示用にTrue/Falseを記号に変換
    display_df = df.copy()
    for col in ['C1_Trend', 'C2_Long', 'C3_Pullback', 'C4_Trigger', 'All_Signal']:
        display_df[col] = display_df[col].map({True: '✓', False: '✗'})
    
    # スタイルを適用して表示
    styled_df = display_df.style.apply(
        lambda row: ['background-color: #90EE90; font-weight: bold'] * len(row) 
        if row['All_Signal'] == '✓' else [''] * len(row), 
        axis=1
    ).format({
        'Slope_MA20': '{:.2f}%'
    })
    
    st.dataframe(styled_df, use_container_width=True, height=400)

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
    display_df_heat = df.head(30)
    heatmap_df = display_df_heat.set_index("Code")[[
        "Slope_MA20", "C1_Trend", "C2_Long", "C3_Pullback", "C4_Trigger"
    ]]

    # True/False を 1/0 に変換
    hm_numeric = heatmap_df.replace({True: 1, False: 0})

    fig, ax = plt.subplots(figsize=(12, max(6, len(display_df_heat) * 0.3)))
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
    
    # デフォルトで全条件クリア銘柄を選択
    default_tickers = df[df["All_Signal"] == True]["Code"].tolist()[:5]
    
    selected = st.multiselect(
        "バックテストしたい銘柄を選んでください",
        df["Code"].tolist(),
        default=default_tickers,
        key="ticker_multiselect"
    )
    
    if selected:
        selected_info = df[df["Code"].isin(selected)][["Code", "Name", "Slope_MA20", "All_Signal"]]
        st.dataframe(selected_info, use_container_width=True)
        
        # バックテストセクション
        st.subheader("🔬 バックテスト設定")
        
        col1, col2 = st.columns(2)
        with col1:
            backtest_period = st.selectbox(
                "バックテスト期間",
                ["1年", "2年", "3年", "5年"],
                index=2,
                key="period_select"
            )
        with col2:
            show_details = st.checkbox("詳細情報を表示", value=True, key="detail_checkbox")
        
        if st.button("🚀 バックテスト開始", type="primary", key="backtest_button"):
            # 期間設定
            period_map = {"1年": 365, "2年": 730, "3年": 1095, "5年": 1825}
            days = period_map[backtest_period]
            end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
            start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime('%Y-%m-%d')
            
            # バックテスト実行
            backtest_results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, ticker in enumerate(selected):
                status_text.text(f"バックテスト実行中... {ticker} ({idx+1}/{len(selected)})")
                progress_bar.progress((idx + 1) / len(selected))
                
                try:
                    from backtest import SwingTradeBacktest, TradingRules
                    
                    # ルール設定
                    rules = TradingRules()
                    
                    # バックテスト実行
                    bt = SwingTradeBacktest(ticker, start_date, end_date, rules)
                    perf = bt.run(show_charts=False, show_detailed=False)
                    
                    if perf:
                        backtest_results.append({
                            'Code': ticker,
                            'Name': df[df['Code']==ticker]['Name'].values[0],
                            'Total Trades': perf['total_trades'],
                            'Win Rate (%)': perf['win_rate'],
                            'Total P&L': perf['total_profit'],
                            'Avg Profit (%)': perf['avg_profit_pct'],
                            'Avg Loss (%)': perf['avg_loss_pct'],
                            'Profit Factor': perf['profit_factor'],
                            'Max Drawdown': perf['max_drawdown'],
                            'Avg Holding Days': perf['avg_holding_days']
                        })
                except Exception as e:
                    st.warning(f"⚠️ {ticker}: {str(e)}")
                    continue
            
            progress_bar.empty()
            status_text.empty()
            
            if backtest_results:
                st.session_state.backtest_done = True
                st.session_state.backtest_results = backtest_results
            else:
                st.session_state.backtest_done = False
                st.session_state.backtest_results = None
                st.error("❌ バックテストに成功した銘柄がありませんでした")
        
        # バックテスト結果の表示
        if st.session_state.backtest_done and st.session_state.backtest_results:
            results_df = pd.DataFrame(st.session_state.backtest_results)
            
            st.success(f"✅ {len(results_df)}銘柄のバックテスト完了！")
            
            # スタイリング関数
            def color_performance(val, column):
                """パフォーマンスに応じて色付け"""
                if column == 'Win Rate (%)':
                    if val >= 60:
                        return 'background-color: #90EE90'
                    elif val >= 50:
                        return 'background-color: #FFFFE0'
                    else:
                        return 'background-color: #FFB6C1'
                elif column == 'Profit Factor':
                    if val >= 2.0:
                        return 'background-color: #90EE90'
                    elif val >= 1.5:
                        return 'background-color: #FFFFE0'
                    else:
                        return 'background-color: #FFB6C1'
                elif column == 'Total P&L':
                    if val > 0:
                        return 'color: green; font-weight: bold'
                    elif val < 0:
                        return 'color: red; font-weight: bold'
                return ''
            
            # スタイル適用
            styled_results = results_df.style.apply(
                lambda x: [color_performance(v, c) for v, c in zip(x, results_df.columns)],
                axis=1
            ).format({
                'Win Rate (%)': '{:.2f}',
                'Total P&L': '¥{:,.0f}',
                'Avg Profit (%)': '{:.2f}',
                'Avg Loss (%)': '{:.2f}',
                'Profit Factor': '{:.2f}',
                'Max Drawdown': '¥{:,.0f}',
                'Avg Holding Days': '{:.1f}'
            })
            
            st.subheader("📊 バックテスト結果")
            st.dataframe(styled_results, use_container_width=True)
            
            # サマリー統計
            st.subheader("📈 総合サマリー")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_win_rate = results_df['Win Rate (%)'].mean()
                st.metric("平均勝率", f"{avg_win_rate:.1f}%")
            with col2:
                total_pnl = results_df['Total P&L'].sum()
                st.metric("合計損益", f"¥{total_pnl:,.0f}")
            with col3:
                avg_pf = results_df['Profit Factor'].mean()
                st.metric("平均PF", f"{avg_pf:.2f}")
            with col4:
                profitable = len(results_df[results_df['Total P&L'] > 0])
                st.metric("黒字銘柄", f"{profitable}/{len(results_df)}")
            
            # 詳細情報
            if show_details:
                st.subheader("📋 詳細分析")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**勝率トップ3**")
                    top_wr = results_df.nlargest(3, 'Win Rate (%)')[['Code', 'Name', 'Win Rate (%)']]
                    st.dataframe(top_wr, use_container_width=True, hide_index=True)
                
                with col2:
                    st.write("**利益トップ3**")
                    top_profit = results_df.nlargest(3, 'Total P&L')[['Code', 'Name', 'Total P&L']]
                    st.dataframe(top_profit, use_container_width=True, hide_index=True)
            
            # CSVダウンロード
            st.subheader("💾 データのエクスポート")
            csv = results_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 バックテスト結果をダウンロード",
                data=csv,
                file_name=f"backtest_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                key="backtest_download"
            )
    else:
        st.info("💡 銘柄を選択してバックテストを実行できます")

    # CSV ダウンロード（スクリーニング結果）
    st.header("💾 スクリーニング結果のエクスポート")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 スクリーニング結果をダウンロード",
        data=csv,
        file_name=f"screening_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="screening_download"
    )