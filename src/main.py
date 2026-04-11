"""
主程式入口
"""
import sys
import os

# Ensure UTF-8 output on Windows
if sys.stdout.encoding.lower() != 'utf-8':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

# Add project root to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check for CERT_BASE64 and restore certificate
if "CERT_BASE64" in os.environ:
    import base64
    try:
        cert_b64 = os.environ["CERT_BASE64"]
        
        # Use system temp directory for cross-platform compatibility (Windows/Linux)
        import tempfile
        temp_dir = tempfile.gettempdir()
        
        filename = "trading_cert.pfx"
        # If user specified a specific filename in CERT_PATH, try to preserve it, but move to tmp
        if "CERT_PATH" in os.environ:
             filename = os.path.basename(os.environ["CERT_PATH"])
             
        cert_path = os.path.abspath(os.path.join(temp_dir, filename))
        
        print(f"Decoding CERT_BASE64 to {cert_path}...", flush=True)
        with open(cert_path, "wb") as f:
            f.write(base64.b64decode(cert_b64))
        
        # Verify file size
        if os.path.exists(cert_path):
             size = os.path.getsize(cert_path)
             print(f"Certificate restored successfully. Size: {size} bytes", flush=True)
        else:
             print("Error: Certificate file not found after writing.", flush=True)

        # FORCE update env var so config.py picks up the correct path
        os.environ["CERT_PATH"] = cert_path
        print(f"Updated CERT_PATH to {cert_path}", flush=True)
            
    except Exception as e:
        print(f"Warning: Failed to decode CERT_BASE64: {e}", flush=True)

import time
from datetime import datetime
import shioaji as sj
from src.connection import Trader
import kgisuperpy as kgi
from dotenv import load_dotenv
from src.processors.kline_maker import KLineMaker
from src.discord_notify import send_discord_message
from src.db_logger import log_daily_equity
from src.portfolio_manager import PortfolioManager


def is_market_closed(dt: datetime) -> bool:
    """
    判斷是否為週末休市時間:
    週六 05:05 後開始休市，直到週一 08:44 開盤前 (皆為台灣時間)。
    """
    weekday = dt.weekday()
    hm = dt.strftime("%H:%M")
    
    if weekday == 5 and hm >= "05:05":
        return True
    if weekday == 6:
        return True
    if weekday == 0 and hm < "08:45":
        return True
        
    return False

def is_pre_market(dt: datetime) -> bool:
    """
    判斷是否為盤前試撮時間 (不處理該時段的模擬撮合報價):
    日盤: 08:30:00 ~ 08:44:59
    夜盤: 14:50:00 ~ 14:59:59
    """
    hm = dt.strftime("%H:%M:%S")
    
    if "08:30:00" <= hm <= "08:44:59":
        return True
    if "14:50:00" <= hm <= "14:59:59":
        return True
        
    return False

def main():
    """系統主進入點"""
    import subprocess
    import sys
    import os
    
    port = os.environ.get("PORT", "8080")
    print(f"🚀 [main.py] 啟動 Streamlit 儀表板 (Port: {port})...", flush=True)
    try:
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "app.py", 
             "--server.port", port, 
             "--server.address", "0.0.0.0", 
             "--server.headless", "true", 
             "--server.enableCORS", "false"]
        )
    except Exception as e:
        print(f"⚠️ 無法啟動 Streamlit: {e}", flush=True)

    print("初始化 KGI 報價系統...")
    load_dotenv()
    kgi_id = os.environ.get("KGI_ID")
    kgi_pwd = os.environ.get("KGI_PASSWORD")
    if not kgi_id or not kgi_pwd:
        print("缺少 KGI_ID 或 KGI_PASSWORD，請確認 .env 設定。")
        sys.exit(1)
        
    # --- KGI 憑證路徑 Monkey Patch ---
    # 藉由攔截底層 TradeComAPI.Login，在實際呼叫 C++ Login 之前塞入憑證設定
    from kgisuperpy.pushClient.pyTradeCom import TradeComAPI
    if not hasattr(TradeComAPI, '_Login_original'):
        TradeComAPI._Login_original = TradeComAPI.Login

    def kgi_login_with_cert(self, user_id, password):
        cert_path = os.environ.get("CERT_PATH")
        cert_pass = os.environ.get("CERT_PASS")
        if cert_path and cert_pass:
            print(f"🔧 [KGI] 偵測到環境變數 CERT_PATH，套用自訂憑證: {cert_path}")
            self.SetCA_PFX(cert_path)
            self.SetCA_PW(cert_pass)
        self._Login_original(user_id, password)

    TradeComAPI.Login = kgi_login_with_cert
    # --------------------------------

    try:
        kgi_api = kgi.login(
            person_id=kgi_id, 
            person_pwd=kgi_pwd, 
            simulation=False
        )
        time.sleep(3)
        print("凱基登入完成。")
    except Exception as e:
        print(f"凱基登入失敗: {e}")
        sys.exit(1)

    print("初始化永豐期貨交易系統 (下單用)...")

    try:
        trader = Trader()
        accounts = trader.login()
        print(f"登入成功。可用帳戶數: {len(accounts)}")
        for acc in accounts:
            print(f" - {acc}")
        
        # 尋找微型台指期 (TMF) 近月合約
        print("正在尋找微型台指期 (TMF) 合約...")
        # 這裡假設 TMF 在 Futures 下，且列表按到期日排序，第一個即為近月
        # 注意: 實際代碼可能需要根據 Shioaji 版本調整查找方式
        tmf_contracts = [
            c for c in trader.api.Contracts.Futures.TMF 
            if c.code[-2:] not in ["R1", "R2"] # 排除跨月價差單
        ]
        
        import pytz
        tw_tz = pytz.timezone('Asia/Taipei')
        now_tw = datetime.now(tw_tz)
        current_date_str = now_tw.strftime("%Y/%m/%d")
        current_hm_str = now_tw.strftime("%H:%M")

        valid_contracts = []
        for c in tmf_contracts:
            if hasattr(c, 'delivery_date') and getattr(c, 'delivery_date'):
                if c.delivery_date < current_date_str:
                    continue
                if c.delivery_date == current_date_str and current_hm_str >= "13:30":
                    continue
            valid_contracts.append(c)

        if not valid_contracts:
            print("找不到有效的 TMF 合約 (可能全部已到期)，請確認。")
            sys.exit(1)
            
        # 確保照到期日排序
        valid_contracts.sort(key=lambda x: getattr(x, 'delivery_date', '9999/99/99'))
        target_contract = valid_contracts[0]
        print(f"鎖定合約: {target_contract.name} ({target_contract.code})")

        # 定義行情儲存變數
        latest_quote = {}

        # KLineMaker 初始化 (5分K, 60分K & 1D K線)
        maker_5m = KLineMaker(timeframe=5)
        maker_60m = KLineMaker(timeframe=60)
        maker_1d = KLineMaker(timeframe=1440)
        
        # 預載歷史 K 線以解決冷啟動 (Cold-Start) 指標 N/A 問題
        try:
            from datetime import timedelta
            import pandas as pd
            
            print("正在向永豐 API 調閱過去 30 天歷史 K 線以初始化指標...")
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            
            kbars = trader.api.kbars(contract=target_contract, start=start_date, end=end_date)
            
            df_1m = pd.DataFrame({
                'datetime': pd.to_datetime(kbars.ts),
                'open': kbars.Open,
                'high': kbars.High,
                'low': kbars.Low,
                'close': kbars.Close,
                'volume': kbars.Volume
            })
            
            if not df_1m.empty:
                df_1m.set_index('datetime', inplace=True)
                ohlc_dict = {
                    'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
                }
                
                df_5m_hist = df_1m.resample('5min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
                df_60m_hist = df_1m.resample('60min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
                df_1d_hist = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
                
                maker_5m.load_historical_dataframe(df_5m_hist)
                maker_60m.load_historical_dataframe(df_60m_hist)
                maker_1d.load_historical_dataframe(df_1d_hist)
                print(f"歷史資料載入完畢: 5M ({len(df_5m_hist)} 根), 60M ({len(df_60m_hist)} 根), 1D ({len(df_1d_hist)} 根)")
            else:
                print("⚠️ 永豐 API 未回傳歷史資料，系統將空手啟動收集 K 線。")
        except Exception as e:
            print(f"⚠️ 載入歷史資料失敗: {e}")
        
        # 策略初始化
        from src.strategies.dual_logic import DualTimeframeStrategy
        from src.strategies.gatekeeper_bnf_b_5m import GatekeeperBNFB5mStrategy
        from src.strategies.notify_60ma import Notify60maStrategy
        
        # 建立投資組合管理員
        portfolio = PortfolioManager(api=trader.api)
        
        strategies_60m = [
            DualTimeframeStrategy(name="Gatekeeper-MXF-V1", portfolio=portfolio, contract=target_contract),
            Notify60maStrategy(name="Notify_60MA_Crossover", portfolio=portfolio, contract=target_contract),
        ]
        
        strategies_5m = [
            GatekeeperBNFB5mStrategy(name="Gatekeeper-BNF-B", portfolio=portfolio, contract=target_contract),
        ]
        
        strategies = strategies_60m + strategies_5m

        # 定義行情 Callback (KGI 來源)
        def on_kgi_tick(tick):
            import pytz
            tw_tz = pytz.timezone('Asia/Taipei')
            now_tw = datetime.now(tw_tz)
            
            # 週末休市不處理任何行情
            if is_market_closed(now_tw):
                return
                
            # 盤前試撮時間不處理任何模擬報價，避免導致指標失真或誤觸發進出訊號
            if is_pre_market(now_tw):
                return
                
            tick_data = {}
            try:
                dt_str = str(getattr(tick, 'datetime', ''))
                if len(dt_str) >= 14:
                    dt_obj = datetime.strptime(dt_str[:14], "%Y%m%d%H%M%S")
                    dt_obj = tw_tz.localize(dt_obj)
                    tick_data['datetime'] = dt_obj
                else:
                    tick_data['datetime'] = now_tw
                    
                tick_data['close'] = float(getattr(tick, 'close', 0.0))
                tick_data['volume'] = int(getattr(tick, 'volume', 0))
                
                # Check for bid/ask properties
                bids = getattr(tick, 'bid_price', [])
                asks = getattr(tick, 'ask_price', [])
                if bids and asks and len(bids) > 0 and len(asks) > 0:
                    tick_data['close'] = (float(bids[0]) + float(asks[0])) / 2.0

            except Exception as e:
                # print(f"Error parsing KGI tick: {e}")
                return
                
            if tick_data.get('close', 0) <= 0:
                return

            latest_quote.update(tick_data)
            
            # === TICK-LEVEL EXIT CHECK ===
            # 每當有新的報價進來（包含現價），立刻檢查是否觸發停損/移動停利
            if 'close' in tick_data:
                tick_price = float(tick_data['close'])
                
                # Check DualTimeframe (60m) Strategies
                for strategy in strategies_60m:
                    if strategy.is_long or strategy.is_short:
                        # 嘗試取得最新的 ATR，若無則用預設值 20.0
                        df_60m = maker_60m.get_dataframe()
                        current_atr = 20.0
                        if not df_60m.empty and 'atr' in df_60m.columns:
                            current_atr = df_60m.iloc[-1]['atr']
                        
                        strategy.check_exit_signals(tick_price, now_tw, current_atr)

                # Check GatekeeperBNFB (5m) Strategies
                for strategy in strategies_5m:
                    if strategy.is_long or strategy.is_short:
                        df_5m = maker_5m.get_dataframe()
                        current_sma = 0.0
                        current_atr = 20.0
                        
                        # 從最新的 K棒 DataFrame 中計算出最新的 SMA 與 ATR
                        if not df_5m.empty:
                            from src.strategies.indicators import calculate_sma, calculate_atr
                            sma_series = calculate_sma(df_5m, period=strategy.sma_period)
                            if sma_series is not None and not sma_series.empty:
                                current_sma = float(sma_series.iloc[-1])
                                
                            atr_series = calculate_atr(df_5m, period=14)
                            if atr_series is not None and not atr_series.empty:
                                current_atr = float(atr_series.iloc[-1])

                        # 只有當我們有有效的 SMA 基準點時才執行檢查 (避免一開始沒資料時誤動作)
                        if current_sma > 0:
                            strategy.check_exit_signals(tick_price, now_tw, current_sma, current_atr)

            # 更新 K 線
            if 'close' in tick_data and 'volume' in tick_data:
                try:
                    # 同時餵給 5m, 60m 與 1d Maker
                    is_new_1d = maker_1d.update_with_tick(tick_data)
                    is_new_60m = maker_60m.update_with_tick(tick_data)
                    is_new_5m = maker_5m.update_with_tick(tick_data)
                    
                    df_1d = maker_1d.get_dataframe()
                    
                    if is_new_5m:
                        df_5m = maker_5m.get_dataframe()
                        for strategy in strategies_5m:
                            strategy.check_signals(df_5m, df_1d)
                            
                    # 當 60m K 線完成時，進行策略判斷
                    if is_new_60m:
                        df_60m = maker_60m.get_dataframe()
                        
                        # 呼叫策略檢查訊號
                        for strategy in strategies_60m:
                            strategy.check_signals(df_60m, df_1d)
                        
                except Exception as e:
                    print(f"Error in on_quote strategy logic: {e}")

        # 設定 Callback (KGI 來源)
        try:
            kgi_api.FutQuote.set_cb_tick(on_kgi_tick)
            kgi_api.FutQuote.set_cb_bidask(on_kgi_tick)
        except Exception as e:
            print(f"⚠️ 設定 KGI callback 失敗: {e}", flush=True)

        kgi_symbol = os.environ.get("KGI_QUOTE_SYMBOL", "TXF")
        print(f"訂閱 KGI {kgi_symbol} 即時行情 (報價)...", flush=True)
        try:
            kgi_api.FutQuote.subscribe_tick(kgi_symbol)
            kgi_api.FutQuote.subscribe_bidask(kgi_symbol)
        except Exception as e:
            print(f"⚠️ KGI 訂閱失敗: {e}", flush=True)

        # Keep the program running and print quote every 1 minute
        print("系統運行中，按 Ctrl+C 停止...")
        print("開始接收行情 (每 1 分鐘更新監控日誌)...")
        print("-" * 50)
        
        # --- 初始化取得最新權益數 ---
        try:
            acc = trader.api.futopt_account
            if acc:
                margin_res = trader.api.margin(acc)
                if margin_res:
                    margin_data = margin_res[0] if isinstance(margin_res, list) and len(margin_res) > 0 else margin_res
                    t_equity = getattr(margin_data, 'equity', 0.0) 
                    if not t_equity and isinstance(margin_data, dict):
                        t_equity = margin_data.get('equity', 0.0)
                    a_margin = getattr(margin_data, 'available_margin', 0.0)
                    if not a_margin and isinstance(margin_data, dict):
                        a_margin = margin_data.get('available_margin', 0.0)
                    init_date = time.strftime("%Y-%m-%d", time.localtime())
                    log_daily_equity(init_date, total_equity=float(t_equity), available_margin=float(a_margin))
                    print(f"✅ 已將初始權益數 ({t_equity}) 記錄至資料庫。")
        except Exception as e:
            print(f"⚠️ 取得初始權益數或寫入資料庫失敗: {e}")
        # -----------------------------
        import pytz
        tw_tz = pytz.timezone('Asia/Taipei')
        
        notified_open = False
        notified_close = False
        notified_night_open = False
        notified_night_close = False
        last_date = ""
        last_reconciliation_time = 0
        last_weekend_log_time = 0

        while True:
            try:
                # Use Asia/Taipei timezone explicitly to avoid UTC offset issues on cloud servers
                now_tw = datetime.now(tw_tz)
                
                # 判斷是否為週末休市 (如果休市，則跳過主要監測迴圈並定時輸出休市日誌)
                if is_market_closed(now_tw):
                    current_unix_time = time.time()
                    if current_unix_time - last_weekend_log_time >= 1800: # 每 30 分鐘印一次
                        print(f"[{now_tw.strftime('%Y-%m-%d %H:%M:%S')}] 週末休市中，系統處於待命狀態...")
                        last_weekend_log_time = current_unix_time
                    time.sleep(60)
                    continue
                    
                current_time = now_tw.strftime("%Y-%m-%d %H:%M:%S")
                current_date = now_tw.strftime("%Y-%m-%d")
                current_hm = now_tw.strftime("%H:%M")
                
                if current_date != last_date:
                    notified_open = False
                    notified_close = False
                    notified_night_open = False
                    notified_night_close = False
                    last_date = current_date
                
                if latest_quote:
                    # 取得目前價格
                    price = latest_quote.get('close', latest_quote.get('price', 0))
                    
                    # === Discord Notify ===
                    # 日盤開盤 (08:45)
                    if current_hm == "08:46" and not notified_open:
                        df_5m = maker_5m.get_dataframe()
                        atr_val = "N/A"
                        if not df_5m.empty and 'atr' in df_5m.columns:
                            atr_val = f"{df_5m.iloc[-1]['atr']:.2f}"
                        elif not df_5m.empty:
                            from src.strategies.indicators import calculate_atr
                            atr_series = calculate_atr(df_5m, period=10)
                            if not atr_series.empty:
                                atr_val = f"{atr_series.iloc[-1]:.2f}"
                                
                        msg_open = f"☀️ [日盤] 門神已就位！今日開盤價：{price}，ATR 波動率：{atr_val}，Body Filter 閾值已鎖定。"
                        send_discord_message(msg_open)
                        notified_open = True
                    
                    # 日盤收盤 (13:45)
                    if current_hm == "13:46" and not notified_close:
                        pos_status_list = []
                        total_pnl = 0.0
                        for strategy in strategies:
                            status = "持倉中(多)" if strategy.is_long else "空手"
                            pos_status_list.append(f"{strategy.name}: {status}")
                            
                            # 計算本日已實現損益 (包含可能未平倉的損益)
                            today_trades = [t for t in strategy.trades if isinstance(t['exit_time'], datetime) and t['exit_time'].strftime("%Y-%m-%d") == current_date]
                            for t in today_trades:
                                total_pnl += t['pnl']
                                
                            if strategy.is_long:
                                floating_pnl = price - strategy.entry_price
                                total_pnl += floating_pnl
                                pos_status_list[-1] += f" (未平倉損益: {floating_pnl:.1f})"
                                
                        pos_status_str = " | ".join(pos_status_list) if pos_status_list else "無"
                        msg_close = f"📊 [日盤] 今日任務結束。\n狀態：{pos_status_str}\n本日盈虧：{total_pnl:.1f} 點。"
                        send_discord_message(msg_close)
                        notified_close = True
                        
                        # --- Log Daily Equity to PostgreSQL ---
                        try:
                            acc = trader.api.futopt_account
                            if acc:
                                margin_res = trader.api.margin(acc)
                                if margin_res:
                                    margin_data = margin_res[0] if isinstance(margin_res, list) and len(margin_res) > 0 else margin_res
                                    t_equity = getattr(margin_data, 'equity', 0.0) 
                                    if not t_equity and isinstance(margin_data, dict):
                                        t_equity = margin_data.get('equity', 0.0)
                                    a_margin = getattr(margin_data, 'available_margin', 0.0)
                                    if not a_margin and isinstance(margin_data, dict):
                                        a_margin = margin_data.get('available_margin', 0.0)
                                        
                                    log_daily_equity(current_date, total_equity=float(t_equity), available_margin=float(a_margin))
                                    print(f"[{current_time}] 已將本日權益數 ({t_equity}) 記錄至資料庫。")
                        except Exception as e:
                            print(f"取得權益數或寫入資料庫失敗: {e}")
                        # --------------------------------------
                    
                    # 夜盤開盤 (15:00)
                    if current_hm == "15:01" and not notified_night_open:
                        msg_night_open = f"🌙 [夜盤] 門神已就位！夜盤開盤價：{price}，系統持續監控中。"
                        send_discord_message(msg_night_open)
                        notified_night_open = True
                        
                    # 夜盤收盤 (05:00)
                    if current_hm == "05:01" and not notified_night_close:
                        # Optional: Add night session PnL summary here if needed
                        msg_night_close = f"💤 [夜盤] 任務結束。狀態更新完畢，準備迎接日盤。"
                        send_discord_message(msg_night_close)
                        notified_night_close = True
                        
                    # Dynamic Status Dashboard Lookups
                    days_left = "N/A"
                    if getattr(target_contract, 'delivery_date', None):
                        try:
                            # Usually format 'YYYY/MM/DD' or 'YYYYMMDD'
                            delivery_str = str(target_contract.delivery_date).replace('/', '')
                            if len(delivery_str) >= 8:
                                del_date = datetime.strptime(delivery_str[:8], "%Y%m%d")
                                days_left = (del_date - datetime.now()).days
                        except:
                            pass
                            
                    trend_status = "N/A"
                    try:
                        df_1d = maker_1d.get_dataframe()
                        if not df_1d.empty and len(df_1d) >= 10:
                            from src.strategies.indicators import calculate_supertrend
                            is_bullish, _ = calculate_supertrend(df_1d)
                            trend_status = "BULL (多)" if is_bullish else "BEAR (空)"
                    except Exception as e:
                        import traceback
                        print(f"Failed to fetch 1D trend: {e}")
                        traceback.print_exc()

                    print(f"[{current_time}] [Monitor] Expiry: {days_left}d | 1D: {trend_status} | Current Price: {price}")
                    
                    # Print status for each strategy
                    for strategy in strategies:
                        if strategy.is_long:
                            pos_status = "LONG"
                        elif getattr(strategy, 'is_short', False):
                            pos_status = "SHORT"
                        else:
                            pos_status = "EMPTY"
                            
                        entry_p = getattr(strategy, 'entry_price', 0.0)
                        print(f"   -> [{strategy.name}] Position: {pos_status} | Entry: {entry_p}")
                    
                else:
                    # Dashboard Output (No Tick State)
                    tw_tz_now = datetime.now(tw_tz)
                    current_time_str = tw_tz_now.strftime('%Y-%m-%d %H:%M:%S')
                    trend_status = "N/A"
                    try:
                        df_1d = maker_1d.get_dataframe()
                        if not df_1d.empty and len(df_1d) >= 10:
                            from src.strategies.indicators import calculate_supertrend
                            is_bullish, _ = calculate_supertrend(df_1d)
                            trend_status = "BULL (多)" if is_bullish else "BEAR (空)"
                    except Exception as e:
                        import traceback
                        print(f"Failed to fetch 1D trend (No Tick State): {e}")
                        traceback.print_exc()

                    print(f"[{current_time_str}] 等待行情中... | 1D: {trend_status}")
                
                # --- Periodic Reconciliation (每 5 分鐘執行一次對帳) ---
                current_unix_time = time.time()
                if current_unix_time - last_reconciliation_time >= 300:
                    portfolio.reconcile_positions(target_contract.code)
                    last_reconciliation_time = current_unix_time

                time.sleep(60)
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(60)

    except KeyboardInterrupt:
        print("\n系統正在停止...")
        try:
            if 'trader' in locals() and trader.api:
                print("正在登出券商 API...")
                trader.api.logout()
                print("已登出")
        except Exception as e:
            print(f"登出時發生錯誤: {e}")
        
        print("系統已安全退出")
        sys.exit(0)

    except Exception as e:
        print(f"系統執行發生錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
