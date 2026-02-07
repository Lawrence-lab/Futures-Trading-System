"""
主程式入口
"""
import sys
import time
#from src.connection import Trader


def main():
    """系統主進入點"""
    print("初始化永豐期貨交易系統...")

    try:
        #trader = Trader()
        #accounts = trader.login()
        #print(f"登入成功。可用帳戶數: {len(accounts)}")
        #for acc in accounts:
        #    print(f" - {acc}")
        print("登入成功")

        # Keep the program running
        print("系統運行中，按 Ctrl+C 停止...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n系統已停止")
        sys.exit(0)

    except Exception as e:
        print(f"系統啟動失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
