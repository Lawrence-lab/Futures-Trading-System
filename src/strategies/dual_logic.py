import logging
import pandas as pd
from datetime import datetime
from .indicators import calculate_supertrend, calculate_ut_bot, calculate_atr
from src.line_notify import send_line_push_message
from src.db_logger import log_trade_entry, log_trade_exit

class DualTimeframeStrategy:
    def __init__(self, name="DualTimeframe"):
        self.name = name
        self.is_long = False
        self.entry_price = 0.0
        self.entry_time = None
        self.highest_price = 0.0
        self.stop_loss = 0.0
        self.break_even_triggered = False
        self.current_db_trade_id = -1
        
        self.trades = [] # List to store trade history: {entry_time, exit_time, entry_price, exit_price, pnl, reason}
        
        # Parameters
        self.be_threshold = 60.0  # 保本觸發點 (Optimized: 60)
        self.trailing_stop_drop = 30.0 # 折返停利點
        self.ut_bot_key = 3.5 # UT Bot Sensitivity (Optimized: 3.5)
        self.body_filter = 60.0 # Candle Body Filter (Optimized: 60)

    def check_signals(self, df_5m, df_60m, precalc_bullish_60m=None, precalc_signal_5m=None):
        if df_5m.empty or df_60m.empty: return
        
        # 1. Check 60M Trend (The Filter)
        if precalc_bullish_60m is not None:
             is_bullish_60m = precalc_bullish_60m
        else:
             is_bullish_60m, _ = calculate_supertrend(df_60m)
        
        # 2. Check 5M Signal (The Trigger)
        if precalc_signal_5m is not None:
             signal_5m = precalc_signal_5m
        else:
             signal_5m = calculate_ut_bot(df_5m, key_value=self.ut_bot_key)
        
        current_bar = df_5m.iloc[-1]
        current_price = current_bar['close']
        current_open = current_bar['open']
        current_time = current_bar.get('datetime', datetime.now())
        
        # Calculate ATR for dynamic stop loss
        # ATR also needs to be efficient. For backtest, we can accept re-calc or pre-calc.
        # Since ATR calc is fast (rolling window), we can keep it or pre-calc.
        # Let's keep it simple for now, ATR on slice is okay-ish, or optimize later.
        # But for max speed, better to just take it from the row if available.
        # Assuming df_5m has 'atr' if pre-calculated.
        
        if 'atr' in df_5m.columns:
             current_atr = current_bar['atr']
        else:
             atr_series = calculate_atr(df_5m, period=10)
             current_atr = atr_series.iloc[-1] if not atr_series.empty else 20.0
        
        # Entry Logic
        if not self.is_long:
            # Body Filter: Close - Open > 60
            is_valid_body = (current_price - current_open) > self.body_filter
            
            if is_bullish_60m and signal_5m == "Buy" and is_valid_body:
                self.is_long = True
                self.entry_price = current_price
                self.entry_time = current_time
                self.highest_price = current_price
                
                # Dynamic Stop Loss: 2.0 * ATR
                stop_dist = 2.0 * current_atr
                self.stop_loss = current_price - stop_dist
                self.break_even_triggered = False
                
                logging.info(f"[{self.name}] [SIGNAL] 買入進場 | 時間: {current_time} | 價格: {self.entry_price} | 實體: {current_price - current_open:.1f} | ATR: {current_atr:.1f} | 停損: {self.stop_loss:.1f}")
                
                # LINE Notify: Entry
                body = current_price - current_open
                candle_range = current_bar['high'] - current_bar['low']
                ratio = round((body / candle_range * 100), 2) if candle_range > 0 else 0
                msg = f"🎯 門神出擊！\n方向：做多 (LONG)\n點位：{self.entry_price}\n停損：{self.stop_loss:.1f}\n目前的 Body Ratio：{ratio}%"
                send_line_push_message(msg)
                
                # Write to database (Trade Entry)
                self.current_db_trade_id = log_trade_entry(
                    strategy_name=self.name,
                    side="Buy",
                    entry_price=float(self.entry_price),
                    entry_time=current_time
                )
        
        # Exit / Risk Management Logic
        else:
            self.highest_price = max(self.highest_price, current_price)
            profit = current_price - self.entry_price
            
            # Excel: 保本機制
            if not self.break_even_triggered and profit >= self.be_threshold:
                self.stop_loss = self.entry_price
                self.break_even_triggered = True
                logging.info(f"[{self.name}] [RISK] 啟動保本 | 時間: {current_time} | 目前價格: {current_price} | 停損移至成本: {self.stop_loss}")
            
            # Check Exit Conditions
            exit_reason = None
            
            # Excel: 折返點數停利
            if profit >= self.be_threshold:
                if current_price <= (self.highest_price - self.trailing_stop_drop):
                    exit_reason = "Trailing Stop"
            
            # Hard Stop Loss
            if current_price <= self.stop_loss:
                exit_reason = "Stop Loss" if not self.break_even_triggered else "Break Even"
            
            if exit_reason:
                self.is_long = False
                pnl = current_price - self.entry_price
                logging.info(f"[{self.name}] [EXIT] {exit_reason} | 時間: {current_time} | 出場價格: {current_price} | 損益: {pnl}")
                
                self.trades.append({
                    'strategy': self.name,
                    'entry_time': self.entry_time,
                    'exit_time': current_time,
                    'entry_price': self.entry_price,
                    'exit_price': current_price,
                    'pnl': pnl,
                    'reason': exit_reason
                })
                
                # Update database (Trade Exit)
                if self.current_db_trade_id != -1:
                    log_trade_exit(
                        trade_id=self.current_db_trade_id,
                        exit_price=float(current_price),
                        exit_time=current_time,
                        pnl_points=float(pnl)
                    )
                    self.current_db_trade_id = -1
