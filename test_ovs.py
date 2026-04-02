import time
import sys
import os
sys.path.append(os.path.abspath('.'))
from src.connection import Trader
import shioaji as sj

def main():
    print("【海期資料抓取測試】")
    print("正在登入與初始化 API...")
    trader = Trader()
    trader.login()
    print("-" * 30)
    
    try:
        print("正在檢查您的帳號是否有海期合約資料權限...")
        
        # 檢查 Contracts 底下是否有 OVSFutures (海期分類)
        if hasattr(trader.api.Contracts, 'OVSFutures'):
            print("✅ 您的帳號具備海期權限，正在嘗試抓取 CME 小那斯達克 (MNQ) 合約...")
            cme_contracts = trader.api.Contracts.OVSFutures.CME
            mnq_list = [c for c in cme_contracts if 'MNQ' in c.code]
            
            if not mnq_list:
                print("⚠️ 找不到 CME 的 MNQ 合約。")
            else:
                contract = mnq_list[0]
                print(f"✅ 成功找到海期合約：{contract.code} - {contract.target_name} ({contract.delivery_month})")
                
                print("---")
                print("正在測試歷史 K 線資料存取權限 (Kbars)...")
                kbars = trader.api.kbars(contract, start="2024-05-01", end="2024-05-03")
                if kbars and kbars.ts:
                    print(f"✅ 歷史 K 線抓取成功！取得 {len(kbars.ts)} 筆資料。")
                else:
                    print("⚠️ K 線抓取結果為空。")
        else:
            print("❌ 測試失敗：您的帳號目前「無法」抓取海期資料！")
            print("💡 原因分析：API 的 Contracts 找不到海期 (OVSFutures) 的資料模組。")
            print("這通常是因為以下兩個原因之一：")
            print("  1. 您的永豐期貨帳戶「尚未開通海外期貨權限」。")
            print("  2. 您還沒有簽署海期報價或交易的相關風險預告書。")
            print("👉 建議做法：請聯絡您的永豐營業員，請其協助確認並開通海期 API 權限。")
            
    except Exception as e:
        print(f"❌ 發生未知的錯誤: {e}")
        
    finally:
        print("-" * 30)
        print("登出 API...")
        trader.api.logout()
        print("測試結束。")

if __name__ == '__main__':
    main()
