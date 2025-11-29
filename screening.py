# screening.py
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ticker_list import sp500_list, nikkei225_list

# === 設定パラメータ ===
MA_SHORT = 7          # 短期MA
MA_MID = 20           # 中期MA
MA_LONG = 60          # 長期MA
SLOPE_THRESHOLD = 1.2 # 傾き閾値 (%)
SLOPE_PERIOD = 5      # 傾き計算期間 (日)

def get_data_and_screen_advanced(stock_list):
    
    tickers = [item["code"] for item in stock_list]
    ticker_map = {item["code"]: item["name"] for item in stock_list}

    print(f"データを取得中... (対象: {len(tickers)}銘柄)")

    try:
        data = yf.download(tickers, period="6mo", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            close_prices = data["Close"]
        else:
            close_prices = data
    except Exception as e:
        print(f"データ取得エラー: {e}")
        return pd.DataFrame()

    print("指標計算中...")

    # ======== MA のベクトル計算 ========
    ma7  = close_prices.rolling(MA_SHORT).mean()
    ma20 = close_prices.rolling(MA_MID).mean()
    ma60 = close_prices.rolling(MA_LONG).mean()

    # ======== 傾き（MA20 の5日変化率） ========
    ma20_slope = (ma20 - ma20.shift(SLOPE_PERIOD)) / ma20.shift(SLOPE_PERIOD) * 100

    # 最新データ取り出し
    latest_close = close_prices.iloc[-1]
    latest_ma7 = ma7.iloc[-1]
    latest_ma20 = ma20.iloc[-1]
    latest_ma60 = ma60.iloc[-1]
    latest_slope = ma20_slope.iloc[-1]

    # 判定結果リスト
    result = []

    for ticker in tickers:
        try:
            # MA60 が出ていない＝データ不足
            if pd.isna(latest_ma60[ticker]):
                continue

            c = latest_close[ticker]
            m7 = latest_ma7[ticker]
            m20 = latest_ma20[ticker]
            m60 = latest_ma60[ticker]
            slope = latest_slope[ticker]

            # ======== 条件判定 ========
            C1 = slope >= SLOPE_THRESHOLD
            C2 = m20 > m60
            C3 = m7 < m20
            C4 = c > m7

            signal = C1 and C2 and C3 and C4

            if C1:  # 強トレンド銘柄のみレポート
                result.append({
                    "Code": ticker,
                    "Name": ticker_map.get(ticker, ticker),
                    "Slope_MA20": slope,
                    "C1_Trend": C1,
                    "C2_Long": C2,
                    "C3_Pullback": C3,
                    "C4_Trigger": C4,
                    "All_Signal": signal
                })

        except Exception:
            continue

    df = pd.DataFrame(result)

    if df.empty:
        return df

    # ソート → 総合シグナル優先、次に傾き順
    df = df.sort_values(["All_Signal", "Slope_MA20"], ascending=[False, False])

    return df


def get_chart_data_for_ticker(ticker, period="6mo"):
    """
    個別銘柄のチャートデータを取得
    
    Parameters:
    -----------
    ticker : str
        銘柄コード
    period : str
        取得期間（デフォルト: 6ヶ月）
    
    Returns:
    --------
    daily_data : DataFrame
        日足データ
    weekly_data : DataFrame
        週足データ
    """
    try:
        # 日足データ取得
        stock = yf.Ticker(ticker)
        daily_data = stock.history(period=period)
        
        if daily_data.empty:
            return None, None
        
        # 移動平均線を計算
        daily_data['MA_short'] = daily_data['Close'].rolling(MA_SHORT).mean()
        daily_data['MA_mid'] = daily_data['Close'].rolling(MA_MID).mean()
        daily_data['MA_long'] = daily_data['Close'].rolling(MA_LONG).mean()
        
        # 週足データを作成（日足から集計）
        weekly_data = daily_data.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        # 週足の移動平均線（週足用の期間）
        weekly_data['MA_short'] = weekly_data['Close'].rolling(4).mean()  # 約1ヶ月
        weekly_data['MA_mid'] = weekly_data['Close'].rolling(13).mean()   # 約3ヶ月
        weekly_data['MA_long'] = weekly_data['Close'].rolling(26).mean()  # 約6ヶ月
        
        return daily_data, weekly_data
        
    except Exception as e:
        print(f"チャートデータ取得エラー ({ticker}): {str(e)}")
        return None, None


def plot_signal_chart(ticker, name, daily_data, weekly_data, is_japanese=False):
    """
    シグナル銘柄のチャートを描画
    
    Parameters:
    -----------
    ticker : str
        銘柄コード
    name : str
        銘柄名
    daily_data : DataFrame
        日足データ
    weekly_data : DataFrame
        週足データ
    is_japanese : bool
        日本株かどうか
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        グラフオブジェクト
    """
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # === 日足チャート ===
    # 直近60日分のみ表示
    daily_plot = daily_data.tail(60)
    
    ax1.plot(daily_plot.index, daily_plot['Close'], label='Close', linewidth=2, color='black', alpha=0.8)
    ax1.plot(daily_plot.index, daily_plot['MA_short'], label=f'MA{MA_SHORT}', linewidth=1.5, color='blue', alpha=0.7)
    ax1.plot(daily_plot.index, daily_plot['MA_mid'], label=f'MA{MA_MID}', linewidth=1.5, color='orange', alpha=0.7)
    ax1.plot(daily_plot.index, daily_plot['MA_long'], label=f'MA{MA_LONG}', linewidth=1.5, color='red', alpha=0.7)
    
    # 最新のシグナルポイントをマーク
    latest_price = daily_plot['Close'].iloc[-1]
    latest_date = daily_plot.index[-1]
    ax1.scatter(latest_date, latest_price, marker='*', color='gold', s=500, zorder=10, 
               edgecolors='red', linewidth=2, label='Signal')
    
    ax1.set_title(f'日足チャート: {name} ({ticker})', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # === 週足チャート ===
    # 直近26週分のみ表示
    weekly_plot = weekly_data.tail(26)
    
    ax2.plot(weekly_plot.index, weekly_plot['Close'], label='Close', linewidth=2, color='black', alpha=0.8)
    ax2.plot(weekly_plot.index, weekly_plot['MA_short'], label='MA4(週)', linewidth=1.5, color='blue', alpha=0.7)
    ax2.plot(weekly_plot.index, weekly_plot['MA_mid'], label='MA13(週)', linewidth=1.5, color='orange', alpha=0.7)
    ax2.plot(weekly_plot.index, weekly_plot['MA_long'], label='MA26(週)', linewidth=1.5, color='red', alpha=0.7)
    
    # 最新のシグナルポイントをマーク
    latest_price_w = weekly_plot['Close'].iloc[-1]
    latest_date_w = weekly_plot.index[-1]
    ax2.scatter(latest_date_w, latest_price_w, marker='*', color='gold', s=500, zorder=10,
               edgecolors='red', linewidth=2, label='Signal')
    
    ax2.set_title(f'週足チャート: {name} ({ticker})', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date')
    ax2.set_ylabel('Price')
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


# screening.py の最後に以下を追加

import matplotlib.pyplot as plt
import matplotlib
from matplotlib.patches import Rectangle
matplotlib.use('Agg')

# 日本語フォント設定
plt.rcParams['font.sans-serif'] = ['MS Gothic', 'Yu Gothic', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


def get_chart_data_for_ticker(ticker, period="6mo"):
    """
    個別銘柄のチャートデータを取得
    
    Parameters:
    -----------
    ticker : str
        銘柄コード
    period : str
        取得期間（デフォルト: 6ヶ月）
    
    Returns:
    --------
    daily_data : DataFrame
        日足データ
    weekly_data : DataFrame
        週足データ
    """
    try:
        # 日足データ取得
        stock = yf.Ticker(ticker)
        daily_data = stock.history(period=period)
        
        if daily_data.empty:
            return None, None
        
        # 移動平均線を計算
        daily_data['MA_short'] = daily_data['Close'].rolling(MA_SHORT).mean()
        daily_data['MA_mid'] = daily_data['Close'].rolling(MA_MID).mean()
        daily_data['MA_long'] = daily_data['Close'].rolling(MA_LONG).mean()
        
        # 週足データを作成（日足から集計）
        weekly_data = daily_data.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        # 週足の移動平均線（週足用の期間）
        weekly_data['MA_short'] = weekly_data['Close'].rolling(4).mean()  # 約1ヶ月
        weekly_data['MA_mid'] = weekly_data['Close'].rolling(13).mean()   # 約3ヶ月
        weekly_data['MA_long'] = weekly_data['Close'].rolling(26).mean()  # 約6ヶ月
        
        return daily_data, weekly_data
        
    except Exception as e:
        print(f"チャートデータ取得エラー ({ticker}): {str(e)}")
        return None, None


def _plot_candlestick(ax, data):
    """ローソク足描画ヘルパー"""
    width = 0.6
    for i, (idx, row) in enumerate(data.iterrows()):
        open_p, close_p, high_p, low_p = row['Open'], row['Close'], row['High'], row['Low']
        
        # 日本式: 赤が陽線（上昇）、青が陰線（下落）
        color = 'red' if close_p >= open_p else 'blue'
        
        # ヒゲ
        ax.plot([i, i], [low_p, high_p], color=color, linewidth=1)
        
        # 実体
        body_height = abs(close_p - open_p)
        body_bottom = min(open_p, close_p)
        rect = Rectangle((i - width/2, body_bottom), width, body_height,
                       facecolor=color, edgecolor=color, alpha=0.8)
        ax.add_patch(rect)


def plot_signal_chart(ticker, name, daily_data, weekly_data, is_japanese=False):
    """
    シグナル銘柄のチャートを描画（ローソク足版）
    
    Parameters:
    -----------
    ticker : str
        銘柄コード
    name : str
        銘柄名
    daily_data : DataFrame
        日足データ
    weekly_data : DataFrame
        週足データ
    is_japanese : bool
        日本株かどうか
    
    Returns:
    --------
    fig : matplotlib.figure.Figure
        グラフオブジェクト
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # === 日足チャート（直近3週間 = 15営業日） ===
    daily_plot = daily_data.tail(15)
    
    # ローソク足描画
    _plot_candlestick(ax1, daily_plot)
    
    # 移動平均線
    x_range = range(len(daily_plot))
    ax1.plot(x_range, daily_plot['MA_short'].values, label=f'MA{MA_SHORT}', 
            linewidth=2, color='blue', alpha=0.7)
    ax1.plot(x_range, daily_plot['MA_mid'].values, label=f'MA{MA_MID}', 
            linewidth=2, color='orange', alpha=0.7)
    ax1.plot(x_range, daily_plot['MA_long'].values, label=f'MA{MA_LONG}', 
            linewidth=1.5, color='red', alpha=0.7)
    
    # 最新のシグナルポイントをマーク
    latest_idx = len(daily_plot) - 1
    latest_price = daily_plot['Close'].iloc[-1]
    ax1.scatter(latest_idx, latest_price, marker='*', color='gold', s=400, zorder=10, 
               edgecolors='red', linewidth=2, label='Signal')
    
    # X軸の日付設定
    tick_idxs = np.linspace(0, len(daily_plot)-1, min(8, len(daily_plot)), dtype=int)
    ax1.set_xticks(tick_idxs)
    ax1.set_xticklabels([daily_plot.index[i].strftime('%m/%d') for i in tick_idxs], rotation=45)
    
    ax1.set_title(f'Daily Chart: {name} ({ticker})', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Price', fontsize=11)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # === 週足チャート（直近3ヶ月 = 13週） ===
    weekly_plot = weekly_data.tail(13)
    
    # ローソク足描画
    _plot_candlestick(ax2, weekly_plot)
    
    # 移動平均線
    x_range_w = range(len(weekly_plot))
    ax2.plot(x_range_w, weekly_plot['MA_short'].values, label='MA4(Week)', 
            linewidth=2, color='blue', alpha=0.7)
    ax2.plot(x_range_w, weekly_plot['MA_mid'].values, label='MA13(Week)', 
            linewidth=2, color='orange', alpha=0.7)
    ax2.plot(x_range_w, weekly_plot['MA_long'].values, label='MA26(Week)', 
            linewidth=1.5, color='red', alpha=0.7)
    
    # 最新のシグナルポイントをマーク
    latest_idx_w = len(weekly_plot) - 1
    latest_price_w = weekly_plot['Close'].iloc[-1]
    ax2.scatter(latest_idx_w, latest_price_w, marker='*', color='gold', s=400, zorder=10,
               edgecolors='red', linewidth=2, label='Signal')
    
    # X軸の日付設定
    tick_idxs_w = np.linspace(0, len(weekly_plot)-1, min(6, len(weekly_plot)), dtype=int)
    ax2.set_xticks(tick_idxs_w)
    ax2.set_xticklabels([weekly_plot.index[i].strftime('%m/%d') for i in tick_idxs_w], rotation=45)
    
    ax2.set_title(f'Weekly Chart: {name} ({ticker})', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Date', fontsize=11)
    ax2.set_ylabel('Price', fontsize=11)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig