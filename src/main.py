"""
主程式入口
"""
import sys
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

        # 未來: 在此初始化策略
        # strategy = MyStrategy(trader)
        # strategy.run()

    except Exception as e:
        print(f"系統啟動失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
