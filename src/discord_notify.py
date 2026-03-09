import os
import requests

def send_discord_message(message: str):
    """
    發送 Discord 訊息到指定的 Webhook URL。
    需確保環境變數中設定了 DISCORD_WEBHOOK_URL。
    """
    # Check global kill switch
    if os.environ.get("DISABLE_NOTIFY", "").lower() == "true":
        return

    # 從環境變數讀取 Webhook URL
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    
    if not webhook_url:
        print("⚠️ 錯誤：請確保 DISCORD_WEBHOOK_URL 環境變數已設定。")
        return

    headers = {
        "Content-Type": "application/json"
    }
    
    data = {
        "content": message
    }

    try:
        response = requests.post(webhook_url, headers=headers, json=data)
        response.raise_for_status() # 檢查是否有 HTTP 錯誤狀態碼
        print("✅ Discord 訊息發送成功！")
        
        # 204 No Content is standard for successful Discord webhook post without `wait=true`
        if response.status_code != 204:
            return response.json()
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Discord 訊息發送失敗: {e}")
        if e.response is not None:
            print(f"詳細錯誤回應: {e.response.text}")
        return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() # 自動載入同目錄下的 .env 檔案
    
    test_message = "🤖 門神 V1：Discord Webhook 環境測試成功！"
    send_discord_message(test_message)
