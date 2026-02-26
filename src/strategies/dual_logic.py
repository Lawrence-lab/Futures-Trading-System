import logging
import pandas as pd
from datetime import datetime
from .indicators import calculate_supertrend, calculate_ut_bot, calculate_atr
from src.line_notify import send_line_push_message
from src.db_logger import log_trade_entry, log_trade_exit
import shioaji as sj

class DualTimeframeStrategy:
    def __init__(self, name="DualTimeframe", api=None, contract=None):
        self.name = name
        self.api = api
        self.contract = contract
        self.contract = contract
        self.is_long = False
        self.is_short = False
        self.entry_price = 0.0
        self.entry_time = None
        self.highest_price = 0.0
        self.lowest_price = float('inf')
        self.stop_loss = 0.0
        self.break_even_triggered = False
        self.current_db_trade_id = -1
        
        self.trades = [] # List to store trade history: {entry_time, exit_time, entry_price, exit_price, pnl, reason}
        
        # Parameters
        self.be_threshold = 150.0  # 保本觸發點 (Optimized: 150)
        self.trailing_stop_drop = 100.0 # 折返停利點
        self.ut_bot_key = 3.5 # UT Bot Sensitivity (Optimized: 3.5)
        self.body_filter = 100.0 # Candle Body Filter (Optimized: 100)

    def check_signals(self, df_60m, df_1d, precalc_bullish_1d=None, precalc_signal_60m=None):
        if df_60m.empty or df_1d.empty: return
        
        # 1. Check Daily Trend (The Filter)
        if precalc_bullish_1d is not None:
             is_bullish_1d = precalc_bullish_1d
        else:
             is_bullish_1d, _ = calculate_supertrend(df_1d)
        
        # 2. Check 60M Signal (The Trigger)
        if precalc_signal_60m is not None:
             signal_60m = precalc_signal_60m
        else:
             signal_60m = calculate_ut_bot(df_60m, key_value=self.ut_bot_key)
        
        current_bar = df_60m.iloc[-1]
        current_price = float(current_bar['close'])
        current_open = float(current_bar['open'])
        current_time = current_bar.get('datetime', datetime.now())
        
        # Calculate ATR for dynamic stop loss
        # ATR also needs to be efficient. For backtest, we can accept re-calc or pre-calc.
        # Since ATR calc is fast (rolling window), we can keep it or pre-calc.
        # Let's keep it simple for now, ATR on slice is okay-ish, or optimize later.
        # But for max speed, better to just take it from the row if available.
        # Assuming df_60m has 'atr' if pre-calculated.
        
        if 'atr' in df_60m.columns:
             current_atr = current_bar['atr']
        else:
             atr_series = calculate_atr(df_60m, period=10)
             current_atr = atr_series.iloc[-1] if not atr_series.empty else 20.0
        
        # Entry Logic
        if not self.is_long and not self.is_short:
            # Body Filter: Close - Open > 60 (For Long), Open - Close > 60 (For Short)
            bullish_body = (current_price - current_open) > self.body_filter
            bearish_body = (current_open - current_price) > self.body_filter
            
            # Long Entry
            if is_bullish_1d and signal_60m == "Buy" and bullish_body:
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
                candle_range = float(current_bar['high']) - float(current_bar['low'])
                ratio = round((body / candle_range * 100), 2) if candle_range > 0 else 0
                msg = f"🎯 門神出擊！\n方向：做多 (LONG)\n點位：{self.entry_price}\n停損：{self.stop_loss:.1f}\n目前的 Body Ratio：{ratio}%"
                
                if "Backtest" not in self.name:
                    send_line_push_message(msg)
                    
                    # Write to database (Trade Entry)
                    self.current_db_trade_id = log_trade_entry(
                        strategy_name=self.name,
                        side="Buy",
                        entry_price=float(self.entry_price),
                        entry_time=current_time
                    )
                    
                    # Physical Order Execution
                    if self.api and self.contract:
                        try:
                            order = self.api.Order(
                                action=sj.constant.Action.Buy,
                                price=0,
                                quantity=1,
                                price_type=sj.constant.FuturesPriceType.MWP,
                                order_type=sj.constant.OrderType.ROD, 
                                octype=sj.constant.FuturesOCType.Auto
                            )
                            trade = self.api.place_order(self.contract, order)
                            logging.info(f"[{self.name}] [ORDER] 實體買單已送出: {trade}")
                        except Exception as e:
                            error_msg = f"❌ [{self.name}] [ERROR] 買單送出失敗: {e}"
                            logging.error(error_msg)
                            send_line_push_message(error_msg)

            # Short Entry
            elif not is_bullish_1d and signal_60m == "Sell" and bearish_body:
                self.is_short = True
                self.entry_price = current_price
                self.entry_time = current_time
                self.lowest_price = current_price
                
                # Dynamic Stop Loss: 2.0 * ATR
                stop_dist = 2.0 * current_atr
                self.stop_loss = current_price + stop_dist
                self.break_even_triggered = False
                
                logging.info(f"[{self.name}] [SIGNAL] 放空進場 | 時間: {current_time} | 價格: {self.entry_price} | 實體: {current_open - current_price:.1f} | ATR: {current_atr:.1f} | 停損: {self.stop_loss:.1f}")
                
                # LINE Notify: Entry
                body = current_open - current_price
                candle_range = float(current_bar['high']) - float(current_bar['low'])
                ratio = round((body / candle_range * 100), 2) if candle_range > 0 else 0
                msg = f"🎯 門神出擊！\n方向：放空 (SHORT)\n點位：{self.entry_price}\n停損：{self.stop_loss:.1f}\n目前的 Body Ratio：{ratio}%"
                
                if "Backtest" not in self.name:
                    send_line_push_message(msg)
                    
                    # Write to database (Trade Entry)
                    self.current_db_trade_id = log_trade_entry(
                        strategy_name=self.name,
                        side="Sell",
                        entry_price=float(self.entry_price),
                        entry_time=current_time
                    )
                    
                    # Physical Order Execution
                    if self.api and self.contract:
                        try:
                            order = self.api.Order(
                                action=sj.constant.Action.Sell,
                                price=0,
                                quantity=1,
                                price_type=sj.constant.FuturesPriceType.MWP,
                                order_type=sj.constant.OrderType.ROD, 
                                octype=sj.constant.FuturesOCType.Auto
                            )
                            trade = self.api.place_order(self.contract, order)
                            logging.info(f"[{self.name}] [ORDER] 實體賣單出擊: {trade}")
                        except Exception as e:
                            error_msg = f"❌ [{self.name}] [ERROR] 賣單送出失敗: {e}"
                            logging.error(error_msg)
                            send_line_push_message(error_msg)

        
        # Exit / Risk Management Logic
        elif self.is_long:
            self.highest_price = max(self.highest_price, current_price)
            profit = current_price - self.entry_price
            
            # Excel: 保本機制
            if not self.break_even_triggered and profit >= self.be_threshold:
                self.stop_loss = self.entry_price
                self.break_even_triggered = True
                logging.info(f"[{self.name}] [RISK] 多單啟動保本 | 時間: {current_time} | 目前價格: {current_price} | 停損移至成本: {self.stop_loss}")
            
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
                logging.info(f"[{self.name}] [EXIT] {exit_reason} (Long) | 時間: {current_time} | 出場價格: {current_price} | 損益: {pnl}")
                
                self.trades.append({
                    'strategy': self.name,
                    'direction': 'Long',
                    'entry_time': self.entry_time,
                    'exit_time': current_time,
                    'entry_price': self.entry_price,
                    'exit_price': current_price,
                    'pnl': pnl,
                    'reason': exit_reason
                })
                
                # Update database (Trade Exit)
                if self.current_db_trade_id != -1 and "Backtest" not in self.name:
                    log_trade_exit(
                        trade_id=self.current_db_trade_id,
                        exit_price=float(current_price),
                        exit_time=current_time,
                        pnl_points=float(pnl)
                    )
                    self.current_db_trade_id = -1
                    
                    # 實體委託單送出 (Physical Order Execution)
                    if self.api and self.contract:
                        try:
                            order = self.api.Order(
                                action=sj.constant.Action.Sell, # 平倉賣出
                                price=0, 
                                quantity=1,
                                price_type=sj.constant.FuturesPriceType.MWP,
                                order_type=sj.constant.OrderType.ROD,
                                octype=sj.constant.FuturesOCType.Auto
                            )
                            trade = self.api.place_order(self.contract, order)
                            logging.info(f"[{self.name}] [ORDER] 實體賣單 (平多單) 已送出: {trade}")
                            msg = f"💸 門神平倉出局！\n出局原因：{exit_reason}\n出場點位：{current_price}\n損益點數：{pnl:.1f}"
                            send_line_push_message(msg)
                        except Exception as e:
                            error_msg = f"❌ [{self.name}] [ERROR] 賣單送出失敗: {e}"
                            logging.error(error_msg)
                            send_line_push_message(error_msg)

        elif self.is_short:
            self.lowest_price = min(self.lowest_price, current_price)
            profit = self.entry_price - current_price # Short PnL is inverted
            
            # Excel: 保本機制
            if not self.break_even_triggered and profit >= self.be_threshold:
                self.stop_loss = self.entry_price
                self.break_even_triggered = True
                logging.info(f"[{self.name}] [RISK] 空單啟動保本 | 時間: {current_time} | 目前價格: {current_price} | 停損移至成本: {self.stop_loss}")
            
            # Check Exit Conditions
            exit_reason = None
            
            # Excel: 折返點數停利 (反彈)
            if profit >= self.be_threshold:
                if current_price >= (self.lowest_price + self.trailing_stop_drop):
                    exit_reason = "Trailing Stop"
            
            # Hard Stop Loss (Touched upper band)
            if current_price >= self.stop_loss:
                exit_reason = "Stop Loss" if not self.break_even_triggered else "Break Even"
            
            if exit_reason:
                self.is_short = False
                pnl = self.entry_price - current_price
                logging.info(f"[{self.name}] [EXIT] {exit_reason} (Short) | 時間: {current_time} | 出場價格: {current_price} | 損益: {pnl}")
                
                self.trades.append({
                    'strategy': self.name,
                    'direction': 'Short',
                    'entry_time': self.entry_time,
                    'exit_time': current_time,
                    'entry_price': self.entry_price,
                    'exit_price': current_price,
                    'pnl': pnl,
                    'reason': exit_reason
                })
                
                # Update database (Trade Exit)
                if self.current_db_trade_id != -1 and "Backtest" not in self.name:
                    log_trade_exit(
                        trade_id=self.current_db_trade_id,
                        exit_price=float(current_price),
                        exit_time=current_time,
                        pnl_points=float(pnl)
                    )
                    self.current_db_trade_id = -1
                    
                    # 實體委託單送出 (Physical Order Execution)
                    if self.api and self.contract:
                        try:
                            order = self.api.Order(
                                action=sj.constant.Action.Buy, # 平倉買回
                                price=0, 
                                quantity=1,
                                price_type=sj.constant.FuturesPriceType.MWP,
                                order_type=sj.constant.OrderType.ROD,
                                octype=sj.constant.FuturesOCType.Auto
                            )
                            trade = self.api.place_order(self.contract, order)
                            logging.info(f"[{self.name}] [ORDER] 實體買單 (平空單) 已送出: {trade}")
                            msg = f"💸 門神平空單出局！\n出局原因：{exit_reason}\n出場點位：{current_price}\n損益點數：{pnl:.1f}"
                            send_line_push_message(msg)
                        except Exception as e:
                            error_msg = f"❌ [{self.name}] [ERROR] 買單送出失敗: {e}"
                            logging.error(error_msg)
                            send_line_push_message(error_msg)
