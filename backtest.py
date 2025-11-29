#backtest.py
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
        self.ma_short = 5   # 短期MA（日足）
        self.ma_mid = 20    # 中期MA（日足）
        self.ma_long = 50   # 長期MA（日足）

        self.ma_weekly_short = 20  # 短期MA（週足）
        self.ma_weekly_long = 50   # 長期MA（週足）

        # === エントリー条件 ===
        # 押し目検出
        self.pullback_method = 'ma_below'  # 'ma_below', 'price_touch', 'both'
        self.pullback_tolerance = 0.995  # 価格がMAの何%まで近づいたら押し目とみなすか

        # 移動平均線の傾き
        self.ma_slope_threshold = 0.5  # 中期MAの傾き閾値（%）
        self.ma_slope_period = 5  # 傾きを計算する日数
        self.use_slope_filter = True  # 傾きフィルターを使用するか

        # エントリートリガー
        self.entry_trigger = 'price_cross_ma5'  # 'price_cross_ma5', 'ma_cross', 'close_above'

        # 出来高条件
        self.volume_threshold = 500000  # 最低出来高
        self.volume_consecutive_days = 5  # 連続日数
        self.use_volume_filter = True  # 出来高フィルターを使用するか

        # 週足トレンド条件
        self.use_weekly_filter = True  # 週足フィルターを使用するか
        self.weekly_slope_threshold = 2.0  # 週足MAの傾き閾値（%）
        self.weekly_slope_period = 4  # 週足傾きを計算する週数

        # === エグジット条件 ===
        # 損切り
        self.stop_loss_method = 'recent_low'  # 'recent_low', 'percentage', 'atr'
        self.stop_loss_percentage = 0.98  # 直近安値の何%で損切りか
        self.stop_loss_lookback = 5  # 直近安値を何日分見るか

        # 利確・決済
        self.exit_method = 'ma5_cross'  # 'ma5_cross', 'percentage', 'trailing'
        self.take_profit_percentage = 1.05  # 利確目標（5%）

        # エグジットタイミング
        self.exit_timing = 'next_open'  # 'immediate', 'next_open', 'next_close'

        # === 表示設定 ===
        self.show_detailed_charts = False  # 個別トレードのローソク足を表示するか
        self.num_detailed_charts = 5  # 表示する個別トレードの数

    def summary(self):
        """ルール設定のサマリーを表示"""
        print("\n" + "="*60)
        print("トレードルール設定")
        print("="*60)
        print(f"【移動平均線】")
        print(f"  日足: MA{self.ma_short}, MA{self.ma_mid}, MA{self.ma_long}")
        print(f"  週足: MA{self.ma_weekly_short}, MA{self.ma_weekly_long}")
        print(f"\n【エントリー条件】")
        print(f"  押し目検出: {self.pullback_method}")
        if self.pullback_method in ['price_touch', 'both']:
            print(f"  押し目許容度: {self.pullback_tolerance*100:.1f}%")
        if self.use_slope_filter:
            print(f"  傾きフィルター: MA{self.ma_mid}が{self.ma_slope_period}日で{self.ma_slope_threshold}%以上上昇")
        print(f"  エントリートリガー: {self.entry_trigger}")
        if self.use_volume_filter:
            print(f"  出来高条件: {self.volume_consecutive_days}日連続で{self.volume_threshold:,}株以上")
        if self.use_weekly_filter:
            print(f"  週足条件: MA{self.ma_weekly_short} > MA{self.ma_weekly_long}")
        print(f"\n【エグジット条件】")
        print(f"  損切り: {self.stop_loss_method} ({self.stop_loss_percentage*100:.0f}%, {self.stop_loss_lookback}日)")
        print(f"  決済方法: {self.exit_method}")
        if self.exit_method == 'percentage':
            print(f"  利確目標: {(self.take_profit_percentage-1)*100:.0f}%")
        print(f"  決済タイミング: {self.exit_timing}")
        print("="*60 + "\n")


class SwingTradeBacktest:
    """パラメータ調整可能なバックテストクラス"""

    def __init__(self, ticker, start_date, end_date, rules=None):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.rules = rules if rules else TradingRules()
        self.daily_data = None
        self.weekly_data = None
        self.trades = []

    def fetch_data(self):
        """データ取得"""
        print(f"データ取得中: {self.ticker}")
        extended_start = (pd.to_datetime(self.start_date) - timedelta(days=400)).strftime('%Y-%m-%d')
        stock = yf.Ticker(self.ticker)
        self.daily_data = stock.history(start=extended_start, end=self.end_date)

        if self.daily_data.empty:
            raise ValueError(f"データが取得できませんでした: {self.ticker}")
        print(f"取得完了: {len(self.daily_data)} 日分のデータ")

    def calculate_indicators(self):
        """指標計算"""
        df = self.daily_data.copy()

        # 移動平均線（役割ベースの名前）
        df['MA_short'] = df['Close'].rolling(window=self.rules.ma_short).mean()
        df['MA_mid'] = df['Close'].rolling(window=self.rules.ma_mid).mean()
        df['MA_long'] = df['Close'].rolling(window=self.rules.ma_long).mean()

        # 傾き計算
        df['MA_short_slope'] = (df['MA_short'] - df['MA_short'].shift(2)) / df['MA_short'].shift(2) * 100
        df['MA_mid_slope'] = (df['MA_mid'] - df['MA_mid'].shift(self.rules.ma_slope_period)) / \
                             df['MA_mid'].shift(self.rules.ma_slope_period) * 100
        df['MA_long_slope'] = (df['MA_long'] - df['MA_long'].shift(10)) / df['MA_long'].shift(10) * 100

        # 出来高条件
        df['Volume_Condition'] = df['Volume'] >= self.rules.volume_threshold
        df['Volume_Streak'] = df['Volume_Condition'].rolling(window=self.rules.volume_consecutive_days).sum()
        df['Volume_OK'] = df['Volume_Streak'] >= self.rules.volume_consecutive_days

        # 直近安値
        df['Recent_Low'] = df['Low'].rolling(window=self.rules.stop_loss_lookback).min()

        self.daily_data = df

        # 週足指標
        weekly = df.resample('W-FRI').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min',
            'Close': 'last', 'Volume': 'sum'
        }).dropna()

        weekly['MA_weekly_short'] = weekly['Close'].rolling(window=self.rules.ma_weekly_short).mean()
        weekly['MA_weekly_long'] = weekly['Close'].rolling(window=self.rules.ma_weekly_long).mean()
        weekly['MA_weekly_short_slope'] = (weekly['MA_weekly_short'] - weekly['MA_weekly_short'].shift(self.rules.weekly_slope_period)) / \
                                           weekly['MA_weekly_short'].shift(self.rules.weekly_slope_period) * 100
        weekly['Trend_Up'] = (weekly['MA_weekly_short'] > weekly['MA_weekly_long']) & \
                            (weekly['Close'] >= weekly['MA_weekly_short'])

        self.weekly_data = weekly

    def check_weekly_trend(self, date):
        """週足トレンド確認"""
        week_data = self.weekly_data[self.weekly_data.index <= date]
        if len(week_data) == 0:
            return False
        return week_data.iloc[-1]['Trend_Up']

    def check_pullback(self, current):
      """押し目判定（ルールに基づく）"""
      if self.rules.pullback_method == 'ma_below':
          return current['MA_short'] < current['MA_mid']

      elif self.rules.pullback_method == 'price_touch':
          return current['Low'] <= current['MA_short'] * self.rules.pullback_tolerance

      elif self.rules.pullback_method == 'both':
          return (current['Low'] <= current['MA_short'] * self.rules.pullback_tolerance) and \
                (current['MA_short'] < current['MA_mid'])

      return False

    def check_entry_trigger(self, current, prev):
        """エントリートリガー判定"""
        if self.rules.entry_trigger == 'price_cross_ma5':
            return current['High'] >= current['MA_short']

        elif self.rules.entry_trigger == 'ma_cross':
            return prev['MA_short'] < prev['MA_mid'] and current['MA_short'] >= current['MA_mid']

        elif self.rules.entry_trigger == 'close_above':
            return current['Close'] > current['MA_short']

        return False

    def calculate_stop_loss(self, entry_price, current):
        """損切り価格計算"""
        if self.rules.stop_loss_method == 'recent_low':
            return current['Recent_Low'] * self.rules.stop_loss_percentage

        elif self.rules.stop_loss_method == 'percentage':
            return entry_price * self.rules.stop_loss_percentage

        return entry_price * 0.98  # デフォルト


    def check_exit_condition(self, current, position):
        """エグジット条件判定"""

        # === 損切り条件 ===
        if self.rules.stop_loss_method == 'recent_low':
            stop_loss_price = current['Recent_Low'] * self.rules.stop_loss_percentage
            if current['Close'] <= stop_loss_price:
                if self.rules.hold_if_ma5_uptrend:
                    ma5_up = pd.notna(current['MA_short_slope']) and \
                            current['MA_short_slope'] > self.rules.ma5_uptrend_threshold
                    if ma5_up:
                        return False, None
                return True, 'Stop Loss (Close)'

        elif self.rules.stop_loss_method == 'percentage':
            stop_loss_price = position['entry_price'] * self.rules.stop_loss_percentage
            if current['Close'] <= stop_loss_price:
                return True, 'Stop Loss (Percentage)'

        # === 利確・決済条件 ===
        if self.rules.exit_method == 'ma5_cross':
            if pd.notna(current['MA_short']) and current['Close'] < current['MA_short']:
                return True, 'MA_short Cross Exit'

        elif self.rules.exit_method == 'ma5_advanced':
            if self.rules.ma5_exit_price_type == 'close':
                price = current['Close']
            elif self.rules.ma5_exit_price_type == 'open':
                price = current['Open']
            elif self.rules.ma5_exit_price_type == 'low':
                price = current['Low']
            elif self.rules.ma5_exit_price_type == 'high':
                price = current['High']
            else:
                price = current['Close']

            ma_threshold = current['MA_short'] * (1 - self.rules.ma5_exit_margin / 100)

            if pd.notna(current['MA_short']) and price < ma_threshold:
                if self.rules.ma5_exit_consecutive_days <= 1:
                    return True, f'MA_short Exit ({self.rules.ma5_exit_price_type})'

        elif self.rules.exit_method == 'percentage':
            if current['High'] >= position['entry_price'] * self.rules.take_profit_percentage:
                return True, 'Take Profit'

        return False, None

    def generate_signals(self):
        """シグナル生成"""
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
                    entry_date = current_date
                    stop_loss = self.calculate_stop_loss(entry_price, prev)

                    position = {
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'shares': 1
                    }
                    entry_signal_date = None
                    continue

                # エントリーシグナル判定
                if self.rules.use_weekly_filter and not self.check_weekly_trend(current_date):
                    continue

                if pd.notna(current['MA_short']) and pd.notna(current['MA_mid']) and pd.notna(current['Close']):
                    pullback = self.check_pullback(current)

                    if self.rules.use_slope_filter:
                        ma_trending = pd.notna(current['MA_mid_slope']) and \
                                    current['MA_mid_slope'] > self.rules.ma_slope_threshold
                    else:
                        ma_trending = True

                    # 出来高フィルター（オプション）
                    if self.rules.use_volume_filter:
                        volume_ok = current['Volume_OK']
                    else:
                        volume_ok = True  # フィルター無効時は常にTrue

                    entry_trigger = self.check_entry_trigger(current, prev)

                    if pullback and ma_trending and volume_ok and entry_trigger:
                        entry_signal_date = current_date

            # エグジット処理
            else:
                should_exit, exit_reason = self.check_exit_condition(current, position)

                if should_exit:
                    if self.rules.exit_timing == 'next_open' and i+1 < len(df):
                        exit_date = df.index[i+1]
                        exit_price = df.iloc[i+1]['Open']
                    else:
                        exit_date = current_date
                        exit_price = current['Close']

                    profit = (exit_price - position['entry_price']) * position['shares']
                    profit_pct = (exit_price / position['entry_price'] - 1) * 100

                    trade = {
                        'entry_date': position['entry_date'],
                        'exit_date': exit_date,
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'shares': position['shares'],
                        'profit': profit,
                        'profit_pct': profit_pct,
                        'exit_reason': exit_reason,
                        'holding_days': (exit_date - position['entry_date']).days
                    }

                    self.trades.append(trade)
                    position = None

    def calculate_performance(self):
        """パフォーマンス計算"""
        if len(self.trades) == 0:
            print("トレードが発生しませんでした")
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

    def print_performance(self):
        """結果表示"""
        if not hasattr(self, 'performance'):
            return

        p = self.performance
        print("\n" + "="*60)
        print(f"バックテスト結果: {self.ticker}")
        print(f"期間: {self.start_date} ~ {self.end_date}")
        print("="*60)
        print(f"総トレード数: {p['total_trades']} 回")
        print(f"勝率: {p['win_rate']:.2f}% ({p['winning_trades']}勝 {p['losing_trades']}敗)")
        print(f"累積損益: ¥{p['total_profit']:,.0f}")
        print(f"平均利益: ¥{p['avg_profit']:,.0f} ({p['avg_profit_pct']:.2f}%)")
        print(f"平均損失: ¥{p['avg_loss']:,.0f} ({p['avg_loss_pct']:.2f}%)")
        print(f"PF: {p['profit_factor']:.2f} | DD: ¥{p['max_drawdown']:,.0f}")
        print("="*60 + "\n")

    def plot_results(self):
        """バックテスト期間全体のグラフを表示"""
        if not hasattr(self, 'trades_df') or len(self.trades_df) == 0:
            print("トレードデータがありません")
            return

        fig, axes = plt.subplots(3, 1, figsize=(16, 14))

        # === グラフ1: 価格チャート + エントリー・エグジットポイント ===
        ax1 = axes[0]
        chart_data = self.daily_data[self.daily_data.index >= self.start_date].copy()

        # 株価チャート
        ax1.plot(chart_data.index, chart_data['Close'], label='Close Price',
                linewidth=1.5, color='black', alpha=0.7)

        # 移動平均線
        ax1.plot(chart_data.index, chart_data['MA_short'], label=f'MA{self.rules.ma_short}',
                linewidth=1, color='blue', alpha=0.6)
        ax1.plot(chart_data.index, chart_data['MA_mid'], label=f'MA{self.rules.ma_mid}',
                linewidth=1, color='orange', alpha=0.6)
        ax1.plot(chart_data.index, chart_data['MA_long'], label=f'MA{self.rules.ma_long}',
                linewidth=1, color='red', alpha=0.6)

        # エントリー・エグジットポイント
        for _, trade in self.trades_df.iterrows():
            ax1.scatter(trade['entry_date'], trade['entry_price'],
                       marker='^', color='green', s=100, zorder=5,
                       edgecolors='darkgreen', linewidth=1.5)

            if 'Stop Loss' in trade['exit_reason']:
                ax1.scatter(trade['exit_date'], trade['exit_price'],
                           marker='v', color='red', s=100, zorder=5,
                           edgecolors='darkred', linewidth=1.5)
            else:
                ax1.scatter(trade['exit_date'], trade['exit_price'],
                           marker='o', color='blue', s=100, zorder=5,
                           edgecolors='darkblue', linewidth=1.5)

            line_color = 'green' if trade['profit'] > 0 else 'red'
            ax1.plot([trade['entry_date'], trade['exit_date']],
                    [trade['entry_price'], trade['exit_price']],
                    color=line_color, linewidth=2, alpha=0.3, linestyle='--')

        ax1.set_title(f'Price Chart with Entry/Exit Points - {self.ticker}',
                     fontsize=14, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Price (JPY)')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)

        custom_lines = [
            Line2D([0], [0], marker='^', color='w', markerfacecolor='green',
                   markersize=10, label='Entry', markeredgecolor='darkgreen', markeredgewidth=1.5),
            Line2D([0], [0], marker='v', color='w', markerfacecolor='red',
                   markersize=10, label='Stop Loss', markeredgecolor='darkred', markeredgewidth=1.5),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='blue',
                   markersize=10, label='Exit (MA5 Cross)', markeredgecolor='darkblue', markeredgewidth=1.5)
        ]
        ax1.legend(handles=ax1.get_legend_handles_labels()[0] + custom_lines,
                  loc='upper left', fontsize=9)

        # === グラフ2: 累積損益推移 ===
        ax2 = axes[1]
        ax2.plot(self.trades_df['exit_date'],
                 self.trades_df['cumulative_profit'],
                 label='Cumulative P&L', linewidth=2, color='blue')
        ax2.axhline(y=0, color='gray', linestyle='--', label='Break Even')
        ax2.fill_between(self.trades_df['exit_date'],
                         self.trades_df['cumulative_profit'], 0,
                         where=(self.trades_df['cumulative_profit'] >= 0),
                         alpha=0.3, color='green', label='Profit Zone')
        ax2.fill_between(self.trades_df['exit_date'],
                         self.trades_df['cumulative_profit'], 0,
                         where=(self.trades_df['cumulative_profit'] < 0),
                         alpha=0.3, color='red', label='Loss Zone')
        ax2.set_title('Cumulative Profit/Loss', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('Cumulative P&L (JPY)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # === グラフ3: トレードごとの損益 ===
        ax3 = axes[2]
        colors = ['green' if x > 0 else 'red' for x in self.trades_df['profit']]
        ax3.bar(range(len(self.trades_df)), self.trades_df['profit'], color=colors, alpha=0.6)
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax3.set_title('Trade-by-Trade Profit/Loss', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Trade Number')
        ax3.set_ylabel('Profit/Loss (JPY)')
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    def plot_candlestick(self, ax, data):
        """ローソク足を描画"""
        width = 0.6

        for idx, (date, row) in enumerate(data.iterrows()):
            open_price = row['Open']
            close_price = row['Close']
            high_price = row['High']
            low_price = row['Low']

            if close_price >= open_price:
                color = 'red'
                body_color = 'red'
                alpha = 0.8
            else:
                color = 'blue'
                body_color = 'blue'
                alpha = 0.8

            body_height = abs(close_price - open_price)
            body_bottom = min(open_price, close_price)

            rect = Rectangle((idx - width/2, body_bottom), width, body_height,
                           facecolor=body_color, edgecolor='black',
                           linewidth=0.5, alpha=alpha)
            ax.add_patch(rect)

            ax.plot([idx, idx], [max(open_price, close_price), high_price],
                   color=color, linewidth=1)
            ax.plot([idx, idx], [low_price, min(open_price, close_price)],
                   color=color, linewidth=1)

    def plot_detailed_trades(self, num_trades=5):
        """個別トレードをローソク足で詳細表示"""
        if not hasattr(self, 'trades_df') or len(self.trades_df) == 0:
            print("トレードデータがありません")
            return

        trades_to_show = min(num_trades, len(self.trades_df))

        for idx in range(trades_to_show):
            trade = self.trades_df.iloc[idx]

            start_date = trade['entry_date'] - pd.Timedelta(days=30)
            end_date = trade['exit_date'] + pd.Timedelta(days=10)

            trade_data = self.daily_data[
                (self.daily_data.index >= start_date) &
                (self.daily_data.index <= end_date)
            ].copy()

            if len(trade_data) == 0:
                continue

            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10),
                                           gridspec_kw={'height_ratios': [3, 1]})

            # ローソク足
            self.plot_candlestick(ax1, trade_data)

            x_positions = range(len(trade_data))
            ax1.set_xlim(-0.5, len(trade_data) - 0.5)

            date_labels = []
            date_positions = []
            for i, date in enumerate(trade_data.index):
                if i % 5 == 0 or i == len(trade_data) - 1:
                    date_labels.append(date.strftime('%m/%d'))
                    date_positions.append(i)
            ax1.set_xticks(date_positions)
            ax1.set_xticklabels(date_labels, rotation=45)

            # 移動平均線
            ax1.plot(x_positions, trade_data['MA_short'].values,
                    label=f'MA{self.rules.ma_short}', color='blue', linewidth=1.5, alpha=0.8)
            ax1.plot(x_positions, trade_data['MA_mid'].values,
                    label=f'MA{self.rules.ma_mid}', color='orange', linewidth=1.5, alpha=0.8)
            ax1.plot(x_positions, trade_data['MA_long'].values,
                    label=f'MA{self.rules.ma_long}', color='red', linewidth=1, alpha=0.6)

            # エントリー・エグジットポイント
            entry_idx = trade_data.index.get_loc(trade['entry_date'])
            exit_idx = trade_data.index.get_loc(trade['exit_date'])

            ax1.scatter(entry_idx, trade['entry_price'],
                       marker='^', color='green', s=300, zorder=5,
                       edgecolors='darkgreen', linewidth=2, label='Entry')

            if 'Stop Loss' in trade['exit_reason']:
                exit_color = 'red'
                exit_marker = 'v'
                exit_label = 'Stop Loss Exit'
            else:
                exit_color = 'blue'
                exit_marker = 'o'
                exit_label = 'MA5 Cross Exit'

            ax1.scatter(exit_idx, trade['exit_price'],
                       marker=exit_marker, color=exit_color, s=300, zorder=5,
                       edgecolors='dark'+exit_color, linewidth=2, label=exit_label)

            stop_loss_price = trade['entry_price'] * 0.98
            ax1.hlines(stop_loss_price, entry_idx, exit_idx,
                      colors='red', linestyles=':', linewidth=2,
                      alpha=0.6, label='Stop Loss Level')

            profit_text = f"P&L: ¥{trade['profit']:.0f} ({trade['profit_pct']:.2f}%)"
            days_text = f"Hold: {trade['holding_days']}days"
            entry_text = f"Entry: {trade['entry_date'].strftime('%Y-%m-%d')}"
            exit_text = f"Exit: {trade['exit_date'].strftime('%Y-%m-%d')}"
            reason_text = f"Reason: {trade['exit_reason']}"

            title = f"Trade #{idx+1} | {profit_text} | {days_text}\n{entry_text} → {exit_text} | {reason_text}"
            ax1.set_title(title, fontsize=12, fontweight='bold', pad=15)
            ax1.set_ylabel('Price (JPY)', fontsize=11)
            ax1.legend(loc='upper left', fontsize=9, framealpha=0.9)
            ax1.grid(True, alpha=0.3, linestyle='--')

            # 出来高
            colors_volume = ['red' if trade_data.iloc[i]['Close'] >= trade_data.iloc[i]['Open']
                            else 'blue' for i in range(len(trade_data))]
            ax2.bar(x_positions, trade_data['Volume'].values,
                   color=colors_volume, alpha=0.6, width=0.8)
            ax2.set_xlim(-0.5, len(trade_data) - 0.5)
            ax2.set_xticks(date_positions)
            ax2.set_xticklabels(date_labels, rotation=45)
            ax2.set_ylabel('Volume', fontsize=11)
            ax2.grid(True, alpha=0.3, linestyle='--')

            plt.tight_layout()
            plt.show()

            print(f"\n{'='*70}")
            print(f"Trade #{idx+1} 詳細情報")
            print(f"{'='*70}")
            print(f"エントリー日: {trade['entry_date'].strftime('%Y-%m-%d')}")
            print(f"エントリー価格: ¥{trade['entry_price']:.2f}")
            print(f"エグジット日: {trade['exit_date'].strftime('%Y-%m-%d')}")
            print(f"エグジット価格: ¥{trade['exit_price']:.2f}")
            print(f"保有期間: {trade['holding_days']}日")
            print(f"損益: ¥{trade['profit']:.2f} ({trade['profit_pct']:.2f}%)")
            print(f"決済理由: {trade['exit_reason']}")
            print(f"{'='*70}\n")

    def run(self, show_charts=True, show_detailed=False, num_detailed=5):
        """バックテスト実行"""
        self.fetch_data()
        self.calculate_indicators()
        self.generate_signals()
        self.calculate_performance()
        self.print_performance()

        # グラフ表示
        if show_charts and len(self.trades) > 0:
            self.plot_results()

        # 個別トレード詳細
        if show_detailed and len(self.trades) > 0:
            print("\n個別トレード詳細グラフを生成中...")
            self.plot_detailed_trades(num_trades=num_detailed)


# === 便利な比較関数 ===
# === 便利な比較関数 ===
def compare_rules(ticker, start_date, end_date, rules_list, rule_names, show_charts=False):
    """複数のルールを比較

    Parameters:
    -----------
    ticker : str
        銘柄コード
    start_date : str
        開始日
    end_date : str
        終了日
    rules_list : list of TradingRules
        比較するルールのリスト
    rule_names : list of str
        各ルールの名前
    show_charts : bool, default=False
        各ルールのグラフを表示するか

    Returns:
    --------
    results : list of dict
        各ルールの結果を含む辞書のリスト
        各辞書には 'name', 'performance', 'backtest' が含まれる
    """
    print(f"\n{'='*80}")
    print(f"ルール比較: {ticker}")
    print(f"{'='*80}")

    results = []

    for rule, name in zip(rules_list, rule_names):
        print(f"\n--- {name} ---")
        bt = SwingTradeBacktest(ticker, start_date, end_date, rule)
        bt.run(show_charts=show_charts, show_detailed=False)

        if hasattr(bt, 'performance'):
            results.append({
                'name': name,
                'performance': bt.performance,
                'backtest': bt  # バックテストオブジェクトを保存
            })

    # 比較表
    print(f"\n{'='*80}")
    print("【ルール比較サマリー】")
    print(f"{'='*80}")
    print(f"{'ルール':<25} {'勝率':<10} {'累積損益':<15} {'PF':<8} {'トレード数':<10}")
    print("-"*80)

    for r in results:
        p = r['performance']
        print(f"{r['name']:<25} {p['win_rate']:>6.1f}%  ¥{p['total_profit']:>10,.0f}  {p['profit_factor']:>6.2f}  {p['total_trades']:>8}回")

    print("="*80)

    return results

