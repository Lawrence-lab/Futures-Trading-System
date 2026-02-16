"""
主程式入口
"""
import sys
import os

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


def main():
    """系統主進入點"""
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

        # KLineMaker 初始化 (5分K & 60分K)
        maker_5m = KLineMaker(timeframe=5)
        maker_60m = KLineMaker(timeframe=60)
        
        # 策略初始化
        from src.strategies.dual_logic import DualTimeframeStrategy
        strategies = [
            DualTimeframeStrategy(name="Gatekeeper-MXF-V1"),
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
                    # 同時餵給 5m 與 60m Maker
                    is_new_60m = maker_60m.update_with_tick(tick_data)
                    is_new_5m = maker_5m.update_with_tick(tick_data)
                    
                    # 當 5m K 線完成時，進行策略判斷
                    if is_new_5m:
                        df_5m = maker_5m.get_dataframe()
                        df_60m = maker_60m.get_dataframe()
                        
                        # 呼叫策略檢查訊號
                        for strategy in strategies:
                            strategy.check_signals(df_5m, df_60m)
                        
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
        
        while True:
            try:
                current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                
                if latest_quote:
                    # 取得目前價格
                    price = latest_quote.get('close', latest_quote.get('price', 0))
                    
                    print(f"[{current_time}] [Monitor] Expiry: {days_left}d | 60M: {trend_status} | 5M Price: {price}")
                    
                    # Print status for each strategy
                    for strategy in strategies:
                        pos_status = "LONG" if strategy.is_long else "EMPTY"
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
