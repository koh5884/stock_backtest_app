# screening.py
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
# from ticker_list import sp500_list, nikkei225_list # 不要なインポートを削除

# === 設定パラメータ ===
MA_SHORT = 7          # 短期MA
MA_MID = 20           # 中期MA
MA_LONG = 60          # 長期MA
SLOPE_THRESHOLD = 1.2 # 傾き閾値 (%)
SLOPE_PERIOD = 5      # 傾き計算期間 (日)

def get_data_and_screen_advanced(stock_list):
    
    tickers = [item["code"] for item in stock_list]
    ticker_map = {item["code"]: item["name"] for item in stock_list}

    # print(f"データを取得中... (対象: {len(tickers)}銘柄)") # 削除

    try:
        data = yf.download(tickers, period="6mo", progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            close_prices = data["Close"]
        else:
            close_prices = data
    except Exception: # エラーメッセージを削除
        return pd.DataFrame()

    # print("指標計算中...") # 削除

    # ======== MA のベクトル計算 ========
    ma7  = close_prices.rolling(MA_SHORT).mean()
    ma20 = close_prices.rolling(MA_MID).mean()
    ma60 = close_prices.rolling(MA_LONG).mean()
    
    # MA20の傾き (変化率)
    ma20_slope = (ma20 / ma20.shift(SLOPE_PERIOD) - 1) * 100

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
            C1 = slope >= SLOPE_THRESHOLD   # C1: 強トレンド (MA20の傾き)
            C2 = m20 > m60                  # C2: 長期トレンド (MA20 > MA60)
            C3 = m7 < m20                   # C3: 押し目形成 (MA7 < MA20)
            C4 = c > m7                     # C4: 反転シグナル (Close > MA7)

            signal = C1 and C2 and C3 and C4

            if C1:  # 強トレンド銘柄のみレポート
                result.append({
                    "Code": ticker,
                    "Name": ticker_map.get(ticker, ticker),
                    "Close": c,
                    "MA7": m7,
                    "MA20": m20,
                    "MA60": m60,
                    "Slope_MA20": slope,
                    "C1_Trend": C1,
                    "C2_Long": C2,
                    "C3_Pullback": C3,
                    "C4_Trigger": C4,
                    "All_Signal": signal,
                })

        except KeyError:
            # データがない銘柄はスキップ
            continue
        except Exception:
            # その他エラーもスキップ
            continue

    return pd.DataFrame(result)