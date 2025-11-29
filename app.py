import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from ticker_list import sp500_list, nikkei225_list
from screening import MA_SHORT, MA_MID, MA_LONG, SLOPE_THRESHOLD, SLOPE_PERIOD
from screening import get_data_and_screen_advanced

st.set_page_config(page_title="株式スクリーニング", page_icon="📈", layout="wide")

st.title("📈 株式スクリーニング＆ヒートマップ分析")
st.markdown("""
このアプリは移動平均線を使った**押し目買い戦略**のスクリーニングツールです。  
強いトレンドの中で一時的に調整した銘柄を自動検出します。
""")
# --- サイドバー ---
st.sidebar.header("スクリーニング設定")
use_sp500 = st.sidebar.checkbox("S&P 500（米国株）", value=True)
use_nikkei = st.sidebar.checkbox("日経225（日本株）", value=False)
# 銘柄リストの決定
stock_list = []
if use_sp500:
    stock_list += sp500_list
if use_nikkei:
    stock_list += nikkei225_list