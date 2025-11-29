import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt # グラフ表示に必要
from datetime import timedelta # 期間計算に必要

# 既存ファイルのインポート
from ticker_list import sp500_list, nikkei225_list
# MA定数とスクリーニング関数のインポート
from screening import MA_SHORT, MA_MID, MA_LONG, SLOPE_THRESHOLD, SLOPE_PERIOD
from screening import get_data_and_screen_advanced
# バックテストクラスとチャート描画関数のインポート (plot_current_statusを追加)
from backtest import SwingTradeBacktest, TradingRules, plot_current_status 


st.set_page_config(page_title="よこへトレード支援アプリ", page_icon="📈", layout="wide")


# =======================================================
# 📌 セッション状態の初期化
# =======================================================
if 'screening_done' not in st.session_state:
    st.session_state.screening_done = False
if 'screening_df' not in st.session_state:
    st.session_state.screening_df = None
if 'backtest_done' not in st.session_state:
    st.session_state.backtest_done = False
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'currency' not in st.session_state:
    st.session_state.currency = None
if 'currency_symbol' not in st.session_state:
    st.session_state.currency_symbol = None
if 'screening_period' not in st.session_state:
    st.session_state.screening_period = None
if 'backtest_period' not in st.session_state:
    st.session_state.backtest_period = None

st.title("📈 株式スクリーニング＆バックテスト")
st.markdown("""
このアプリは、指定された市場リストに対して、特定の移動平均線（MA）に基づくスイングトレード戦略のスクリーニングとバックテストを実行します。
""")

# =======================================================
# ⚙️ サイドバーの設定
# =======================================================
st.sidebar.title("設定")

# 1. 市場選択
market = st.sidebar.selectbox(
    "市場を選択",
    ["日経225 (日本)", "S&P 500 (米国)"],
    key="market"
)
stock_list = nikkei225_list if market == "日経225 (日本)" else sp500_list

# 2. 期間設定 (ここではユーザーが触れないように非表示)
st.session_state.screening_period = st.sidebar.text_input("スクリーニングデータ期間 (固定)", "6ヶ月", disabled=True)
st.session_state.backtest_period = st.sidebar.text_input("バックテスト期間 (固定)", "2023-01-01 ～ 2024-01-01", disabled=True)

# 3. MA設定（TradingRulesクラスの値を初期値とする）
st.sidebar.subheader("移動平均線パラメータ")
ma_short = st.sidebar.number_input("短期MA (MA_SHORT)", min_value=1, value=MA_SHORT)
ma_mid = st.sidebar.number_input("中期MA (MA_MID)", min_value=1, value=MA_MID)
ma_long = st.sidebar.number_input("長期MA (MA_LONG)", min_value=1, value=MA_LONG)

# 4. 傾き設定
st.sidebar.subheader("トレンド傾きフィルタ")
slope_threshold = st.sidebar.number_input("MA20傾き閾値 (%)", value=SLOPE_THRESHOLD, step=0.1)
slope_period = st.sidebar.number_input("傾き計算期間 (日)", value=SLOPE_PERIOD, min_value=1)

# 5. 実行ボタン
if st.sidebar.button("スクリーニング開始"):
    st.session_state.screening_done = False
    st.session_state.backtest_done = False
    st.session_state.backtest_results = None
    
    with st.spinner(f"{market} の {len(stock_list)} 銘柄に対してスクリーニングを実行中..."):
        # スクリーニング実行
        screening_df = get_data_and_screen_advanced(stock_list, ma_short, ma_mid, ma_long, slope_threshold, slope_period)
        
        # 結果をセッションに保存
        st.session_state.screening_df = screening_df
        st.session_state.screening_done = True
        
        # 通貨シンボルの設定 (簡易)
        if market == "日経225 (日本)":
            st.session_state.currency = "JPY"
            st.session_state.currency_symbol = "¥"
        else:
            st.session_state.currency = "USD"
            st.session_state.currency_symbol = "$"
            
        st.rerun() # 結果表示のために再実行


# =======================================================
# ➡️ スクリーニング結果の表示
# =======================================================
if st.session_state.screening_done and st.session_state.screening_df is not None:
    
    screening_df = st.session_state.screening_df
    
    st.header("1. スクリーニング結果")
    st.info(f"合計 {len(stock_list)} 銘柄中、{len(screening_df)} 銘柄が**中期トレンド条件 (C1)** を満たしました。")
    
    if screening_df.empty:
        st.warning("条件を満たす銘柄は見つかりませんでした。")
    else:
        # 表示調整
        display_df = screening_df.copy()
        display_df.rename(columns={
            "Slope_MA20": "MA20傾き(%)",
            "C1_Trend": "C1 (トレンド)",
            "C2_MA": "C2 (MA長)",
            "C3_Pullback": "C3 (押し目)",
            "C4_Trigger": "C4 (トリガー)",
            "All Signal": "All Signal"
        }, inplace=True)
        
        # スタイル設定
        def color_signal(val):
            color = 'background-color: #d4edda; color: #155724' if val is True else ''
            return color
        
        styled_df = display_df.style.map(color_signal, subset=['C1 (トレンド)', 'C2 (MA長)', 'C3 (押し目)', 'C4 (トリガー)', 'All Signal'])
        
        # DataFrame表示
        st.subheader("✅ 抽出銘柄リスト")
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # =======================================================
        # 🆕 新機能: All Signal点灯銘柄の最新チャート表示
        # =======================================================
        signal_tickers = screening_df[screening_df['All Signal'] == True]['Code'].tolist()
        
        if signal_tickers:
            st.header("2. All Signal点灯銘柄の最新チャート")
            st.info(f"**{len(signal_tickers)}** 銘柄がすべての条件を満たしています。日足・週足の最新チャートを表示します。")
            
            # MA設定を渡すためのTradingRulesインスタンスを作成
            rules = TradingRules()
            rules.ma_short = ma_short
            rules.ma_mid = ma_mid
            rules.ma_long = ma_long
            
            for ticker in signal_tickers:
                # 銘柄名を取得
                name = screening_df[screening_df['Code'] == ticker]['Name'].iloc[0]
                st.subheader(f"🚀 {name} ({ticker})")
                
                col_daily, col_weekly = st.columns(2)
                
                # 日足チャート (1d)
                with col_daily:
                    st.caption("日足チャート (Daily)")
                    fig_daily = plot_current_status(ticker, '1d', rules)
                    if fig_daily:
                        st.pyplot(fig_daily)
                        plt.close(fig_daily)
                    else:
                        st.warning("日足チャートデータが取得できませんでした。")
                        
                # 週足チャート (1wk)
                with col_weekly:
                    st.caption("週足チャート (Weekly)")
                    fig_weekly = plot_current_status(ticker, '1wk', rules)
                    if fig_weekly:
                        st.pyplot(fig_weekly)
                        plt.close(fig_weekly)
                    else:
                        st.warning("週足チャートデータが取得できませんでした。")

                st.markdown("---")

        
        # =======================================================
        # 3. バックテスト実行コントロール
        # =======================================================
        st.header("3. バックテスト実行")
        
        # バックテスト対象銘柄
        default_bt_tickers = screening_df[screening_df['All Signal'] == True]['Code'].tolist()
        if not default_bt_tickers:
            st.warning("すべての条件を満たす銘柄がないため、バックテストは実行できません。")
            bt_tickers = []
        else:
            # ユーザーが選択できるようにする
            st.caption(f"推奨：**All Signal点灯銘柄 ({len(default_bt_tickers)}件)**")
            selected_tickers = st.multiselect(
                "バックテストを実行する銘柄を選択 (最大20件推奨)",
                options=screening_df['Code'].tolist(),
                default=default_bt_tickers,
                key="bt_tickers_select"
            )
            bt_tickers = selected_tickers
        
        
        # バックテスト実行
        if st.button("バックテスト開始", disabled=not bt_tickers) and bt_tickers:
            st.session_state.backtest_results = []
            st.session_state.backtest_done = False
            
            start_date = '2023-01-01'
            end_date = '2024-01-01'

            # MA設定を渡すためのTradingRulesインスタンスを作成
            rules = TradingRules()
            rules.ma_short = ma_short
            rules.ma_mid = ma_mid
            rules.ma_long = ma_long
            
            with st.spinner(f"選択された {len(bt_tickers)} 銘柄に対してバックテストを実行中 ({start_date}〜{end_date})..."):
                
                ticker_map = {row['Code']: row['Name'] for _, row in screening_df.iterrows()}
                
                for ticker in bt_tickers:
                    try:
                        bt = SwingTradeBacktest(ticker, start_date, end_date, rules)
                        perf = bt.run()
                        
                        if perf is not None:
                            # 成功した銘柄のみ結果をリストに追加
                            result_data = {
                                'Code': ticker,
                                'Name': ticker_map.get(ticker, ticker),
                                'Total Trades': perf['total_trades'],
                                'Win Rate (%)': perf['win_rate'],
                                'Profit Factor': perf['profit_factor'],
                                'Total P&L': perf['total_profit'],
                                'Avg Holding Days': perf['avg_holding_days'],
                                'Max Drawdown': perf['max_drawdown'],
                                'BT_Object': bt  # 後でグラフ描画用にオブジェクトを保存
                            }
                            st.session_state.backtest_results.append(result_data)
                            st.caption(f"✅ {ticker_map.get(ticker, ticker)} ({ticker}): バックテストに成功")
                        else:
                            st.caption(f"⚠️ {ticker_map.get(ticker, ticker)} ({ticker}): バックテストは実行されましたが、データ不足またはトレードなしで結果が得られませんでした。")
                            
                    except Exception as e:
                        st.caption(f"❌ {ticker_map.get(ticker, ticker)} ({ticker}): エラーが発生しました - {e}")
                        
            st.session_state.backtest_done = True
            st.rerun() # 結果表示のために再実行


# =======================================================
# ➡️ バックテスト結果の表示
# =======================================================
if st.session_state.backtest_done and st.session_state.backtest_results:
    
    st.header("4. バックテスト結果サマリー")
    
    results = st.session_state.backtest_results
    
    if not results:
        st.error("❌ バックテストに成功した銘柄がありませんでした。")
    else:
        # 結果リストをDataFrameに変換
        results_df = pd.DataFrame(results)
        
        # 通貨情報
        currency = st.session_state.currency
        curr_prefix = st.session_state.currency_symbol

        # スタイル設定
        styled_results = results_df.drop(columns=['BT_Object']).style.format({
            'Win Rate (%)': '{:.1f}%',
            'Profit Factor': '{:.2f}',
            'Total P&L': f'{curr_prefix}{{:,0f}}',
            'Max Drawdown': f'{curr_prefix}{{:,0f}}',
            'Avg Holding Days': '{:.1f}'
        })

        # パフォーマンス表
        st.subheader("📊 パフォーマンス結果")
        st.info(f"**通貨単位**: {currency}")
        st.dataframe(styled_results, use_container_width=True, hide_index=True)
        st.markdown("---")
        
        # サマリー統計
        st.subheader("📈 総合サマリー")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_win_rate = results_df['Win Rate (%)'].mean()
            st.metric("平均勝率", f"{avg_win_rate:.1f}%")
        with col2:
            total_pnl = results_df['Total P&L'].sum()
            st.metric("合計損益", f"{curr_prefix}{total_pnl:,.0f}")
        with col3:
            avg_pf = results_df['Profit Factor'].mean()
            st.metric("平均PF", f"{avg_pf:.2f}")
        with col4:
            profitable = len(results_df[results_df['Total P&L'] > 0])
            st.metric("黒字銘柄", f"{profitable}/{len(results_df)}")
        
        # 詳細情報
        show_details = st.checkbox("詳細分析を表示", value=False)
        if show_details:
            st.subheader("📋 詳細分析")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**勝率トップ3**")
                top_wr = results_df.nlargest(3, 'Win Rate (%)')[['Code', 'Name', 'Win Rate (%)']]
                st.dataframe(top_wr, use_container_width=True, hide_index=True)
            
            with col2:
                st.write("**合計損益トップ3**")
                top_pnl = results_df.nlargest(3, 'Total P&L')[['Code', 'Name', 'Total P&L']]
                top_pnl_styled = top_pnl.style.format({'Total P&L': f'{curr_prefix}{{:,0f}}'})
                st.dataframe(top_pnl_styled, use_container_width=True, hide_index=True)


        # グラフ表示
        st.markdown("---")
        st.header("5. 個別バックテスト詳細チャート")
        
        # 銘柄ごとのチャート表示
        for result in results:
            bt = result['BT_Object']
            ticker = result['Code']
            name = result['Name']
            
            with st.expander(f"📈 {name} ({ticker}) の詳細チャート・トレード履歴を見る", expanded=False):
                # 1. 全体オーバービュー
                st.subheader("全体推移")
                fig_overview = bt.plot_overview()
                if fig_overview:
                    st.pyplot(fig_overview)
                    plt.close(fig_overview)
                
                # 2. 個別トレード（すべて表示）
                st.subheader("個別トレード詳細")
                if bt.trades_df is not None and len(bt.trades_df) > 0:
                    trade_figs = bt.plot_all_trades()
                    for i, fig in enumerate(trade_figs):
                        st.caption(f"Trade #{i+1}")
                        st.pyplot(fig)
                        plt.close(fig)
                else:
                    st.info("トレードはありませんでした。")