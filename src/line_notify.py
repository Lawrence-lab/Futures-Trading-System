import os
import requests

def send_line_push_message(message: str):
    """
    發送 LINE Push Message 到指定的 User ID。
    需確保環境變數中設定了 LINE_CHANNEL_ACCESS_TOKEN 與 LINE_USER_ID。
    """
    # 從環境變數讀取 Token 和 User ID
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.environ.get("LINE_USER_ID")
    
    if not token or not user_id:
        print("⚠️ 錯誤：請確保 LINE_CHANNEL_ACCESS_TOKEN 和 LINE_USER_ID 環境變數已設定。")
        return

    url = "https://api.line.me/v2/bot/message/push"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    data = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status() # 檢查是否有 HTTP 錯誤狀態碼
        print("✅ LINE 訊息發送成功！")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ LINE 訊息發送失敗: {e}")
        if e.response is not None:
            print(f"詳細錯誤回應: {e.response.text}")
        return None

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv() # 自動載入同目錄下的 .env 檔案
    
    test_message = "🏮 門神 V1：Zeabur 環境測試成功！"
    send_line_push_message(test_message)
