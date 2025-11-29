import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from datetime import timedelta

# Streamlitでの描画用にバックエンド設定
import matplotlib
matplotlib.use('Agg')  

# ... (TradingRules, SwingTradeBacktest.__init__, _prepare_data, _run_strategy, _calculate_performance, run は変更なし) ...

class SwingTradeBacktest:
    # ... (前略)

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
        # ... (変更なし) ...
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
        ax.plot(data.index, data['MA_Short'], label=f'MA{self.rules.ma_short}', color='orange', linewidth=1.5)
        ax.plot(data.index, data['MA_Mid'], label=f'MA{self.rules.ma_mid}', color='blue', linewidth=1.5)
        ax.plot(data.index, data['MA_Long'], label=f'MA{self.rules.ma_long}', color='purple', linewidth=1.5)


    def plot_overview(self):
        """エクイティカーブと価格の全体像をプロットする"""
        if self.data is None or self.trades_df.empty:
            return None

        try:
            # データコピーとインデックスリセットをローカルに行う
            plot_data = self.data.reset_index().copy() 
            data_indices = plot_data.index # 0, 1, 2, ...
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=False)
            fig.suptitle(f"{self.ticker} | バックテスト概要", fontsize=16, fontweight='bold')
            
            # --- Ax1: 価格とMA ---
            self._plot_candlestick(ax1, plot_data)
            
            # エントリー/エグジットポイントの描画
            for _, trade in self.trades_df.iterrows():
                try:
                    # 日付に対応するインデックスを取得
                    entry_idx = plot_data[plot_data['Date'] == trade['entry_date']].index[0]
                    exit_idx = plot_data[plot_data['Date'] == trade['exit_date']].index[0]
                except IndexError:
                    # トレードデータがデータ範囲外や欠損値の場合はスキップ
                    continue
                
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
            handles, labels = ax1.get_legend_handles_labels()
            unique_labels = dict(zip(labels, handles))
            ax1.legend(unique_labels.values(), unique_labels.keys())


            # --- Ax2: エクイティカーブ ---
            equity_indices = np.arange(len(self.equity_curve))
            ax2.plot(equity_indices, self.equity_curve['cumulative_profit'], 
                    color='darkblue', linewidth=2, label='Equity Curve')
            ax2.fill_between(equity_indices, self.equity_curve['cumulative_profit'], 0, 
                            color='lightblue', alpha=0.3)

            ax2.plot(equity_indices, self.equity_curve['running_max'].iloc[:len(equity_indices)], 
                    linestyle='--', color='orange', label='Running Max')
            
            ax2.set_title("累積損益 (Equity Curve)", fontsize=12)
            ax2.set_ylabel("累積損益")
            ax2.set_xlabel("トレード回数")
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # X軸の日付ラベル設定
            ax1.set_xticks(data_indices[::len(data_indices)//5 or 1])
            ax1.set_xticklabels([plot_data['Date'].iloc[i].strftime('%Y-%m-%d') for i in data_indices[::len(data_indices)//5 or 1]], rotation=45, ha='right')

            plt.tight_layout()
            return fig
        
        except Exception:
            # その他の描画エラーが発生した場合、Noneを返してクラッシュを防ぐ
            return None


    def plot_all_trades(self):
        """全ての個別トレードの詳細をプロットする"""
        if self.trades_df.empty or self.data is None:
            return []

        figs = []
        
        try:
            # データコピーとインデックスリセットをローカルに行う
            full_plot_data = self.data.reset_index().copy() 
            
            for idx, trade in self.trades_df.iterrows():
                try:
                    # トレード期間を抽出 (前後に5日間のバッファを持たせる)
                    start_date_idx = full_plot_data[full_plot_data['Date'] == trade['entry_date']].index[0]
                    exit_date_idx = full_plot_data[full_plot_data['Date'] == trade['exit_date']].index[0]
                except IndexError:
                    # トレードデータの日付が見つからない場合はスキップ
                    continue
                
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
                try:
                    entry_idx = trade_data[trade_data['Date'] == trade['entry_date']].index[0]
                    exit_idx = trade_data[trade_data['Date'] == trade['exit_date']].index[0]
                except IndexError:
                    # 再度チェックし、データがまだ存在しない場合はスキップ
                    plt.close(fig)
                    continue

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
                ax.set_xticklabels([trade_data.iloc[i]['Date'].strftime('%m/%d') for i in tick_idxs])

                plt.tight_layout()
                figs.append(fig)
                
            return figs
        
        except Exception:
            # その他の描画エラーが発生した場合、空リストを返してクラッシュを防ぐ
            return []