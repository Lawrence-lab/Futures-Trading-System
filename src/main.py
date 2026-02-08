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
        # Determine strict path or use a default
        cert_path = "/app/certs/trading_cert.pfx"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(cert_path), exist_ok=True)
        
        print(f"Decoding CERT_BASE64 to {cert_path}...")
        with open(cert_path, "wb") as f:
            f.write(base64.b64decode(cert_b64))
        print("Certificate restored successfully.")
        
        # Auto-configure CERT_PATH if not set
        if "CERT_PATH" not in os.environ:
            os.environ["CERT_PATH"] = cert_path
            print(f"Automatically set CERT_PATH to {cert_path}")
            
    except Exception as e:
        print(f"Warning: Failed to decode CERT_BASE64: {e}")

import time
from src.connection import Trader


def main():
    """系統主進入點"""
    print("初始化永豐期貨交易系統...")

    try:
        #trader = Trader()
        #accounts = trader.login()
        #print(f"登入成功。可用帳戶數: {len(accounts)}")
        #for acc in accounts:
        #    print(f" - {acc}")
        #print("登入成功")

        # Keep the program running
        print("系統運行中，按 Ctrl+C 停止...")
        while True:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            print(f"系統運行中，目前時間：[{current_time}]")
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
