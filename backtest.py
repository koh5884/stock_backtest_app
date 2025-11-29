import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from datetime import datetime, timedelta
import warnings

# Streamlitでの描画用にバックエンド設定
import matplotlib
matplotlib.use('Agg')  

warnings.filterwarnings('ignore')


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
        self.trades_df = None
        self.performance = None

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

        total_profit = float(trades_df['profit'].sum())
        avg_profit = float(trades_df[trades_df['profit'] > 0]['profit'].mean()) if winning_trades > 0 else 0
        avg_loss = float(trades_df[trades_df['profit'] <= 0]['profit'].mean()) if losing_trades > 0 else 0
        avg_profit_pct = float(trades_df[trades_df['profit'] > 0]['profit_pct'].mean()) if winning_trades > 0 else 0
        avg_loss_pct = float(trades_df[trades_df['profit'] <= 0]['profit_pct'].mean()) if losing_trades > 0 else 0

        trades_df['cumulative_profit'] = trades_df['profit'].cumsum()
        trades_df['running_max'] = trades_df['cumulative_profit'].cummax()
        trades_df['drawdown'] = trades_df['cumulative_profit'] - trades_df['running_max']
        max_drawdown = float(trades_df['drawdown'].min())

        avg_holding_days = float(trades_df['holding_days'].mean())

        self.performance = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': float(win_rate),
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

    # === グラフ描画メソッド ===

    def plot_overview(self):
        """バックテスト期間全体のグラフを作成してFigureを返す"""
        if self.trades_df is None or len(self.trades_df) == 0:
            return None

        fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [2, 1, 1]})

        # === グラフ1: 価格チャート + エントリー・エグジット ===
        ax1 = axes[0]
        chart_data = self.daily_data[self.daily_data.index >= self.start_date].copy()

        ax1.plot(chart_data.index, chart_data['Close'], label='Close', linewidth=1.5, color='black', alpha=0.7)
        ax1.plot(chart_data.index, chart_data['MA_short'], label=f'MA{self.rules.ma_short}', linewidth=1, color='blue', alpha=0.6)
        ax1.plot(chart_data.index, chart_data['MA_mid'], label=f'MA{self.rules.ma_mid}', linewidth=1, color='orange', alpha=0.6)
        ax1.plot(chart_data.index, chart_data['MA_long'], label=f'MA{self.rules.ma_long}', linewidth=1, color='red', alpha=0.6)

        for _, trade in self.trades_df.iterrows():
            # エントリー
            ax1.scatter(trade['entry_date'], trade['entry_price'], marker='^', color='green', s=100, zorder=5, edgecolors='darkgreen', linewidth=1.5)
            # エグジット
            if 'Stop Loss' in trade['exit_reason']:
                ax1.scatter(trade['exit_date'], trade['exit_price'], marker='v', color='red', s=100, zorder=5, edgecolors='darkred', linewidth=1.5)
            else:
                ax1.scatter(trade['exit_date'], trade['exit_price'], marker='o', color='blue', s=100, zorder=5, edgecolors='darkblue', linewidth=1.5)
            
            # 線で結ぶ
            color = 'green' if trade['profit'] > 0 else 'red'
            ax1.plot([trade['entry_date'], trade['exit_date']], [trade['entry_price'], trade['exit_price']],
                     color=color, linewidth=2, linestyle='--', alpha=0.4)

        ax1.set_title(f'Price Chart - {self.ticker}', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Price')
        ax1.legend(loc='upper left', fontsize=9)
        ax1.grid(True, alpha=0.3)

        # === グラフ2: 累積損益 ===
        ax2 = axes[1]
        ax2.plot(self.trades_df['exit_date'], self.trades_df['cumulative_profit'], label='Cumulative P&L', color='blue', linewidth=2)
        ax2.axhline(0, color='gray', linestyle='--', linewidth=1)
        ax2.fill_between(self.trades_df['exit_date'], self.trades_df['cumulative_profit'], 0, 
                         where=(self.trades_df['cumulative_profit']>=0), color='green', alpha=0.2)
        ax2.fill_between(self.trades_df['exit_date'], self.trades_df['cumulative_profit'], 0, 
                         where=(self.trades_df['cumulative_profit']<0), color='red', alpha=0.2)
        ax2.set_title('Cumulative Profit/Loss', fontsize=12, fontweight='bold')
        ax2.set_ylabel('P&L')
        ax2.grid(True, alpha=0.3)

        # === グラフ3: トレード別損益 ===
        ax3 = axes[2]
        colors = ['green' if x > 0 else 'red' for x in self.trades_df['profit']]
        ax3.bar(range(len(self.trades_df)), self.trades_df['profit'], color=colors, alpha=0.7)
        ax3.axhline(0, color='black', linewidth=0.5)
        ax3.set_title('Trade-by-Trade P&L', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Trade Number')
        ax3.set_ylabel('P&L')
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig

    def plot_all_trades(self):
        """全トレードの詳細チャートを作成してFigureのリストを返す"""
        if self.trades_df is None or len(self.trades_df) == 0:
            return []

        figs = []
        for idx, trade in self.trades_df.iterrows():
            start_date = trade['entry_date'] - pd.Timedelta(days=30)
            end_date = trade['exit_date'] + pd.Timedelta(days=10)

            trade_data = self.daily_data[(self.daily_data.index >= start_date) & (self.daily_data.index <= end_date)].copy()
            if trade_data.empty:
                continue

            fig, ax = plt.subplots(figsize=(12, 7))

            # ローソク足描画
            self._plot_candlestick(ax, trade_data)

            # 移動平均線
            x_range = range(len(trade_data))
            ax.plot(x_range, trade_data['MA_short'].values, label=f'MA{self.rules.ma_short}', color='blue', linewidth=1.5, alpha=0.7)
            ax.plot(x_range, trade_data['MA_mid'].values, label=f'MA{self.rules.ma_mid}', color='orange', linewidth=1.5, alpha=0.7)
            ax.plot(x_range, trade_data['MA_long'].values, label=f'MA{self.rules.ma_long}', color='red', linewidth=1, alpha=0.6)

            # エントリー・エグジットポイント
            try:
                entry_idx = trade_data.index.get_loc(trade['entry_date'])
                exit_idx = trade_data.index.get_loc(trade['exit_date'])
                
                ax.scatter(entry_idx, trade['entry_price'], marker='^', color='green', s=200, zorder=10, 
                          edgecolors='darkgreen', linewidth=2, label='Entry')

                exit_color = 'red' if trade['profit'] < 0 else 'blue'
                exit_marker = 'v' if 'Stop Loss' in trade['exit_reason'] else 'o'
                ax.scatter(exit_idx, trade['exit_price'], marker=exit_marker, color=exit_color, s=200, zorder=10,
                          edgecolors='black', linewidth=2, label='Exit')
                
                # 損切りラインを表示
                if 'Stop Loss' in trade['exit_reason']:
                    ax.hlines(trade['exit_price'], entry_idx, exit_idx, colors='red', linestyles=':', linewidth=2, alpha=0.6)
                
            except KeyError:
                pass

            # タイトル
            profit_text = f"¥{trade['profit']:,.0f}" if '.T' in self.ticker else f"${trade['profit']:,.0f}"
            title = f"Trade #{idx+1} | {profit_text} ({trade['profit_pct']:.2f}%) | {trade['holding_days']}days | {trade['exit_reason']}"
            ax.set_title(title, fontsize=12, fontweight='bold', pad=15)
            ax.set_ylabel('Price')
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper left', fontsize=9)
            
            # X軸の日付調整
            tick_count = min(8, len(trade_data))
            tick_idxs = np.linspace(0, len(trade_data)-1, tick_count, dtype=int)
            ax.set_xticks(tick_idxs)
            ax.set_xticklabels([trade_data.index[i].strftime('%Y-%m-%d') for i in tick_idxs], rotation=45)

            plt.tight_layout()
            figs.append(fig)
            
        return figs

    def _plot_candlestick(self, ax, data):
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