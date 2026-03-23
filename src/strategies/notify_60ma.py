import logging
import pandas as pd
from datetime import datetime
from src.discord_notify import send_discord_message

class Notify60maStrategy:
    def __init__(self, name="Notify_60MA_Crossover", portfolio=None, contract=None):
        """
        純通知型策略：不實作下單邏輯，僅作多空趨勢交叉提示。
        邏輯：
        - 判斷大局：日K線 > 20MA (多頭趨勢)，日K線 < 20MA (空頭趨勢)。
        - 觸發條件：
            多頭時：60 分 K 線向上突破 60MA (前一根在其下，最新一根在其上)。
            空頭時：60 分 K 線向下跌破 60MA (前一根在其上，最新一根在其下)。
        """
        self.name = name
        self.portfolio = portfolio
        self.contract = contract
        
        # 為了滿足 main.py 中的調用介面，宣告 is_long 與 is_short 為 False
        # 通知型策略永遠不持有部位
        self.is_long = False
        self.is_short = False
        self.entry_price = 0.0
        self.trades = []

    def check_signals(self, df_60m, df_1d=None):
        if df_60m.empty or len(df_60m) < 61: 
            return
        
        # 計算 60m 60MA
        sma_60m = df_60m['close'].rolling(window=60).mean()
        
        # 取得大局 (日 K)
        is_bullish = True # 預設偏多相容
        if df_1d is not None and not df_1d.empty and len(df_1d) >= 20:
            sma_1d = df_1d['close'].rolling(window=20).mean()
            current_1d_close = df_1d['close'].iloc[-1]
            current_1d_ma = sma_1d.iloc[-1]
            if not pd.isna(current_1d_ma):
                is_bullish = current_1d_close >= current_1d_ma
                
        # Get 60m previous and current prices & MAs
        prev_close_60 = df_60m['close'].iloc[-2]
        curr_close_60 = df_60m['close'].iloc[-1]
        
        prev_ma_60 = sma_60m.iloc[-2]
        curr_ma_60 = sma_60m.iloc[-1]
        
        if pd.isna(prev_ma_60) or pd.isna(curr_ma_60):
            return
            
        # 多頭時：做多邏輯 (向上突破 60MA)
        if is_bullish:
            if prev_close_60 <= prev_ma_60 and curr_close_60 > curr_ma_60:
                msg = f"🔔 【策略通知】目前大局偏【多】(日 K 點位位於月線 20MA 之上)。\n👉 發現小時 K 線剛剛『向上突破』小時 60MA ({curr_ma_60:.0f})！\n目前點位 {curr_close_60:.0f}，請留意做**多**機會 (僅通知，系統未自動下單)。"
                logging.info(f"[{self.name}] {msg}")
                send_discord_message(msg)
                
        # 空頭時：做空邏輯 (向下跌破 60MA)
        else:
            if prev_close_60 >= prev_ma_60 and curr_close_60 < curr_ma_60:
                msg = f"🔔 【策略通知】目前大局偏【空】(日 K 點位位於月線 20MA 之下)。\n👉 發現小時 K 線剛剛『向下跌破』小時 60MA ({curr_ma_60:.0f})！\n目前點位 {curr_close_60:.0f}，請留意做**空**機會 (僅通知，系統未自動下單)。"
                logging.info(f"[{self.name}] {msg}")
                send_discord_message(msg)

    def check_exit_signals(self, *args, **kwargs):
        """純通知策略，無出場邏輯"""
        pass
