# Futures Trading System

一個基於 Python 與 Shioaji API (永豐金證券) 開發的期貨自動交易系統。支援本機運行與 Zeabur 雲端部署。

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Shioaji](https://img.shields.io/badge/Shioaji-API-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ 特色

*   **自動登入**：支援 Shioaji API 自動登入與 CA 憑證啟用。
*   **即時行情**：自動抓取並訂閱微型台指期 (MXF) 近月合約的即時行情 (Tick data)。
*   **雲端部署優化**：專為 Zeabur 部署設計，支援環境變數設定與 Base64 憑證還原。
*   **跨平台支援**：相容 Windows 本機開發與 Linux 容器環境。

## 🚀 快速開始

### 前置需求

*   Python 3.9 或更高版本
*   永豐金證券帳戶 (API Key, Secret Key, PFX 憑證)

### 1. 安裝與設定

複製專案並安裝相依套件：

```bash
git clone https://github.com/Lawrence-lab/Futures-Trading-System.git
cd Futures-Trading-System
pip install -r requirements.txt
```

### 2. 環境變數設定

在專案根目錄建立 `.env` 檔案，填入你的帳戶資訊：

```ini
API_KEY=你的API_Key
SECRET_KEY=你的Secret_Key
CERT_PATH=certs/你的憑證檔名.pfx
CERT_PASS=你的憑證密碼
SIMULATION=True  # True 為模擬環境，False 為正式環境
```

> **注意**：請確保 `certs/` 資料夾下有你的 `.pfx` 憑證檔案 (由於隱私原因，憑證檔已被 gitignore 排除)。

### 3. 本機執行

```bash
python src/main.py
```

程式啟動後將：
1.  登入 Shioaji API。
2.  尋找微型台指期 (MXF) 近月合約。
3.  開始每秒印出即時成交價、單量與買賣報價。

---

## ☁️ 部署至 Zeabur

本專案已包含 `Dockerfile`與 `zbpack.json`，可直接部署至 Zeabur。

### 憑證處理 (重要)

由於 Zeabur 無法直接上傳憑證檔案，需將 `.pfx` 轉為 Base64 字串並透過環境變數注入。

詳細步驟請參考：[Zeabur 部署憑證指南](docs/ZEABUR_CERT_GUIDE.md)

### Zeabur 環境變數

在 Zeabur Dashboard 設定以下變數：

*   `API_KEY`
*   `SECRET_KEY`
*   `CERT_PASS`
*   `CERT_BASE64` (你的 Base64 憑證字串)
*   `SIMULATION` (True/False)

---

## 📂 專案結構

```
Futures-Trading-System/
├── src/
│   ├── main.py         # 主程式入口，處理登入與行情迴圈
│   ├── connection.py   # Shioaji 連線模組
│   └── config.py       # Pydantic 設定讀取
├── certs/              # 放置 .pfx 憑證 (已加入 .gitignore)
├── docs/               #文件
├── requirements.txt    # Python 相依套件
├── Dockerfile          # Docker 建置檔
└── README.md           # 專案說明文件
```

## 🛠️ 開發

*   **格式化代碼**：專案使用 `black` 進行排版。
*   **靜態分析**：使用 `pylint` 檢查代碼品質。

## 📝 License

MIT License
