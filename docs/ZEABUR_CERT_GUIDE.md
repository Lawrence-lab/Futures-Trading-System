# Zeabur 憑證上傳指南

要在 Zeabur 上安全且正確地使用 `.pfx` 憑證，建議使用 **Config File (設定檔)** 功能。這比直接上傳到容器更安全且具備持久性。

## 方法一：使用 Zeabur Config File (推薦)

1.  **準備憑證**：確保你的 `.pfx` 檔案在手邊 (例如 `Sinopac.pfx`)。
2.  **進入 Zeabur Dashboard**：
    *   點選你的服務。
    *   切換到 **Settings (設定)** > **Config Files (設定檔)**。
3.  **新增設定檔**：
    *   點擊 **Add Config File**。
    *   **File Path (掛載路徑)**：輸入 `/app/certs/Sinopac.pfx` (這是容器內的路徑)。
    *   **Content (內容)**：直接將你的 `.pfx` 檔案拖曳到上傳區域，或點擊上傳。
4.  **設定環境變數**：
    *   切換到 **Variables (環境變數)**。
    *   設定 `CERT_PATH` 為 `/app/certs/Sinopac.pfx`。
    *   設定 `CERT_PASS` 為你的憑證密碼。
    *   (別忘了設定 `API_KEY` 和 `SECRET_KEY`)。

Zeabur 會自動重新部署服務，並將憑證掛載到指定路徑。

---

## 方法二：Base64 字串 (適合 CI/CD)

如果你不想手動上傳檔案，可以將檔案轉為 Base64 字串並存入環境變數。

1.  **產生 Base64 字串** (PowerShell):
    ```powershell
    $base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("path/to/cert.pfx"))
    Write-Host $base64
    ```
2.  **設定環境變數**：
    *   在 Zeabur 新增一個變數，例如 `CERT_BASE64`，內容貼上那串很長的字串。
3.  **修改程式碼**：
    *   你需要修改 `main.py` 或 `config.py`，在啟動時讀取 `CERT_BASE64`，解碼並寫入到 `/tmp/temp.pfx`，然後讓 Shioaji 讀取該暫存檔。

*注意：目前程式碼尚未支援此方法，若需要請告訴我，我可以幫你修改。*

---

## 方法三：手動寫入 (僅供測試，不持久)

你也可以進入 Zeabur 的 **Terminal (終端機)** 手動建立檔案，但**只要服務重新部署 (例如 Push 新程式碼)，檔案就會消失**。

1.  在本地執行 `scripts/generate_upload_command.ps1`。
2.  複製產生的指令。
3.  在 Zeabur Dashboard 開啟服務的 Terminal。
4.  貼上指令執行。

**警告**：此方法不適合生產環境，建議僅用於暫時測試。
