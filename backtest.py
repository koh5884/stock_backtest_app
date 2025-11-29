import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from datetime import timedelta

# Streamlitでの描画用にバックエンド設定
import matplotlib
matplotlib.use('Agg')  

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


class SwingTradeBacktest:
    """シンプル化されたバックテストクラス（Streamlit統合用）"""

    def __init__(self, ticker, start_date, end_date, rules: TradingRules):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.rules = rules
        self.data = None
        self.trades_df = pd.DataFrame()
        self.performance = None
        self.equity_curve = None


    def _prepare_data(self):
        """データを取得し、MAとシグナルを計算する"""
        try:
            # データ取得
            # ... (省略: yfinanceのデータ取得ロジックは変更なし)
            self.data = yf.download(
                self.ticker, 
                start=self.start_date, 
                end=self.end_date, 
                progress=False
            )
            if self.data.empty:
                raise ValueError("指定された期間のデータが取得できませんでした。")
        except Exception as e:
            raise Exception(f"データ取得エラー: {e}")

        # MA計算
        self.data['MA_Short'] = self.data['Close'].rolling(self.rules.ma_short).mean()
        self.data['MA_Mid'] = self.data['Close'].rolling(self.rules.ma_mid).mean()
        self.data['MA_Long'] = self.data['Close'].rolling(self.rules.ma_long).mean()
        
        # 傾き計算
        ma_mid_shifted = self.data['MA_Mid'].shift(self.rules.slope_period)
        self.data['Slope_MA_Mid'] = (self.data['MA_Mid'] / ma_mid_shifted - 1) * 100
        
        self.data.dropna(inplace=True)


    def _run_strategy(self):
        # ... (省略: 戦略ロジックは変更なし)
        """トレード戦略のロジックを実行する"""
        if self.data is None or self.data.empty:
            return

        trades = []
        in_trade = False
        entry_price = 0
        entry_date = None
        
        data = self.data.copy()

        for i in range(len(data)):
            row = data.iloc[i]
            
            # --- エントリー条件 ---
            C1_Trend = row['Slope_MA_Mid'] >= self.rules.slope_threshold
            C2_Long = row['MA_Mid'] > row['MA_Long']
            C3_Pullback = row['MA_Short'] < row['MA_Mid']
            C4_Trigger = row['Close'] > row['MA_Short']
            
            entry_signal = C1_Trend and C2_Long and C3_Pullback and C4_Trigger

            if not in_trade and entry_signal:
                # エントリー
                in_trade = True
                entry_price = row['Close']
                entry_date = data.index[i]
            
            # --- エグジット条件 ---
            if in_trade:
                exit_signal = False
                exit_reason = ""
                exit_price = 0
                
                # 損切りライン (直近N日間の安値 * 損切り率)
                lookback_low = data['Low'].iloc[max(0, i - self.rules.stop_loss_lookback):i].min()
                stop_loss_level = lookback_low * self.rules.stop_loss_percentage
                
                # 損切り判定
                if row['Low'] < stop_loss_level:
                    exit_signal = True
                    exit_reason = "Stop Loss"
                    exit_price = stop_loss_level 

                # トレード終了処理
                if exit_signal or (i == len(data) - 1):
                    exit_date = data.index[i] if exit_signal else data.index[-1]
                    final_exit_price = exit_price if exit_signal else row['Close']
                    
                    if exit_date > entry_date:
                        profit = final_exit_price - entry_price
                        profit_pct = (final_exit_price / entry_price - 1) * 100
                        holding_days = (exit_date - entry_date).days

                        trades.append({
                            'entry_date': entry_date,
                            'entry_price': entry_price,
                            'exit_date': exit_date,
                            'exit_price': final_exit_price,
                            'profit': profit,
                            'profit_pct': profit_pct,
                            'holding_days': holding_days,
                            'exit_reason': exit_reason if exit_signal else "Time Out"
                        })
                    
                    in_trade = False
        
        self.trades_df = pd.DataFrame(trades)

    def _calculate_performance(self):
        # ... (省略: パフォーマンス計算ロジックは変更なし)
        """パフォーマンス指標を計算する"""
        if self.trades_df.empty:
            self.performance = None
            return

        trades_df = self.trades_df.copy()

        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['profit'] > 0])
        losing_trades = total_trades - winning_trades
        
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        total_profit = trades_df['profit'].sum()
        
        avg_profit = trades_df[trades_df['profit'] > 0]['profit'].sum() / winning_trades if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['profit'] <= 0]['profit'].sum() / losing_trades if losing_trades > 0 else 0
        
        avg_profit_pct = trades_df[trades_df['profit'] > 0]['profit_pct'].mean() if winning_trades > 0 else 0
        avg_loss_pct = trades_df[trades_df['profit'] <= 0]['profit_pct'].mean() if losing_trades > 0 else 0

        # ドローダウン計算
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
            'profit_factor': abs(avg_profit / avg_loss) if avg_loss != 0 else np.inf
        }

        # エクイティカーブ（累積損益）
        self.equity_curve = trades_df[['cumulative_profit']].reset_index(drop=True)


    def run(self):
        """バックテストを実行し、結果を返す"""
        try:
            self._prepare_data()
            self._run_strategy()
            self._calculate_performance()
            return self.performance
        except Exception:
            # エラーが発生した場合はNoneを返し、app.py側で警告を出せるようにする
            return None


    # =======================================================
    # 📈 グラフ描画メソッド (Streamlit用)
    # =======================================================

    def _plot_candlestick(self, ax, data):
        """ローソク足描画ヘルパー (陽線: 緑, 陰線: 赤)"""
        width = 0.6
        for i, (idx, row) in enumerate(data.iterrows()):
            open_p, close_p, high_p, low_p = row['Open'], row['Close'], row['High'], row['Low']
            # 陽線: 緑, 陰線: 赤 に統一
            color = 'green' if close_p >= open_p else 'red'
            
            # ヒゲ
            ax.plot([i, i], [low_p, high_p], color='black', linewidth=1)
            # 本体
            rect_bottom = open_p if close_p >= open_p else close_p
            height = abs(close_p - open_p)
            rect = Rectangle((i - width/2, rect_bottom), width, height, facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(rect)
        
        # MAのプロット
        # dataはplot_dataのコピーなので、MAカラムはそのまま使える
        ax.plot(data.index, data['MA_Short'], label=f'MA{self.rules.ma_short}', color='orange', linewidth=1.5)
        ax.plot(data.index, data['MA_Mid'], label=f'MA{self.rules.ma_mid}', color='blue', linewidth=1.5)
        ax.plot(data.index, data['MA_Long'], label=f'MA{self.rules.ma_long}', color='purple', linewidth=1.5)


    def plot_overview(self):
        """エクイティカーブと価格の全体像をプロットする"""
        if self.data is None or self.trades_df.empty:
            return None

        # --- 修正: データコピーとインデックスリセットをローカルに行う ---
        plot_data = self.data.reset_index().copy() 
        data_indices = np.arange(len(plot_data))
        plot_data.index = data_indices
        # yfinanceのデフォルト挙動によりインデックスが'Date'カラムになっていることを想定
        # -----------------------------------------------------------
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=False)
        fig.suptitle(f"{self.ticker} | バックテスト概要", fontsize=16, fontweight='bold')
        
        # --- Ax1: 価格とMA ---
        self._plot_candlestick(ax1, plot_data) # <--- 修正: plot_dataを渡す
        
        # エントリー/エグジットポイントの描画
        for _, trade in self.trades_df.iterrows():
            # 日付に対応するインデックスを取得
            # 修正: plot_dataの'Date'カラムと新しいインデックスを使用
            entry_idx = plot_data[plot_data['Date'] == trade['entry_date']].index[0]
            exit_idx = plot_data[plot_data['Date'] == trade['exit_date']].index[0]
            
            # エントリー
            ax1.scatter(entry_idx, trade['entry_price'], 
                        marker='^', color='darkgreen', s=100, zorder=10, 
                        label='Entry' if ax1.get_legend() is None else None)
            # エグジット
            exit_color = 'red' if trade['profit'] < 0 else 'blue'
            ax1.scatter(exit_idx, trade['exit_price'], 
                        marker='v', color=exit_color, s=100, zorder=10, 
                        label='Exit' if ax1.get_legend() is None else None)
            
            # トレード期間のハイライト (緑:勝ち, 赤:負け)
            trade_color = 'lightgreen' if trade['profit'] > 0 else 'salmon'
            ax1.axvspan(entry_idx, exit_idx, facecolor=trade_color, alpha=0.2)
        
        ax1.set_title("価格推移とトレードポイント", fontsize=12)
        ax1.set_ylabel("価格")
        ax1.grid(True, alpha=0.3)
        # 凡例を一度だけ表示するためにハンドル/ラベルをフィルタリング
        handles, labels = ax1.get_legend_handles_labels()
        unique_labels = dict(zip(labels, handles))
        ax1.legend(unique_labels.values(), unique_labels.keys())


        # --- Ax2: エクイティカーブ ---
        equity_indices = np.arange(len(self.equity_curve))
        ax2.plot(equity_indices, self.equity_curve['cumulative_profit'], 
                 color='darkblue', linewidth=2, label='Equity Curve')
        ax2.fill_between(equity_indices, self.equity_curve['cumulative_profit'], 0, 
                         color='lightblue', alpha=0.3)

        # ドローダウンの描画
        ax2.plot(equity_indices, self.equity_curve['running_max'].iloc[:len(equity_indices)], 
                 linestyle='--', color='orange', label='Running Max')
        
        ax2.set_title("累積損益 (Equity Curve)", fontsize=12)
        ax2.set_ylabel("累積損益")
        ax2.set_xlabel("トレード回数")
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        # X軸の日付ラベル設定（共有しないため個別に設定）
        ax1.set_xticks(data_indices[::len(data_indices)//5 or 1])
        # 修正: plot_dataのDateカラムを参照
        ax1.set_xticklabels([plot_data['Date'].iloc[i].strftime('%Y-%m-%d') for i in data_indices[::len(data_indices)//5 or 1]], rotation=45, ha='right')

        plt.tight_layout()
        return fig


    def plot_all_trades(self):
        """全ての個別トレードの詳細をプロットする"""
        if self.trades_df.empty or self.data is None:
            return []

        figs = []
        
        # --- 修正: データコピーとインデックスリセットをローカルに行う ---
        full_plot_data = self.data.reset_index().copy() 
        # -----------------------------------------------------------
        
        for idx, trade in self.trades_df.iterrows():
            # トレード期間を抽出 (前後に5日間のバッファを持たせる)
            # 修正: full_plot_dataの'Date'カラムを使ってインデックスを検索
            start_date_idx = full_plot_data[full_plot_data['Date'] == trade['entry_date']].index[0]
            exit_date_idx = full_plot_data[full_plot_data['Date'] == trade['exit_date']].index[0]
            
            start_idx = start_date_idx - 5
            end_idx = exit_date_idx + 5
            
            start_idx = max(0, start_idx)
            end_idx = min(len(full_plot_data) - 1, end_idx)

            trade_data = full_plot_data.iloc[start_idx:end_idx].copy()
            
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # X軸のインデックスを0から振り直し
            trade_data.reset_index(drop=True, inplace=True) 

            # ローソク足とMAの描画
            self._plot_candlestick(ax, trade_data)
            
            # エントリー/エグジットポイントの描画
            entry_idx = trade_data[trade_data['Date'] == trade['entry_date']].index[0]
            exit_idx = trade_data[trade_data['Date'] == trade['exit_date']].index[0]

            # エントリーポイント
            ax.scatter(entry_idx, trade['entry_price'], 
                       marker='^', color='darkgreen', 
                       s=150, zorder=10, 
                       edgecolors='black', 
                       linewidth=2,
                       label='Entry Price')
            
            # エグジットポイント
            exit_color = 'red' if trade['profit'] < 0 else 'blue'
            ax.scatter(exit_idx, trade['exit_price'], 
                       marker='v', color=exit_color, 
                       s=150, zorder=10, 
                       edgecolors='black', 
                       linewidth=2,        
                       label='Exit') 
            
            # 損切りラインの描画 (損切りエグジットの場合のみ)
            if trade['exit_reason'] == 'Stop Loss':
                ax.axhline(trade['exit_price'], color='red', linestyle='--', linewidth=1, label='Stop Loss Level')

            title = f"Trade #{idx+1} | Profit: {trade['profit']:.0f} ({trade['profit_pct']:.2f}%) | {trade['exit_reason']}"
            ax.set_title(title, fontsize=12, fontweight='bold')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # X軸の日付調整
            tick_idxs = np.linspace(0, len(trade_data)-1, 6, dtype=int)
            ax.set_xticks(tick_idxs)
            # 修正: trade_dataのDateカラムを参照
            ax.set_xticklabels([trade_data.iloc[i]['Date'].strftime('%m/%d') for i in tick_idxs])

            plt.tight_layout()
            figs.append(fig)
            
        return figs