import logging
import pandas as pd
from datetime import datetime
from .indicators import calculate_sma, calculate_bias, calculate_atr
from src.line_notify import send_line_push_message
from src.db_logger import log_trade_entry, log_trade_exit

class GatekeeperBNFBStrategy:
    def __init__(self, name="Gatekeeper_BNF_B", portfolio=None, contract=None):
        """
        Gatekeeper BNF_B 摸底與摸頭逆勢策略
        核心邏輯：觀察 60MA 乖離率 (Bias) 與成交量，在大盤多頭極端負乖離時進場做多，空頭極端正乖離做空。
        部位管理：進場 1 口，反彈/回落 80 點啟動保本與移動停利，剩餘部位用 2*ATR 移動停利，或觸碰 60MA 全數平倉。
        """
        self.name = name
        self.portfolio = portfolio
        self.contract = contract
        
        # 1. 查詢庫存與還原狀態
        initial_pos = 0
        if self.portfolio and self.contract:
            initial_pos = self.portfolio.get_virtual_position(self.name, self.contract.code)

        self.is_long = initial_pos > 0
        self.is_short = initial_pos < 0
        self.current_position_size = abs(initial_pos)  # 預期是 1 或是 0
        
        # 狀態紀錄
        self.entry_price = 0.0
        self.entry_time = None
        self.highest_price = 0.0
        self.lowest_price = 0.0 # 用於作空
        self.stop_loss = 0.0
        self.trailing_active = False
        
        # 每日單次進場限制紀錄
        self.last_entry_date = None
        
        self.trades = []
        self.current_db_trade_id = -1
        
        # 參數設定
        self.sma_period = 60
        self.bias_threshold = -1.5 # 乖離率 % (多方 < -1.5, 空方 > +1.5)
        self.volume_ma_period = 20
        self.volume_spike_ratio = 2.0 # Optimal parameters found via backtest sweeping
        
        self.fixed_sl_points = 100.0   # 固定停損 100 點
        self.partial_tp_points = 80.0  # +80 點啟動保本與移動停利
        self.trailing_atr_mult = 2.0   # 2xATR 移動停利
        self.time_stop_days = 3        # 持倉 3 天時間停損

    def check_signals(self, df_60m, df_1d=None, precalc_bullish_1d=None, precalc_signal_60m=None):
        if df_60m.empty: return
        
        current_bar = df_60m.iloc[-1]
        current_price = float(current_bar['close'])
        current_time = current_bar.get('datetime', datetime.now())
        current_volume = float(current_bar.get('volume', 0))
        
        # --- 指標計算 ---
        # 取得 60MA 與 Bias
        sma_series = calculate_sma(df_60m, period=self.sma_period)
        bias_series = calculate_bias(df_60m, sma_col=None, period=self.sma_period)
        
        if sma_series is None or pd.isna(sma_series.iloc[-1]):
            return # 指標不足不動作
            
        current_sma = sma_series.iloc[-1]
        current_bias = bias_series.iloc[-1]
        
        # 取得 Volume MA
        vol_ma_series = df_60m['volume'].rolling(window=self.volume_ma_period).mean()
        if vol_ma_series.empty or pd.isna(vol_ma_series.iloc[-1]): return
        current_vol_ma = vol_ma_series.iloc[-1]
        
        # 取得 ATR
        atr_series = calculate_atr(df_60m, period=14)
        current_atr = atr_series.iloc[-1] if not atr_series.empty else 20.0
        
        # 取得日期用於「單日進場限制」與「時間停損」
        current_date_str = pd.to_datetime(current_time).strftime("%Y-%m-%d")

        # 判定大趨勢 (若 precalc_bullish_1d 未提供，預設偏向做多，相容舊邏輯)
        is_bull_trend = precalc_bullish_1d if precalc_bullish_1d is not None else True

        # ====================
        # 進場邏輯 (Entry)
        # ====================
        if not self.is_long and not self.is_short:
            # 條件 1：單日只能進場一次
            if self.last_entry_date == current_date_str:
                return
                
            # 條件 3：成交量放大 (超過 20MA 的 volume_spike_ratio 倍)
            cond_vol = current_volume > (current_vol_ma * self.volume_spike_ratio)
            
            if cond_vol:
                if is_bull_trend:
                    # 多頭趨勢 -> 只做多 (摸底)
                    # 條件 2：Bias < 閾值
                    cond_bias = current_bias < self.bias_threshold
                    
                    if cond_bias:
                        self.is_long = True
                        self.current_position_size = 1 # 固定進場 1 口
                        self.entry_price = current_price
                        self.entry_time = pd.to_datetime(current_time)
                        self.highest_price = current_price
                        
                        # 初始防護停損：-100 點
                        self.stop_loss = current_price - self.fixed_sl_points
                        self.trailing_active = False
                        self.last_entry_date = current_date_str
                        
                        log_msg = f"[{self.name}] [SIGNAL] 逆勢摸底多單進場 (1口) | 價格: {self.entry_price} | Bias: {current_bias:.2f}% | 停損: {self.stop_loss}"
                        logging.info(log_msg)
                        
                        if "Backtest" not in self.name:
                            send_line_push_message(f"🚨 【{self.name}】逆勢摸底啟動！\n方向：做多 1 口\n點位：{self.entry_price}\n乖離率：{current_bias:.2f}%\n停損：{self.stop_loss}")
                            
                            self.current_db_trade_id = log_trade_entry(
                                strategy_name=self.name,
                                side="Buy",
                                entry_price=float(self.entry_price),
                                entry_time=current_time
                            )
                            
                            if self.portfolio and self.contract:
                                try:
                                    self.portfolio.set_virtual_position(
                                        strategy_name=self.name,
                                        contract_symbol=self.contract.code,
                                        new_position=1,
                                        contract_obj=self.contract,
                                        average_cost=self.entry_price
                                    )
                                except Exception as e:
                                    logging.error(f"❌ [{self.name}] 委派買單失敗: {e}")
                else:
                    # 空頭趨勢 -> 只做空 (摸頭)
                    # 條件 2：Bias > |閾值|
                    cond_bias = current_bias > abs(self.bias_threshold)
                    
                    if cond_bias:
                        self.is_short = True
                        self.current_position_size = 1 # 固定進場 1 口
                        self.entry_price = current_price
                        self.entry_time = pd.to_datetime(current_time)
                        self.lowest_price = current_price
                        
                        # 初始防護停損：+100 點
                        self.stop_loss = current_price + self.fixed_sl_points
                        self.trailing_active = False
                        self.last_entry_date = current_date_str
                        
                        log_msg = f"[{self.name}] [SIGNAL] 逆勢摸頭空單進場 (1口) | 價格: {self.entry_price} | Bias: {current_bias:.2f}% | 停損: {self.stop_loss}"
                        logging.info(log_msg)
                        
                        if "Backtest" not in self.name:
                            send_line_push_message(f"🚨 【{self.name}】逆勢摸頭啟動！\n方向：做空 1 口\n點位：{self.entry_price}\n乖離率：{current_bias:.2f}%\n停損：{self.stop_loss}")
                            
                            self.current_db_trade_id = log_trade_entry(
                                strategy_name=self.name,
                                side="Sell",
                                entry_price=float(self.entry_price),
                                entry_time=current_time
                            )
                            
                            if self.portfolio and self.contract:
                                try:
                                    self.portfolio.set_virtual_position(
                                        strategy_name=self.name,
                                        contract_symbol=self.contract.code,
                                        new_position=-1,
                                        contract_obj=self.contract,
                                        average_cost=self.entry_price
                                    )
                                except Exception as e:
                                    logging.error(f"❌ [{self.name}] 委派賣庫存單失敗: {e}")

        # ====================
        # 出場與風控邏輯 (Exit)
        # ====================
        elif self.is_long:
            self.highest_price = max(self.highest_price, current_price)
            profit = current_price - self.entry_price
            
            exit_reason = None
            
            # 1. 達標啟動保本與移動停利
            if not self.trailing_active and profit >= self.partial_tp_points:
                self.trailing_active = True
                
                # 將停損立刻拉升，改用 Trailing Stop (High - 2*ATR)
                # 並確保停損絕對不會低於成本（保本）
                new_sl = max(self.entry_price, self.highest_price - (self.trailing_atr_mult * current_atr))
                self.stop_loss = new_sl
                
                msg = f"🎯 [{self.name}] 達到 {self.partial_tp_points} 點目標！啟動多單保本與移動停利。\n目前價格: {current_price}\n停損移至: {self.stop_loss:.1f}"
                logging.info(msg)
                if "Backtest" not in self.name:
                    send_line_push_message(msg)
            
            # --- 檢查全數平倉條件 ---
            # 更新剩餘部位的移動停利軌道
            if self.trailing_active:
                potential_sl = self.highest_price - (self.trailing_atr_mult * current_atr)
                self.stop_loss = max(self.stop_loss, potential_sl)

            # A. 價格觸碰/跌破停損線
            if current_price <= self.stop_loss:
                exit_reason = "Stop Loss/Trailing Stop"
                
            # B. 均線修復：價格碰觸或穿越 60MA
            elif current_price >= current_sma:
                exit_reason = "Mean Reversion (Touch 60MA)"
                
            # C. 時間停損：持倉超過 X 個交易日未達標
            elif (pd.to_datetime(current_time) - self.entry_time).days >= self.time_stop_days:
                exit_reason = f"Time Stop (Max {self.time_stop_days} Days)"
                
            if exit_reason:
                final_pnl = current_price - self.entry_price
                logging.info(f"[{self.name}] [EXIT] {exit_reason} (Long) | 出場: {current_price} | 損益: {final_pnl}")
                self._execute_exit(current_time, current_price, final_pnl, exit_reason)

        elif self.is_short:
            self.lowest_price = min(self.lowest_price, current_price)
            profit = self.entry_price - current_price # 做空獲利 = 進場價 - 當前價
            
            exit_reason = None
            
            # 1. 達標啟動保本與移動停利
            if not self.trailing_active and profit >= self.partial_tp_points:
                self.trailing_active = True
                
                # 將停損立刻下壓，改用 Trailing Stop (Low + 2*ATR)
                # 並確保停損絕對不會高於成本（保本）
                new_sl = min(self.entry_price, self.lowest_price + (self.trailing_atr_mult * current_atr))
                self.stop_loss = new_sl
                
                msg = f"🎯 [{self.name}] 達到 {self.partial_tp_points} 點目標！啟動空單保本與移動停利。\n目前價格: {current_price}\n停損移至: {self.stop_loss:.1f}"
                logging.info(msg)
                if "Backtest" not in self.name:
                    send_line_push_message(msg)
            
            # --- 檢查全數平倉條件 ---
            # 更新剩餘部位的移動停利軌道
            if self.trailing_active:
                potential_sl = self.lowest_price + (self.trailing_atr_mult * current_atr)
                self.stop_loss = min(self.stop_loss, potential_sl)

            # A. 價格觸碰/突破停損線
            if current_price >= self.stop_loss:
                exit_reason = "Stop Loss/Trailing Stop"
                
            # B. 均線修復：價格碰觸或穿越回 60MA
            elif current_price <= current_sma:
                exit_reason = "Mean Reversion (Touch 60MA)"
                
            # C. 時間停損：持倉超過 X 個交易日未達標
            elif (pd.to_datetime(current_time) - self.entry_time).days >= self.time_stop_days:
                exit_reason = f"Time Stop (Max {self.time_stop_days} Days)"
                
            if exit_reason:
                final_pnl = self.entry_price - current_price
                logging.info(f"[{self.name}] [EXIT] {exit_reason} (Short) | 出場: {current_price} | 損益: {final_pnl}")
                self._execute_exit(current_time, current_price, final_pnl, exit_reason)

    def _execute_exit(self, current_time, current_price, final_pnl, exit_reason):
        """共用的出場結算腳本"""
        direction = "Long" if self.is_long else "Short"
        
        self.is_long = False
        self.is_short = False
        self.current_position_size = 0
        
        self.trades.append({
            'strategy': self.name,
            'direction': direction,
            'entry_time': self.entry_time,
            'exit_time': current_time,
            'entry_price': self.entry_price,
            'exit_price': current_price,
            'pnl': final_pnl,
            'reason': exit_reason
        })
        
        if "Backtest" not in self.name:
            if self.current_db_trade_id != -1:
                log_trade_exit(
                    trade_id=self.current_db_trade_id,
                    exit_price=float(current_price),
                    exit_time=current_time,
                    pnl_points=float(final_pnl),
                    exit_reason=exit_reason
                )
                self.current_db_trade_id = -1
                
            if self.portfolio and self.contract:
                try:
                    self.portfolio.set_virtual_position(
                        strategy_name=self.name,
                        contract_symbol=self.contract.code,
                        new_position=0, 
                        contract_obj=self.contract,
                        average_cost=0.0
                    )
                    action_str = "全數平倉" if direction == "Long" else "空單全數回補"
                    send_line_push_message(f"💸 【{self.name}】{action_str}結案！\n原因：{exit_reason}\n出場點位：{current_price}\n此口損益結算：{final_pnl:.1f}")
                except Exception as e:
                    logging.error(f"❌ [{self.name}] 委派平倉單失敗: {e}")
