# 微型台指期貨交易系統 (Micro TAIEX Futures Trading System)

這是一個基於 Python 的自動化交易系統，使用永豐金證券 Shioaji API 針對 **微型台指期 (Micro TAIEX Futures, TMF)** 進行交易。本系統核心採用 **多策略雙軌架構**，同時運行順勢長波段與逆勢摸底策略。

## 功能特色 (Features)

- **商品**: 微型台指期 (TMF) / Micro TAIEX Futures.
- **核心架構**: 基於 `PortfolioManager` 的多策略組合交易，統籌持倉與對衝風險。
- **搭載策略**:
    - 📈 **Gatekeeper-MXF-V1 (門神一號)**: 雙時間框架順勢波段策略。
    - 📉 **Gatekeeper-BNF-B (摸底逆勢)**: 乖離率與爆量極端值逆勢抄底策略。
- **風險管理**:
    - **部位控制**: 每次訊號均固定下 1 口單。
    - **動態停損**: 結合 ATR (波動率) 自動計算安全防守距離。
    - **移動停利 (Trailing Stop)**: 確保獲利不回吐，抱住長波段。
    - **保本機制 (Break-Even)**: 獲利達標後強制將停損移至成本價。
- **系統架構**:
    - **`src/main.py`**: 即時行情監控與自動交易引擎。
    - **`src/backtest.py`**: 歷史回測模擬 (O(N) 高效運算)。
    - **`src/processors/kline_maker.py`**: 從 Tick 資料即時生成 K 線。

## 績效回測 (Performance - Backtest 最佳化結論)

經過 2025/08 ~ 2026/02 的量化網格測試，系統找出以下黃金參數：

**Gatekeeper-MXF-V1 (順勢波段)**
- **勝率**: 54.55% (11 次交易)
- **總損益**: **+3,019 點** 
- **最佳參數**: UT-Bot 敏感度 `4.0` | 移動停利折返 `200` 點

**Gatekeeper-BNF-B (逆勢摸底)**
- **勝率**: 53.33% (15 次交易)
- **總損益**: **+3,052 點**
- **最佳參數**: 60MA 乖離率小於 `-1.5%` | 成交量大於 20MA 的 `2.0` 倍

## 先決條件 (Prerequisites)

1.  **Python 3.10+**
2.  **永豐金證券 Shioaji API 帳號**
3.  **交易憑證 (`.pfx` 檔案)**

## 安裝步驟 (Installation)

1.  複製專案庫:
    ```bash
    git clone https://github.com/Lawrence-lab/Futures-Trading-System.git
    cd Futures-Trading-System
    ```

2.  安裝相依套件:
    ```bash
    pip install shioaji pandas numpy pydantic-settings
    ```

3.  **憑證設定**:
    - 將您的 `Sinopac.pfx` 憑證檔案放入 `certs/` 目錄。
    - 或者設定 `CERT_PATH` 環境變數指向憑證路徑。
    - 建立 `.env` 檔案並填入 API 金鑰 (參考 `src/config.py`)。

## 使用說明 (Usage)

### 1. 執行歷史回測
執行回測程式以驗證 **Gatekeeper-MXF-V1** 策略表現：
```bash
python src/backtest.py
```
*   自動抓取 TMF 近 180 天的 1 分鐘歷史資料。
*   模擬交易並輸出詳細日誌與損益報告。
*   日誌範例: `[Gatekeeper-MXF-V1_Backtest] [SIGNAL] 買入進場 ...`

### 2. 啟動即時監控 (Live Monitoring)
啟動主程式以進行即時行情監控：
```bash
python src/main.py
```
*   **自動登入**: 連結 Shioaji API。
*   **自動選約**: 自動尋找並鎖定微型台指期 (TMF) 近月合約。
*   **即時運算**: 根據 Tick 資料即時更新 5分K 與 60分K，並檢查訊號。
*   **到期監控**: 顯示合約剩餘天數 (Expiry Days)，輔助轉倉決策。

## 策略邏輯 (Strategy Logic)

本系統掛載的兩套策略完全獨立運作，並透過 PortfolioManager 統合計算實際下單水位。單次觸發皆固定下 `1 口`。

### 1. Gatekeeper-MXF-V1 (順勢長波段)
利用雙時間框架 (1D / 60M) 過濾雜訊，鎖定真正的大波段。
- **進場條件**: 日K `Supertrend` 確認多空大方向，60分K `UT Bot (敏感度 4.0)` 發出同向買賣訊號，且實體 K 棒超過 100 點。
- **出場風控**:
    - **初始停損**: 進場點 ± 2.0 * ATR。
    - **保本機制**: 獲利超過 `150 點`，停損立刻移至進場成本價。
    - **移動停利**: 啟動保本後，若價格由最高點回落 `200 點` 即停利出場。

### 2. Gatekeeper-BNF-B (逆勢短波段)
捕捉恐慌性拋售的極端乖離，實施快進快出的摸底策略。
- **進場條件**: 當價格距離 `60MA` 之乖離率低於 `-1.5%`，且當前成交量爆增至 `20MA` 的 `2.0` 倍以上 (每日限進場 1 次)。
- **出場風控**:
    - **初始停損**: 固定 `-100 點`。
    - **保本與移動停利**: 當反彈獲利達 `+80 點` 時，將停損拉至保本 (進場價)，並啟動 `2.0 * ATR` 高緊密追蹤停利。
    - **均線修復**: 若價格觸及甚至反轉越過 60MA，代表摸底任務完成，全數出場。
    - **時間停損**: 持倉若超過 3 天仍未發動，強制出場。

## 轉倉處理 (Rollover Handling)

系統在啟動時會自動選擇近月合約 (Near-Month Contract)。
> **建議**: 請在結算日 (每月第三個週三) 收盤後，手動重啟程式以切換至新的近月合約。請留意日誌中的 `[Monitor] Expiry: X days` 提示。

## Zeabur 部署指南 (Zeabur Deployment)

本專案已針對 Zeabur 雲端平台進行最佳化配置，確保背景交易程式與前台 Streamlit 儀表板能同時運行於單一容器中。

### 部署注意事項與雷區：
1. **不要使用 `Procfile` 或 `nixpacks.toml`**: 
   Zeabur 內部的 Nixpacks 建置系統若偵測到 Python 專案，預設會強制執行 `python src/main.py`。若試圖用 `Procfile` 自定義 `web` 和 `worker` 程序，極易導致 Streamlit 網頁服務無法被正確綁定到對外 Port 而引發 **502 Bad Gateway**。
2. **單一進入點 (`src/main.py`)**: 
   為了突破雲端平台的啟動限制，本專案將 Streamlit 伺服器的啟動邏輯直接寫入 `src/main.py` 的主程式區塊。只要 Zeabur 執行了 `main.py`，Python 就會在背景生成一個 subprocess 獨立拉起儀表板。
3. **對外 Port 綁定**: 
   確保 `Dockerfile` 內有 `EXPOSE 8080`，並配合專案根目錄的 `zeabur.json` (指定 `"port": 8080`)，讓 Zeabur 的路由精確導向 Streamlit 所在的連線埠。
4. **環境變數 (Environment Variables)**: 
   請務必在 Zeabur 的控制台面板中，將 `.env` 內的機密變數 (如 `DATABASE_URL`, `API_KEY`, `CERT_BASE64` 等) 填寫至「環境變數」設定區塊中。

## 授權 (License)
MIT
