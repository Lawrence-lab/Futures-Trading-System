# 微型台指期貨交易系統 (Micro TAIEX Futures Trading System)

這是一個基於 Python 的自動化交易系統，使用永豐金證券 Shioaji API 針對 **微型台指期 (Micro TAIEX Futures, TMF)** 進行交易。本系統核心策略為 **Gatekeeper-MXF-V1 (門神一號)**，採用雙時間框架邏輯捕捉趨勢並過濾雜訊。

## 功能特色 (Features)

- **商品**: 微型台指期 (TMF) / Micro TAIEX Futures.
- **策略名稱**: **Gatekeeper-MXF-V1 (門神一號)**
- **核心邏輯**: 雙時間框架策略 (60分K 趨勢濾網 + 5分K 進場訊號)。
- **技術指標**: Supertrend (趨勢判斷), UT Bot Alerts (訊號觸發), ATR (波動率計算)。
- **風險管理**:
    - **動態停損**: 進場價 - (2.0 * ATR)。
    - **移動停利 (Trailing Stop)**: 獲利回吐保護。
    - **保本機制 (Break-Even)**: 獲利達標後將停損移至成本價。
    - **實體濾網 (Candle Body Filter)**: 避免盤整與假突破。
- **系統架構**:
    - **`src/main.py`**: 即時行情監控與自動交易引擎。
    - **`src/backtest.py`**: 歷史回測模擬 (O(N) 高效運算)。
    - **`src/processors/kline_maker.py`**: 從 Tick 資料即時生成 K 線。

## 績效回測 (Performance - Backtest)

**測試期間**: 2025年12月 - 2026年2月 (約 2.5 個月)
- **勝率 (Win Rate)**: 62.5%
- **總損益 (Total PnL)**: **+509 點** (約 +5,090 TWD / 口)
- **最大回檔 (Max Drawdown)**: ~125 點
- **交易次數**: 8 次 (精準進場)

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

## 策略邏輯 (Strategy Logic: Gatekeeper-MXF-V1)

1.  **趨勢濾網 (Trend Filter - 60m)**:
    - 使用 **Supertrend** 指標判斷 60 分鐘線趨勢。
    - 僅在 60 分 K 為多頭趨勢時，才允許進場做多。
2.  **進場訊號 (Entry Signal - 5m)**:
    - 使用 **UT Bot** 指標在 5 分鐘線上尋找買點。
    - **濾網**: K 棒實體 (收盤 - 開盤) 必須 > 60 點 (動能確認)。
3.  **出場規則 (Exit Rules)**:
    - **初始停損**: 進場價 - (2.0 * ATR)。
    - **保本機制**: 獲利 > 60 點時，將停損移至進場價。
    - **移動停利**: 獲利 > 60 點後，若價格從高點回落 30 點則出場。

## 轉倉處理 (Rollover Handling)

系統在啟動時會自動選擇近月合約 (Near-Month Contract)。
> **建議**: 請在結算日 (每月第三個週三) 收盤後，手動重啟程式以切換至新的近月合約。請留意日誌中的 `[Monitor] Expiry: X days` 提示。

## 授權 (License)
MIT
