import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from datetime import datetime, timedelta
import warnings
from screening import MA_SHORT, MA_MID, MA_LONG

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
        self.trades_df = None # 初期化を追加
# ... (以降のメソッドが続く)

    # ... (fetch_data, calculate_indicators, generate_signals, _record_trade は変更なし) ...
    # 省略しています。元のコードのまま記述してください。
    
    def fetch_data(self):
        # (元のコードと同じ)
        try:
            extended_start = (pd.to_datetime(self.start_date) - timedelta(days=400)).strftime('%Y-%m-%d')
            stock = yf.Ticker(self.ticker)
            self.daily_data = stock.history(start=extended_start, end=self.end_date)
            if self.daily_data.empty:
                raise ValueError(f"データが取得できませんでした: {self.ticker}")
            self.daily_data = self.daily_data[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        except Exception as e:
            raise Exception(f"データ取得エラー ({self.ticker}): {str(e)}")

    def calculate_indicators(self):
        # (元のコードと同じ)
        df = self.daily_data.copy()
        df['MA_short'] = df['Close'].rolling(window=self.rules.ma_short).mean()
        df['MA_mid'] = df['Close'].rolling(window=self.rules.ma_mid).mean()
        df['MA_long'] = df['Close'].rolling(window=self.rules.ma_long).mean()
        df['MA_mid_slope'] = (df['MA_mid'] - df['MA_mid'].shift(self.rules.slope_period)) / \
                             df['MA_mid'].shift(self.rules.slope_period) * 100
        df['Recent_Low'] = df['Low'].rolling(window=self.rules.stop_loss_lookback).min()
        self.daily_data = df

    def generate_signals(self):
        # (元のコードと同じ)
        df = self.daily_data.copy()
        df = df[df.index >= self.start_date]
        position = None
        entry_signal_date = None

        for i in range(1, len(df)):
            current_date = df.index[i]
            prev_date = df.index[i-1]
            current = df.iloc[i]
            prev = df.iloc[i-1]

            if position is None:
                if entry_signal_date == prev_date:
                    entry_price = current['Open']
                    stop_loss = prev['Recent_Low'] * self.rules.stop_loss_percentage
                    position = {'entry_date': current_date, 'entry_price': entry_price, 'stop_loss': stop_loss}
                    entry_signal_date = None
                    continue

                if pd.notna(current['MA_short']) and pd.notna(current['MA_mid']) and pd.notna(current['MA_long']):
                    pullback = current['MA_short'] < current['MA_mid']
                    ma_trending = pd.notna(current['MA_mid_slope']) and current['MA_mid_slope'] > self.rules.slope_threshold
                    long_trend = current['MA_mid'] > current['MA_long']
                    entry_trigger = current['High'] >= current['MA_short']

                    if pullback and ma_trending and long_trend and entry_trigger:
                        entry_signal_date = current_date
            else:
                if current['Close'] <= position['stop_loss']:
                    self._record_trade(position, current_date, current['Close'], 'Stop Loss')
                    position = None
                elif pd.notna(current['MA_short']) and current['Close'] < current['MA_short']:
                    if i+1 < len(df):
                        exit_price = df.iloc[i+1]['Open']
                        exit_date = df.index[i+1]
                    else:
                        exit_price = current['Close']
                        exit_date = current_date
                    self._record_trade(position, exit_date, exit_price, 'MA Cross')
                    position = None

    def _record_trade(self, position, exit_date, exit_price, exit_reason):
        # (元のコードと同じ)
        profit = exit_price - position['entry_price']
        profit_pct = (exit_price / position['entry_price'] - 1) * 100
        holding_days = (exit_date - position['entry_date']).days
        self.trades.append({
            'entry_date': position['entry_date'], 'exit_date': exit_date,
            'entry_price': position['entry_price'], 'exit_price': exit_price,
            'profit': profit, 'profit_pct': profit_pct,
            'exit_reason': exit_reason, 'holding_days': holding_days
        })

    def calculate_performance(self):
        # (元のコードと同じ)
        if len(self.trades) == 0:
            return None
        trades_df = pd.DataFrame(self.trades)
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['profit'] > 0])
        losing_trades = len(trades_df[trades_df['profit'] <= 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 修正: numpy型の警告回避のため float変換を入れることがあります
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
            'total_trades': total_trades, 'winning_trades': winning_trades, 'losing_trades': losing_trades,
            'win_rate': win_rate, 'total_profit': total_profit,
            'avg_profit': avg_profit, 'avg_loss': avg_loss,
            'avg_profit_pct': avg_profit_pct, 'avg_loss_pct': avg_loss_pct,
            'max_drawdown': max_drawdown, 'avg_holding_days': avg_holding_days,
            'profit_factor': abs(avg_profit / avg_loss) if avg_loss != 0 else 0
        }
        self.trades_df = trades_df
        return self.performance

    def run(self, show_charts=False, show_detailed=False):
        """バックテスト実行（計算のみ）"""
        self.fetch_data()
        self.calculate_indicators()
        self.generate_signals()
        return self.calculate_performance()

    # === 追加・修正した描画用メソッド ===

    def plot_overview(self):
        """バックテスト期間全体のグラフを作成してFigureを返す"""
        if self.trades_df is None or len(self.trades_df) == 0:
            return None

        fig, axes = plt.subplots(3, 1, figsize=(12, 12), gridspec_kw={'height_ratios': [2, 1, 1]})

        # === グラフ1: 価格チャート + エントリー・エグジット ===
        ax1 = axes[0]
        chart_data = self.daily_data[self.daily_data.index >= self.start_date].copy()

        ax1.plot(chart_data.index, chart_data['Close'], label='Close', linewidth=1, color='black', alpha=0.6)
        ax1.plot(chart_data.index, chart_data['MA_short'], label=f'MA{self.rules.ma_short}', linewidth=1, color='blue', alpha=0.5)
        ax1.plot(chart_data.index, chart_data['MA_mid'], label=f'MA{self.rules.ma_mid}', linewidth=1, color='orange', alpha=0.5)
        ax1.plot(chart_data.index, chart_data['MA_long'], label=f'MA{self.rules.ma_long}', linewidth=1, color='red', alpha=0.5)

        for _, trade in self.trades_df.iterrows():
            # エントリー
            ax1.scatter(trade['entry_date'], trade['entry_price'], marker='^', color='green', s=80, zorder=5)
            # エグジット (黒枠線を追加して視認性向上)
            if 'Stop Loss' in trade['exit_reason']:
                ax1.scatter(trade['exit_date'], trade['exit_price'], marker='v', color='red', s=80, zorder=5, edgecolors='black', linewidth=1.5)
            else:
                ax1.scatter(trade['exit_date'], trade['exit_price'], marker='o', color='blue', s=80, zorder=5, edgecolors='black', linewidth=1.5)
            # 線で結ぶ
            color = 'green' if trade['profit'] > 0 else 'red'
            ax1.plot([trade['entry_date'], trade['exit_date']], [trade['entry_price'], trade['exit_price']],
                     color=color, linewidth=1.5, linestyle='--', alpha=0.5)

        ax1.set_title(f'Overview: {self.ticker}', fontsize=12, fontweight='bold')
        ax1.legend(loc='upper left', fontsize='small')
        ax1.grid(True, alpha=0.3)

        # === グラフ2: 累積損益 ===
        ax2 = axes[1]
        ax2.plot(self.trades_df['exit_date'], self.trades_df['cumulative_profit'], label='Cumulative P&L', color='blue')
        ax2.axhline(0, color='gray', linestyle='--', linewidth=1)
        ax2.fill_between(self.trades_df['exit_date'], self.trades_df['cumulative_profit'], 0, where=(self.trades_df['cumulative_profit']>=0), color='green', alpha=0.1)
        ax2.fill_between(self.trades_df['exit_date'], self.trades_df['cumulative_profit'], 0, where=(self.trades_df['cumulative_profit']<0), color='red', alpha=0.1)
        ax2.set_title('Cumulative Profit', fontsize=10)
        ax2.grid(True, alpha=0.3)

        # === グラフ3: トレード別損益 ===
        ax3 = axes[2]
        colors = ['green' if x > 0 else 'red' for x in self.trades_df['profit']]
        ax3.bar(range(len(self.trades_df)), self.trades_df['profit'], color=colors, alpha=0.7)
        ax3.axhline(0, color='black', linewidth=0.5)
        ax3.set_title('Trade P&L', fontsize=10)
        ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig

    def plot_all_trades(self):
        """全トレードの詳細チャートを作成してFigureのリストを返す"""
        if self.trades_df is None or len(self.trades_df) == 0:
            return []

        figs = []
        for idx, trade in self.trades_df.iterrows():
            start_date = trade['entry_date'] - pd.Timedelta(days=20)
            end_date = trade['exit_date'] + pd.Timedelta(days=10)

            trade_data = self.daily_data[(self.daily_data.index >= start_date) & (self.daily_data.index <= end_date)].copy()
            if trade_data.empty:
                continue

            fig, ax = plt.subplots(figsize=(10, 6))

            # ローソク足描画ヘルパー呼び出し
            self._plot_candlestick(ax, trade_data)

            # MA
            x_range = range(len(trade_data))
            ax.plot(x_range, trade_data['MA_short'].values, label='MA7', color='blue', alpha=0.5)
            ax.plot(x_range, trade_data['MA_mid'].values, label='MA20', color='orange', alpha=0.5)
            ax.plot(x_range, trade_data['MA_long'].values, label='MA60', color='red', alpha=0.5)

            # ポイント
            try:
                entry_idx = trade_data.index.get_loc(trade['entry_date'])
                exit_idx = trade_data.index.get_loc(trade['exit_date'])
                
                ax.scatter(entry_idx, trade['entry_price'], marker='^', color='green', s=150, zorder=10, label='Entry')

                exit_color = 'red' if trade['profit'] < 0 else 'blue'
                ax.scatter(exit_idx, trade['exit_price'],
                           marker='v' if trade['profit']<0 else 'o',
                           color=exit_color, 
                           s=150, zorder=10, 
                           edgecolors='black', 
                           linewidth=2,        
                           label='Exit') 
            except KeyError:
                pass # 日付インデックスが見つからない場合の安全策

            title = f"Trade #{idx+1} | Profit: {trade['profit']:.0f} ({trade['profit_pct']:.2f}%) | {trade['exit_reason']}"
            ax.set_title(title, fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # X軸の日付調整
            tick_idxs = np.linspace(0, len(trade_data)-1, 6, dtype=int)
            ax.set_xticks(tick_idxs)
            ax.set_xticklabels([trade_data.index[i].strftime('%m/%d') for i in tick_idxs])

            plt.tight_layout()
            figs.append(fig)
            
        return figs

# =======================================================
# 📈 シグナル根拠チャート描画用ヘルパー関数
# =======================================================
def plot_stock_chart_with_ma(ticker, name, interval='1d'):
    """
    指定された銘柄の最新のチャートを、MA付きで描画する。
    日足は90日、週足は1年間のデータを取得。（シグナル根拠の最長MA=60をカバーするため）
    """
    
    # 期間設定: 日足は3ヶ月(90日)、週足は1年間(60週≒約1年)
    if interval == '1d':
        period_str = '90d' 
    elif interval == '1wk':
        period_str = '1y' 
    else:
        return None

    try:
        # yfinanceでデータ取得
        data = yf.download(ticker, interval=interval, period=period_str, progress=False)
        if data.empty:
            return None
    except Exception as e:
        print(f"チャートデータ取得エラー ({ticker}, {interval}): {e}")
        return None

    # MAの計算 (screening.pyの定数を使用)
    data['MA_Short'] = data['Close'].rolling(window=MA_SHORT).mean()
    data['MA_Mid'] = data['Close'].rolling(window=MA_MID).mean()
    data['MA_Long'] = data['Close'].rolling(window=MA_LONG).mean()
    
    # 描画設定
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # --- ローソク足の描画 ---
    width = 0.6 
    data_for_plot = data.reset_index()
    # MatplotlibのX軸用に数値インデックスを使用
    data_for_plot['Date_Num'] = data_for_plot.index 
    
    for i in range(len(data_for_plot)):
        row = data_for_plot.iloc[i]
        date_num = row['Date_Num']
        o, c, h, l = row['Open'], row['Close'], row['High'], row['Low']
        
        # 色設定
        color = 'red' if c >= o else 'blue'
        
        # 胴体 (body)
        height = abs(c - o)
        bottom = min(o, c)
        rect = Rectangle((date_num - width/2, bottom), width, height, facecolor=color, edgecolor='black', linewidth=0.5)
        ax.add_patch(rect)
        
        # ひげ (wick)
        ax.plot([date_num, date_num], [l, min(o, c)], color='black', linewidth=1) # 下ひげ
        ax.plot([date_num, date_num], [max(o, c), h], color='black', linewidth=1) # 上ひげ
        
    # MAのプロット
    ax.plot(data_for_plot['Date_Num'], data_for_plot['MA_Short'], label=f'MA{MA_SHORT}', color='orange', linewidth=1.5)
    ax.plot(data_for_plot['Date_Num'], data_for_plot['MA_Mid'], label=f'MA{MA_MID}', color='purple', linewidth=1.5)
    ax.plot(data_for_plot['Date_Num'], data_for_plot['MA_Long'], label=f'MA{MA_LONG}', color='green', linewidth=1.5)

    # タイトルと凡例
    ax.set_title(f'[{interval}] {name} ({ticker}) Chart with MAs', fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    # X軸を日付ラベルで設定
    import matplotlib.dates as mdates
    tick_idxs = np.linspace(0, len(data_for_plot)-1, min(10, len(data_for_plot)), dtype=int)
    ax.set_xticks(tick_idxs)
    
    if interval == '1d':
        date_format = '%Y-%m-%d'
    elif interval == '1wk':
        date_format = '%Y-%m'

    ax.set_xticklabels([data_for_plot['Date'].iloc[i].strftime(date_format) for i in tick_idxs], rotation=45, ha='right')
    
    # Y軸のスケール調整
    if not data.empty:
        min_y = data['Low'].min()
        max_y = data['High'].max()
        ax.set_ylim(min_y * 0.98, max_y * 1.02)
    
    plt.tight_layout()
    
    return fig