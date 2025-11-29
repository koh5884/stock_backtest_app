import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class TradingRules:
    """トレードルールの設定を管理するクラス"""

    def __init__(self):
        # === 移動平均線の設定 ===
        self.ma_short = 7   # 短期MA（日足）
        self.ma_mid = 20    # 中期MA（日足）
        self.ma_long = 60   # 長期MA（日足）

        # === エントリー条件 ===
        self.slope_threshold = 1.2  # 傾き閾値 (%)
        self.slope_period = 5       # 傾き計算期間 (日)

        # === エグジット条件 ===
        self.stop_loss_percentage = 0.98  # 損切り (2%)
        self.stop_loss_lookback = 5       # 直近安値を何日分見るか

        # === 表示設定 ===
        self.show_detailed_charts = False


class SwingTradeBacktest:
    """シンプル化されたバックテストクラス（Streamlit統合用）"""

    def __init__(self, ticker, start_date, end_date, rules=None):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.rules = rules if rules else TradingRules()
        self.daily_data = None
        self.trades = []

    def fetch_data(self):
        """データ取得（エラーハンドリング強化）"""
        try:
            extended_start = (pd.to_datetime(self.start_date) - timedelta(days=400)).strftime('%Y-%m-%d')
            stock = yf.Ticker(self.ticker)
            self.daily_data = stock.history(start=extended_start, end=self.end_date)

            if self.daily_data.empty:
                raise ValueError(f"データが取得できませんでした: {self.ticker}")
            
            # データクリーニング
            self.daily_data = self.daily_data[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
            
        except Exception as e:
            raise Exception(f"データ取得エラー ({self.ticker}): {str(e)}")

    def calculate_indicators(self):
        """指標計算"""
        df = self.daily_data.copy()

        # 移動平均線
        df['MA_short'] = df['Close'].rolling(window=self.rules.ma_short).mean()
        df['MA_mid'] = df['Close'].rolling(window=self.rules.ma_mid).mean()
        df['MA_long'] = df['Close'].rolling(window=self.rules.ma_long).mean()

        # 傾き計算
        df['MA_mid_slope'] = (df['MA_mid'] - df['MA_mid'].shift(self.rules.slope_period)) / \
                             df['MA_mid'].shift(self.rules.slope_period) * 100

        # 直近安値
        df['Recent_Low'] = df['Low'].rolling(window=self.rules.stop_loss_lookback).min()

        self.daily_data = df

    def generate_signals(self):
        """シグナル生成（シンプル化）"""
        df = self.daily_data.copy()
        df = df[df.index >= self.start_date]

        position = None
        entry_signal_date = None

        for i in range(1, len(df)):
            current_date = df.index[i]
            prev_date = df.index[i-1]
            current = df.iloc[i]
            prev = df.iloc[i-1]

            # エントリー処理
            if position is None:
                if entry_signal_date == prev_date:
                    entry_price = current['Open']
                    stop_loss = prev['Recent_Low'] * self.rules.stop_loss_percentage

                    position = {
                        'entry_date': current_date,
                        'entry_price': entry_price,
                        'stop_loss': stop_loss
                    }
                    entry_signal_date = None
                    continue

                # エントリーシグナル判定
                if pd.notna(current['MA_short']) and pd.notna(current['MA_mid']) and pd.notna(current['MA_long']):
                    # 条件1: 押し目形成
                    pullback = current['MA_short'] < current['MA_mid']
                    
                    # 条件2: トレンド確認
                    ma_trending = pd.notna(current['MA_mid_slope']) and \
                                current['MA_mid_slope'] > self.rules.slope_threshold
                    
                    # 条件3: 長期上昇トレンド
                    long_trend = current['MA_mid'] > current['MA_long']
                    
                    # 条件4: エントリートリガー
                    entry_trigger = current['High'] >= current['MA_short']

                    if pullback and ma_trending and long_trend and entry_trigger:
                        entry_signal_date = current_date

            # エグジット処理
            else:
                # 損切り
                if current['Close'] <= position['stop_loss']:
                    exit_date = current_date
                    exit_price = current['Close']
                    exit_reason = 'Stop Loss'
                    
                    self._record_trade(position, exit_date, exit_price, exit_reason)
                    position = None
                
                # MA5クロス決済
                elif pd.notna(current['MA_short']) and current['Close'] < current['MA_short']:
                    if i+1 < len(df):
                        exit_date = df.index[i+1]
                        exit_price = df.iloc[i+1]['Open']
                    else:
                        exit_date = current_date
                        exit_price = current['Close']
                    exit_reason = 'MA Cross'
                    
                    self._record_trade(position, exit_date, exit_price, exit_reason)
                    position = None

    def _record_trade(self, position, exit_date, exit_price, exit_reason):
        """トレード記録"""
        profit = exit_price - position['entry_price']
        profit_pct = (exit_price / position['entry_price'] - 1) * 100
        holding_days = (exit_date - position['entry_date']).days

        self.trades.append({
            'entry_date': position['entry_date'],
            'exit_date': exit_date,
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'profit': profit,
            'profit_pct': profit_pct,
            'exit_reason': exit_reason,
            'holding_days': holding_days
        })

    def calculate_performance(self):
        """パフォーマンス計算"""
        if len(self.trades) == 0:
            return None

        trades_df = pd.DataFrame(self.trades)

        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['profit'] > 0])
        losing_trades = len(trades_df[trades_df['profit'] <= 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0

        total_profit = trades_df['profit'].sum()
        avg_profit = trades_df[trades_df['profit'] > 0]['profit'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['profit'] <= 0]['profit'].mean() if losing_trades > 0 else 0
        avg_profit_pct = trades_df[trades_df['profit'] > 0]['profit_pct'].mean() if winning_trades > 0 else 0
        avg_loss_pct = trades_df[trades_df['profit'] <= 0]['profit_pct'].mean() if losing_trades > 0 else 0

        trades_df['cumulative_profit'] = trades_df['profit'].cumsum()
        trades_df['running_max'] = trades_df['cumulative_profit'].cummax()
        trades_df['drawdown'] = trades_df['cumulative_profit'] - trades_df['running_max']
        max_drawdown = trades_df['drawdown'].min()

        avg_holding_days = trades_df['holding_days'].mean()

        self.performance = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_profit': total_profit,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'avg_profit_pct': avg_profit_pct,
            'avg_loss_pct': avg_loss_pct,
            'max_drawdown': max_drawdown,
            'avg_holding_days': avg_holding_days,
            'profit_factor': abs(avg_profit / avg_loss) if avg_loss != 0 else 0
        }

        self.trades_df = trades_df
        return self.performance

    def run(self, show_charts=False, show_detailed=False):
        """バックテスト実行"""
        self.fetch_data()
        self.calculate_indicators()
        self.generate_signals()
        return self.calculate_performance()