import logging
import pandas as pd
from datetime import datetime
from .indicators import calculate_supertrend, calculate_ut_bot, calculate_atr, calculate_adx
from src.discord_notify import send_discord_message
from src.db_logger import log_trade_entry, log_trade_exit
import shioaji as sj

class DualTimeframeStrategy:
    def __init__(self, name="DualTimeframe", portfolio=None, contract=None):
        self.name = name
        self.portfolio = portfolio
        self.contract = contract
        
        # 1. 初始化狀態：向 PortfolioManager 查詢此策略當前的持倉狀態
        initial_pos = 0
        if self.portfolio and self.contract:
            initial_pos = self.portfolio.get_virtual_position(self.name, self.contract.code)

        self.is_long = initial_pos > 0
        self.is_short = initial_pos < 0
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
        self.trailing_atr_mult = 1.5 # 移動停利倍數 (Optimized from backtest sweep)
        self.ut_bot_key = 3.5 # UT Bot Sensitivity (Optimized from backtest sweep)
        
        # 趨勢動能濾網 (ADX Filter)
        self.adx_threshold = 25.0 # 只有 ADX > 此數值才允許進場
        
        # 移除高門檻的實體濾網，讓趨勢一出來就進場
        self.body_filter = 0.0

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
        if 'atr' in df_60m.columns:
             current_atr = current_bar['atr']
        else:
             atr_series = calculate_atr(df_60m, period=10)
             current_atr = atr_series.iloc[-1] if not atr_series.empty else 20.0
             
        # Calculate ADX for trend filtering
        if 'adx' in df_60m.columns:
             current_adx = current_bar['adx']
        else:
             adx_series = calculate_adx(df_60m, period=14)
             current_adx = adx_series.iloc[-1] if (adx_series is not None and not adx_series.empty) else 0.0
        
        # Entry Logic
        if not self.is_long and not self.is_short:
            # Body Filter 已經設為 0，只要大於等於 0 即可 (即收紅K / 收黑K)
            bullish_body = (current_price - current_open) >= self.body_filter
            bearish_body = (current_open - current_price) >= self.body_filter
            
            # Trend Momentum Filter (ADX)
            has_momentum = current_adx > self.adx_threshold
            
            # Long Entry
            if is_bullish_1d and signal_60m == "Buy" and bullish_body and has_momentum:
                # 1. 嘗試發送實體單並登記虛擬部位
                order_success = True
                if self.portfolio and self.contract:
                    try:
                        order_success = self.portfolio.set_virtual_position(
                            strategy_name=self.name,
                            contract_symbol=self.contract.code,
                            new_position=1, # 1 for Long
                            contract_obj=self.contract,
                            average_cost=current_price
                        )
                        if order_success:
                            logging.info(f"[{self.name}] [ORDER] 虛擬買單紀錄與實體單確認成功。")
                    except Exception as e:
                        error_msg = f"❌ [{self.name}] [ERROR] 委派買單失敗: {e}"
                        logging.error(error_msg)
                        order_success = False

                if not order_success:
                    return

                # 2. 實體驗證成功後，才更新內部狀態
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
                msg = f"🎯 門神出擊！\n方向：做多 (LONG)\n點位：{self.entry_price}\n停損：{self.stop_loss:.1f}\n目前的 ADX：{current_adx:.1f}\n目前的 Body Ratio：{ratio}%"
                
                if "Backtest" not in self.name and "Opt" not in self.name:
                    send_discord_message(msg)
                    
                    # Write to database (Trade Entry)
                    self.current_db_trade_id = log_trade_entry(
                        strategy_name=self.name,
                        side="Buy",
                        entry_price=float(self.entry_price),
                        entry_time=current_time
                    )

            # Short Entry
            elif not is_bullish_1d and signal_60m == "Sell" and bearish_body and has_momentum:
                # 1. 嘗試發送實體單並登記虛擬部位
                order_success = True
                if self.portfolio and self.contract:
                    try:
                        order_success = self.portfolio.set_virtual_position(
                            strategy_name=self.name,
                            contract_symbol=self.contract.code,
                            new_position=-1, # -1 for Short
                            contract_obj=self.contract,
                            average_cost=current_price
                        )
                        if order_success:
                            logging.info(f"[{self.name}] [ORDER] 虛擬賣單紀錄與實體單確認成功。")
                    except Exception as e:
                        error_msg = f"❌ [{self.name}] [ERROR] 委派放空訂單失敗: {e}"
                        logging.error(error_msg)
                        order_success = False

                if not order_success:
                    return

                # 2. 實體驗證成功後，才更新內部狀態
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
                msg = f"🎯 門神出擊！\n方向：放空 (SHORT)\n點位：{self.entry_price}\n停損：{self.stop_loss:.1f}\n目前的 ADX：{current_adx:.1f}\n目前的 Body Ratio：{ratio}%"
                
                if "Backtest" not in self.name and "Opt" not in self.name:
                    send_discord_message(msg)
                    
                    # Write to database (Trade Entry)
                    self.current_db_trade_id = log_trade_entry(
                        strategy_name=self.name,
                        side="Sell",
                        entry_price=float(self.entry_price),
                        entry_time=current_time
                    )

        # Exit / Risk Management Logic moved to `check_exit_signals`

    def check_exit_signals(self, current_price: float, current_time: datetime, current_atr: float = 20.0):
        """
        Tick-level Check: 每一筆報價進來時，立即計算停損與停利條件。
        不需等待 K 棒收尾。
        """
        if not self.is_long and not self.is_short:
            return
            
        if self.is_long:
            self.highest_price = max(self.highest_price, current_price)
            profit = current_price - self.entry_price
            
            # 保本機制：獲利達標後，停損「至少」要移到成本價
            if not self.break_even_triggered and profit >= self.be_threshold:
                # 只在停損小於成本時才上移成保本，避免降低已經拉上去的 Trailing Stop
                if self.stop_loss < self.entry_price:
                    self.stop_loss = self.entry_price
                self.break_even_triggered = True
                logging.info(f"[{self.name}] [RISK] 多單啟動保本 | 時間: {current_time} | 目前價格: {current_price} | 停損至少為成本: {self.entry_price}")
            
            # 移動停利機制 (Trailing ATR): 隨著最高價不斷創高，停損價跟著往上推
            # 只有在獲利超過保本點後才開始收緊移動停損 (因為前期的防守靠 2*ATR 固定)
            if self.break_even_triggered:
                potential_sl = self.highest_price - (self.trailing_atr_mult * current_atr)
                # 停損只能往上移，不能往下掉
                self.stop_loss = max(self.stop_loss, potential_sl)

            # Check Exit Conditions
            exit_reason = None
            
            # Hard Stop Loss / Trailing Stop Loss
            if current_price <= self.stop_loss:
                if current_price > self.entry_price:
                    exit_reason = "Trailing Stop (ATR)"
                elif self.break_even_triggered:
                    exit_reason = "Break Even"
                else:
                    exit_reason = "Stop Loss"
            
            if exit_reason:
                # 1. 嘗試發送實體平倉單
                order_success = True
                if "Backtest" not in self.name and "Opt" not in self.name:
                    if self.portfolio and self.contract:
                        try:
                            # 平倉，虛擬部位歸 0
                            order_success = self.portfolio.set_virtual_position(
                                strategy_name=self.name,
                                contract_symbol=self.contract.code,
                                new_position=0, 
                                contract_obj=self.contract,
                                average_cost=current_price
                            )
                            if order_success:
                                logging.info(f"[{self.name}] [ORDER] 虛擬賣單 (平多單) 紀錄與實體單確認成功。")
                        except Exception as e:
                            error_msg = f"❌ [{self.name}] [ERROR] 委派平倉單失敗: {e}"
                            logging.error(error_msg)
                            order_success = False
                            
                    if not order_success:
                        msg = f"⚠️ 【{self.name}】平多單委託被拒絕，系統將保留當前內部部位！\n出局原因：{exit_reason}\n價格：{current_price}"
                        send_discord_message(msg)
                        return

                # 2. 成功後才清理內部狀態與回報交易紀錄
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
                if self.current_db_trade_id != -1 and "Backtest" not in self.name and "Opt" not in self.name:
                    log_trade_exit(
                        trade_id=self.current_db_trade_id,
                        exit_price=float(current_price),
                        exit_time=current_time,
                        pnl_points=float(pnl),
                        exit_reason=exit_reason
                    )
                    self.current_db_trade_id = -1
                    
                    msg = f"💸 門神平倉出局！\n出局原因：{exit_reason}\n出場點位：{current_price}\n損益點數：{pnl:.1f}"
                    send_discord_message(msg)

        elif self.is_short:
            self.lowest_price = min(self.lowest_price, current_price)
            profit = self.entry_price - current_price # Short PnL is inverted
            
            # 保本機制：獲利達標後，停損「至少」要壓到成本價
            if not self.break_even_triggered and profit >= self.be_threshold:
                # 只在停損大於成本時才下壓成保本，避免影響已經被推下去的 Trailing Stop
                if self.stop_loss > self.entry_price:
                    self.stop_loss = self.entry_price
                self.break_even_triggered = True
                logging.info(f"[{self.name}] [RISK] 空單啟動保本 | 時間: {current_time} | 目前價格: {current_price} | 停損至少為成本: {self.entry_price}")
            
            # 移動停利機制 (Trailing ATR): 隨著最低價不斷創低，停損價跟著往下壓
            if self.break_even_triggered:
                potential_sl = self.lowest_price + (self.trailing_atr_mult * current_atr)
                # 停損只能往下壓，不能往上翹
                self.stop_loss = min(self.stop_loss, potential_sl)

            # Check Exit Conditions
            exit_reason = None
            
            # Hard Stop Loss / Trailing Stop Loss (Touched upper band)
            if current_price >= self.stop_loss:
                if current_price < self.entry_price:
                    exit_reason = "Trailing Stop (ATR)"
                elif self.break_even_triggered:
                    exit_reason = "Break Even"
                else:
                    exit_reason = "Stop Loss"
            
            if exit_reason:
                # 1. 嘗試發送實體平倉單
                order_success = True
                if "Backtest" not in self.name and "Opt" not in self.name:
                    if self.portfolio and self.contract:
                        try:
                            # 平倉，虛擬部位歸 0
                            order_success = self.portfolio.set_virtual_position(
                                strategy_name=self.name,
                                contract_symbol=self.contract.code,
                                new_position=0, 
                                contract_obj=self.contract,
                                average_cost=current_price
                            )
                            if order_success:
                                logging.info(f"[{self.name}] [ORDER] 虛擬買單 (平空單) 紀錄與實體單確認成功。")
                        except Exception as e:
                            error_msg = f"❌ [{self.name}] [ERROR] 委派平倉單失敗: {e}"
                            logging.error(error_msg)
                            order_success = False
                            
                    if not order_success:
                        msg = f"⚠️ 【{self.name}】平空單委託被拒絕，系統將保留當前內部部位！\n出局原因：{exit_reason}\n價格：{current_price}"
                        send_discord_message(msg)
                        return

                # 2. 成功後才清理內部狀態與回報交易紀錄
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
                if self.current_db_trade_id != -1 and "Backtest" not in self.name and "Opt" not in self.name:
                    log_trade_exit(
                        trade_id=self.current_db_trade_id,
                        exit_price=float(current_price),
                        exit_time=current_time,
                        pnl_points=float(pnl),
                        exit_reason=exit_reason
                    )
                    self.current_db_trade_id = -1
                    
                    msg = f"💸 門神平空單出局！\n出局原因：{exit_reason}\n出場點位：{current_price}\n損益點數：{pnl:.1f}"
                    send_discord_message(msg)
