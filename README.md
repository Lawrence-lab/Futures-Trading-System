# Futures Trading System (Micro TAIEX)

A Python-based automated trading system for **Micro TAIEX Futures (TMF)** using the Shioaji API. This system implements a **Dual Timeframe Strategy** to capture trends while filtering out noise.

## Features

- **Product**: Micro TAIEX Futures (TMF) / 微型台指期.
- **Strategy**: Dual Timeframe Logic (60m Trend Filter + 5m Entry Signal).
- **Indicators**: Supertrend (Trend), UT Bot alerts (Signal), ATR (Volatility).
- **Risk Management**:
    - Dynamic Stop Loss (2.0 * ATR).
    - Trailing Stop (Profit Protection).
    - Break-Even Trigger.
    - Candle Body Filter (Avoid Chop).
- **Architecture**:
    - **`src/main.py`**: Real-time monitoring and trading engine.
    - **`src/backtest.py`**: Historical backtesting simulation (O(N) optimized).
    - **`src/processors/kline_maker.py`**: Real-time K-line generation from ticks.

## Performance (Backtest)

**Period**: Dec 2025 - Feb 2026 (2.5 Months)
- **Win Rate**: 62.5%
- **Total PnL**: **+509 Points** (approx. +5,090 TWD per contract)
- **Max Drawdown**: ~125 Points
- **Trades**: 8 (Selective Entry)

## Prerequisites

1.  **Python 3.10+**
2.  **Shioaji API Account** (Sinopac Securities)
3.  **Trading Certificate** (`.pfx` file)

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/Lawrence-lab/Futures-Trading-System.git
    cd Futures-Trading-System
    ```

2.  Install dependencies:
    ```bash
    pip install shioaji pandas numpy
    ```

3.  **Certificate Setup**:
    - Place your `Sinopac.pfx` in the `certs/` directory.
    - Or set the `CERT_PATH` environment variable.

## Usage

### 1. Historical Backtest
Run the backtest to verify strategy performance on recent data:
```bash
python src/backtest.py
```
*   Fetches last 180 days of 1-minute data for TMF.
*   Simulates trades and prints detailed logs and PnL.

### 2. Live Monitoring (Paper/Live)
Start the main program to monitor the market in real-time:
```bash
python src/main.py
```
*   **Auto-Login**: Connects to Shioaji API.
*   **Auto-Select Contract**: Automatically finds the near-month TMF contract.
*   **Real-time Logic**: Updates 5m and 60m K-lines from ticks and checks signals.
*   **Expiry Monitor**: Logs "Days to Expiry" to help with rollover decisions.

## Strategy Logic

1.  **Trend Filter (60m)**:
    - Uses **Supertrend** on 60-minute bars.
    - Only look for Longs if 60m is Bullish.
2.  **Entry Signal (5m)**:
    - Uses **UT Bot** alerts on 5-minute bars.
    - **Filter**: Candle Body (Close - Open) must be > 60 points (Momentum check).
3.  **Exit Rules**:
    - **Initial Stop**: Entry Price - (2.0 * ATR).
    - **Break Even**: If Profit > 60 points, move Stop Loss to Entry Price.
    - **Trailing Stop**: If Profit > 60 points, exit if price drops 30 points from high.

## Rollover Handling

The system automatically selects the near-month contract on startup.
> **Recommendation**: Restart the program manually on settlement day (3rd Wednesday of the month) after market close to switch to the new contract. Watch the `[Monitor] Expiry: X days` log.

## License
MIT
