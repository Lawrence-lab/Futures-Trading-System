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
from src.processors.kline_maker import KLineMaker
from src.line_notify import send_line_push_message
from src.db_logger import log_daily_equity


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

    print("初始化永豐期貨交易系統...")

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
        
        if not tmf_contracts:
            print("找不到 TMF 合約，請確認 API 連線或合約下載狀態。")
            sys.exit(1)
            
        target_contract = tmf_contracts[0]
        print(f"鎖定合約: {target_contract.name} ({target_contract.code})")

        # 定義行情儲存變數
        latest_quote = {}

        # KLineMaker 初始化 (60分K & 1D K線)
        maker_60m = KLineMaker(timeframe=60)
        maker_1d = KLineMaker(timeframe=1440)
        
        # 預載歷史 K 線以解決冷啟動 (Cold-Start) 指標 N/A 問題
        try:
            from datetime import timedelta
            import pandas as pd
            
            print("正在向永豐 API 調閱過去 14 天歷史 K 線以初始化指標...")
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            
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
                
                df_60m_hist = df_1m.resample('60min', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
                df_1d_hist = df_1m.resample('1D', label='left', closed='left').apply(ohlc_dict).dropna().reset_index()
                
                maker_60m.load_historical_dataframe(df_60m_hist)
                maker_1d.load_historical_dataframe(df_1d_hist)
                print(f"歷史資料載入完畢: 60M ({len(df_60m_hist)} 根), 1D ({len(df_1d_hist)} 根)")
            else:
                print("⚠️ 永豐 API 未回傳歷史資料，系統將空手啟動收集 K 線。")
        except Exception as e:
            print(f"⚠️ 載入歷史資料失敗: {e}")
        
        # 策略初始化
        from src.strategies.dual_logic import DualTimeframeStrategy
        strategies = [
            DualTimeframeStrategy(name="Gatekeeper-MXF-V1", api=trader.api, contract=target_contract),
            # Future strategies can be added here
        ]

        # 定義行情 Callback
        def on_quote(exchange, quote):
            # Shioaji quote object usually provides to_dict() or dict()
            tick_data = {}
            if hasattr(quote, 'to_dict'):
                tick_data = quote.to_dict()
            elif hasattr(quote, 'dict'):
                tick_data = quote.dict()
            else:
                # Fallback: try to act like a dict
                try:
                    tick_data = dict(quote)
                except:
                    # print(f"DEBUG: Unknown quote type: {type(quote)}")
                    return
            
            latest_quote.update(tick_data)
            
            # 更新 K 線
            # 判斷是否為 Tick 資料 (含有 close 和 volume)
            if 'close' in tick_data and 'volume' in tick_data:
                try:
                    # 同時餵給 60m 與 1d Maker
                    is_new_1d = maker_1d.update_with_tick(tick_data)
                    is_new_60m = maker_60m.update_with_tick(tick_data)
                    
                    # 當 60m K 線完成時，進行策略判斷
                    if is_new_60m:
                        df_60m = maker_60m.get_dataframe()
                        df_1d = maker_1d.get_dataframe()
                        
                        # 呼叫策略檢查訊號
                        for strategy in strategies:
                            strategy.check_signals(df_60m, df_1d)
                        
                except Exception as e:
                    print(f"Error in on_quote strategy logic: {e}")

        # 設定 Callback (Futures/Options)
        trader.api.quote.set_on_tick_fop_v1_callback(on_quote)
        trader.api.quote.set_on_bidask_fop_v1_callback(on_quote)

        # 訂閱行情
        print(f"訂閱 {target_contract.code} 即時行情...")
        trader.api.quote.subscribe(target_contract, quote_type=sj.constant.QuoteType.Tick)
        trader.api.quote.subscribe(target_contract, quote_type=sj.constant.QuoteType.BidAsk)

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
        
        from datetime import datetime
        import pytz
        tw_tz = pytz.timezone('Asia/Taipei')
        
        notified_open = False
        notified_close = False
        notified_night_open = False
        notified_night_close = False
        last_date = ""

        while True:
            try:
                # Use Asia/Taipei timezone explicitly to avoid UTC offset issues on cloud servers
                now_tw = datetime.now(tw_tz)
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
                    
                    # === LINE Notify ===
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
                        send_line_push_message(msg_open)
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
                        send_line_push_message(msg_close)
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
                        send_line_push_message(msg_night_open)
                        notified_night_open = True
                        
                    # 夜盤收盤 (05:00)
                    if current_hm == "05:01" and not notified_night_close:
                        # Optional: Add night session PnL summary here if needed
                        msg_night_close = f"💤 [夜盤] 任務結束。狀態更新完畢，準備迎接日盤。"
                        send_line_push_message(msg_night_close)
                        notified_night_close = True
                        
                    # ===================
                    
                    # Handle undefined variables conditionally
                    days_left = "N/A" 
                    trend_status = "N/A"
                    print(f"[{current_time}] [Monitor] Expiry: {days_left}d | 1D: {trend_status} | 60M Price: {price}")
                    
                    # Print status for each strategy
                    for strategy in strategies:
                        if strategy.is_long:
                            pos_status = "LONG"
                        elif getattr(strategy, 'is_short', False):
                            pos_status = "SHORT"
                        else:
                            pos_status = "EMPTY"
                            
                        print(f"   -> [{strategy.name}] Position: {pos_status} | Entry: {strategy.entry_price}")
                    
                else:
                    print(f"[{current_time}] 等待行情中...")
                
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
