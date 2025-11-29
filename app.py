import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt # グラフ表示に必要
from datetime import timedelta # 期間計算に必要

# 既存ファイルのインポート
from ticker_list import sp500_list, nikkei225_list
from screening import MA_SHORT, MA_MID, MA_LONG, SLOPE_THRESHOLD, SLOPE_PERIOD
from screening import get_data_and_screen_advanced
# バックテストクラスのインポート
from backtest import SwingTradeBacktest, TradingRules 


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

# 単一銘柄バックテスト用の初期化
if 'single_ticker_result' not in st.session_state:
    st.session_state.single_ticker_result = None


# =======================================================
# ⚙️ 関数定義: スクリーニング→バックテストページ
# =======================================================
def run_screening_page():
    st.markdown("**順張り押し目買い戦略**のスクリーニングツールです。スクリーニング対象を選択し、下のボタンからスクリーニングを開始してください。")

    # --- サイドバー ---
    st.sidebar.header("スクリーニング対象")
    market_selection = st.sidebar.radio(
        "市場を選択",
        ("S&P 500（米国株）", "日経225（日本株）"),
        index=0 # デフォルトはS&P 500
    )

    # 銘柄リストの決定
    stock_list = []
    if market_selection == "S&P 500（米国株）":
        stock_list = sp500_list
    elif market_selection == "日経225（日本株）":
        stock_list = nikkei225_list

    # --- スクリーニング ---
    st.header("🔍 スクリーニング実行")

    if not stock_list:
        st.warning("⚠️ スクリーニング対象を選択してください（サイドバー）")
    else:
        if st.button("スクリーニング開始！", key="screening_button"):
            # データ期間を計算
            screening_end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
            screening_start_date = (pd.Timestamp.now() - pd.Timedelta(days=180)).strftime('%Y-%m-%d')
            
            with st.spinner(f"分析中...（対象: {len(stock_list)}銘柄）"):
                df = get_data_and_screen_advanced(stock_list)
                
                # 通貨判定（.Tが含まれていれば日本株）
                is_japanese = any('.T' in item['code'] for item in stock_list if isinstance(item, dict))
                currency = '円' if is_japanese else 'ドル'
                currency_symbol = 'JPY' if is_japanese else 'USD'
                
                if df.empty:
                    st.session_state.screening_done = False
                    st.session_state.screening_df = None
                    st.session_state.currency = None
                    st.session_state.screening_period = None
                    st.warning("❌ 条件に該当する銘柄がありませんでした")
                    st.info(f"""
                    **スクリーニング条件:**
                    - 分析期間: {screening_start_date} ～ {screening_end_date}（過去6ヶ月のデータを使用）
                    - MA{MA_SHORT} < MA{MA_MID} < MA{MA_LONG}（押し目形成）
                    - MA{MA_MID}の傾き ≥ {SLOPE_THRESHOLD}%（強いトレンド）
                    - 直近価格 > MA{MA_SHORT}（反転シグナル）
                    """)
                else:
                    st.session_state.screening_done = True
                    st.session_state.screening_df = df
                    st.session_state.backtest_done = False
                    st.session_state.currency = currency
                    st.session_state.currency_symbol = currency_symbol
                    st.session_state.screening_period = f"{screening_start_date} ～ {screening_end_date}"

    # スクリーニング結果の表示
    if st.session_state.screening_done and st.session_state.screening_df is not None:
        df = st.session_state.screening_df
        currency = st.session_state.currency
        currency_symbol = st.session_state.currency_symbol
        screening_period = st.session_state.screening_period
        
        st.success(f"✅ {len(df)} 銘柄がヒット！")

        # 表示
        st.subheader("📊 スクリーニング結果")
        st.caption(f"""
        **分析期間**: {screening_period}（過去6ヶ月のデータを使用）  
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

        # 銘柄選択
        st.header("📌 バックテスト")
        
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
            
            # バックテスト設定
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
                
                st.session_state.backtest_period = f"{start_date} ～ {end_date}"
                
                backtest_results = []
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for idx, ticker in enumerate(selected):
                    status_text.text(f"バックテスト実行中... {ticker} ({idx+1}/{len(selected)})")
                    progress_bar.progress((idx + 1) / len(selected))
                    
                    try:
                        rules = TradingRules()
                        bt = SwingTradeBacktest(ticker, start_date, end_date, rules)
                        perf = bt.run(show_charts=False, show_detailed=False)
                        
                        if perf:
                            # 銘柄名を取得
                            name = df[df['Code']==ticker]['Name'].values[0]

                            # 結果リストへの追加
                            backtest_results.append({
                                'Code': ticker,
                                'Name': name,
                                'Total Trades': perf['total_trades'],
                                'Win Rate (%)': perf['win_rate'],
                                'Total P&L': perf['total_profit'],
                                'Avg Profit (%)': perf['avg_profit_pct'],
                                'Avg Loss (%)': perf['avg_loss_pct'],
                                'Profit Factor': perf['profit_factor'],
                                'Max Drawdown': perf['max_drawdown'],
                                'Avg Holding Days': perf['avg_holding_days']
                            })
                            
                            # === グラフ表示部分の追加（銘柄名を使用） ===
                            if show_details:
                                with st.expander(f"📈 {name} ({ticker}) の詳細チャート・トレード履歴を見る"):
                                    # 1. 全体オーバービュー
                                    st.subheader("全体推移")
                                    fig_overview = bt.plot_overview()
                                    if fig_overview:
                                        st.pyplot(fig_overview)
                                        plt.close(fig_overview) # メモリ解放
                                    
                                    # 2. 個別トレード（すべて表示）
                                    st.subheader("個別トレード詳細")
                                    if perf['total_trades'] > 0:
                                        trade_figs = bt.plot_all_trades()
                                        for i, fig in enumerate(trade_figs):
                                            st.caption(f"Trade #{i+1}")
                                            st.pyplot(fig)
                                            plt.close(fig) # メモリ解放
                                    else:
                                        st.info("トレードはありませんでした。")

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
            
            # バックテスト結果の表示（ここは if selected の中、かつ if button の外）
            if st.session_state.backtest_done and st.session_state.backtest_results:
                results_df = pd.DataFrame(st.session_state.backtest_results)
                backtest_period_display = st.session_state.backtest_period
                
                st.success(f"✅ {len(results_df)}銘柄のバックテスト完了！")
                
                st.info(f"""
                **バックテスト期間**: {backtest_period_display}  
                **通貨単位**: {currency}
                """)
                
                # スタイリング関数
                def color_performance(val, column):
                    if column == 'Win Rate (%)':
                        if val >= 60: return 'background-color: #90EE90'
                        elif val >= 50: return 'background-color: #FFFFE0'
                        else: return 'background-color: #FFB6C1'
                    elif column == 'Profit Factor':
                        if val >= 2.0: return 'background-color: #90EE90'
                        elif val >= 1.5: return 'background-color: #FFFFE0'
                        else: return 'background-color: #FFB6C1'
                    elif column == 'Total P&L':
                        if val > 0: return 'color: green; font-weight: bold'
                        elif val < 0: return 'color: red; font-weight: bold'
                    return ''
                
                if currency_symbol == 'JPY':
                    curr_prefix = '¥'
                else:
                    curr_prefix = '$'
                
                styled_results = results_df.style.apply(
                    lambda x: [color_performance(v, c) for v, c in zip(x, results_df.columns)],
                    axis=1
                ).format({
                    'Win Rate (%)': '{:.2f}',
                    'Total P&L': f'{curr_prefix}{{:,.0f}}',
                    'Avg Profit (%)': '{:.2f}',
                    'Avg Loss (%)': '{:.2f}',
                    'Profit Factor': '{:.2f}',
                    'Max Drawdown': f'{curr_prefix}{{:,.0f}}',
                    'Avg Holding Days': '{:.1f}'
                })
                
                st.subheader("📊 バックテスト結果")
                st.dataframe(styled_results, use_container_width=True)
                
                # サマリー統計
                st.subheader("📈 総合サマリー")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("平均勝率", f"{results_df['Win Rate (%)'].mean():.1f}%")
                with col2:
                    st.metric("合計損益", f"{curr_prefix}{results_df['Total P&L'].sum():,.0f}")
                with col3:
                    st.metric("平均PF", f"{results_df['Profit Factor'].mean():.2f}")
                with col4:
                    profitable = len(results_df[results_df['Total P&L'] > 0])
                    st.metric("黒字銘柄", f"{profitable}/{len(results_df)}")


# =======================================================
# 🎯 関数定義: 単一銘柄バックテストページ
# =======================================================
def run_single_backtest_page():
    st.title("🎯 バックテスト")
    st.markdown("銘柄コードと期間を入力し、バックテストを実行します。")
    
    # 1. 入力フォーム
    col1, col2 = st.columns([1, 1])
    with col1:
        ticker_input = st.text_input("銘柄コードを入力 (例: 日本株なら「6920.T」, 米株なら「AAPL」)", key="single_ticker_input").strip().upper()
    with col2:
        backtest_period = st.selectbox(
            "バックテスト期間",
            ["1年", "2年", "3年", "5年"],
            index=2,
            key="single_period_select"
        )
        
    # 期間計算ロジック
    period_map = {"1年": 365, "2年": 730, "3年": 1095, "5年": 1825}
    days = period_map[backtest_period]
    end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime('%Y-%m-%d')
    
    st.info(f"バックテスト期間: **{start_date} ～ {end_date}**")

    if st.button("🚀 バックテスト実行", type="primary", key="single_backtest_button"):
        if not ticker_input:
            st.error("銘柄コードを入力してください。")
            return

        st.session_state.single_ticker_result = None
        
        with st.spinner(f"バックテスト実行中: {ticker_input}..."):
            try:
                # backtest.py のクラスを直接使用
                rules = TradingRules()
                bt = SwingTradeBacktest(ticker_input, start_date, end_date, rules)
                perf = bt.run() 
                
                if perf:
                    # 通貨判定とシンボル設定
                    is_japanese = '.T' in ticker_input
                    currency = '円' if is_japanese else 'ドル'
                    curr_prefix = '¥' if is_japanese else '$'
                    
                    # 銘柄名が不明なため、コードをそのまま名前にする
                    name = ticker_input
                    
                    # 結果をDataFrameとしてセッションに保存
                    result_df = pd.DataFrame([{
                        'Code': ticker_input,
                        'Name': name,
                        'Total Trades': perf['total_trades'],
                        'Win Rate (%)': perf['win_rate'],
                        'Total P&L': perf['total_profit'],
                        'Avg Profit (%)': perf['avg_profit_pct'],
                        'Avg Loss (%)': perf['avg_loss_pct'],
                        'Profit Factor': perf['profit_factor'],
                        'Max Drawdown': perf['max_drawdown'],
                        'Avg Holding Days': perf['avg_holding_days']
                    }])
                    
                    st.session_state.single_ticker_result = {
                        'df': result_df,
                        'bt_object': bt, # グラフ描画用にbtオブジェクトを保存
                        'curr_prefix': curr_prefix,
                        'currency': currency
                    }
                    st.success("バックテストが完了しました。")
                    
                else:
                    st.info(f"トレードがありませんでした: {ticker_input}")

            except Exception as e:
                st.error(f"⚠️ バックテスト中にエラーが発生しました: {str(e)}")
    
    # 2. 結果の表示 (session_stateに結果があれば表示)
    if 'single_ticker_result' in st.session_state and st.session_state.single_ticker_result:
        result = st.session_state.single_ticker_result
        results_df = result['df']
        bt = result['bt_object']
        ticker = results_df.iloc[0]['Code']
        name = results_df.iloc[0]['Name']
        curr_prefix = result['curr_prefix']
        currency = result['currency']

        # スタイリング関数 (一括テストと共通)
        def color_performance(val, column):
            if column == 'Win Rate (%)':
                if val >= 60: return 'background-color: #90EE90'
                elif val >= 50: return 'background-color: #FFFFE0'
                else: return 'background-color: #FFB6C1'
            elif column == 'Profit Factor':
                if val >= 2.0: return 'background-color: #90EE90'
                elif val >= 1.5: return 'background-color: #FFFFE0'
                else: return 'background-color: #FFB6C1'
            elif column == 'Total P&L':
                if val > 0: return 'color: green; font-weight: bold'
                elif val < 0: return 'color: red; font-weight: bold'
            return ''
        
        styled_results = results_df.style.apply(
            lambda x: [color_performance(v, c) for v, c in zip(x, results_df.columns)],
            axis=1
        ).format({
            'Win Rate (%)': '{:.2f}',
            'Total P&L': f'{curr_prefix}{{:,.0f}}',
            'Avg Profit (%)': '{:.2f}',
            'Avg Loss (%)': '{:.2f}',
            'Profit Factor': '{:.2f}',
            'Max Drawdown': f'{curr_prefix}{{:,.0f}}',
            'Avg Holding Days': '{:.1f}'
        })

        # パフォーマンス表
        st.subheader("📊 パフォーマンス結果")
        st.info(f"**通貨単位**: {currency}")
        st.dataframe(styled_results, use_container_width=True, hide_index=True)
        st.markdown("---")
        
        # グラフ表示
        st.subheader("詳細チャート")
        
        with st.expander(f"📈 {name} ({ticker}) の詳細チャート・トレード履歴を見る", expanded=True):
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


# =======================================================
# 🚀 メインのコントロールフロー
# =======================================================

# ナビゲーションの配置
st.sidebar.title("メニュー")
page_selection = st.sidebar.radio("機能を選択", ["1. 株式スクリーニング＆バックテスト", "2. バックテストのみ"])

# 選択された機能の実行
if page_selection == "1. 株式スクリーニング＆バックテスト":
    run_screening_page()
    
elif page_selection == "2. バックテストのみ":
    run_single_backtest_page()