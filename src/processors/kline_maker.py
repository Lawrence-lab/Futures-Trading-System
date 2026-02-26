import collections
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Bar:
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

class KLineMaker:
    def __init__(self, timeframe: int = 1):
        """
        初始化 KLineMaker
        :param timeframe: K 線週期 (分鐘), 例如 1, 5, 60
        """
        self.timeframe = timeframe
        self.bars = collections.deque(maxlen=100)
        self.current_bar = None

    def update_with_tick(self, tick_data: dict) -> bool:
        """
        根據傳入的 tick 更新 K 線
        :param tick_data: Shioaji quote.to_dict() 後的字典, 需包含 'datetime', 'close', 'volume'
        :return: bool, 如果產生了新的 K 線 (上一根完成) 則回傳 True, 否則 False
        """
        is_new_bar_completed = False

        # 1. 解析時間與價格
        try:
            ts = tick_data.get('datetime')
            raw_price = tick_data.get('close')
            raw_volume = tick_data.get('volume')
            
            # Cast to native float/int to avoid Decimal operand errors downstream
            price = float(raw_price) if raw_price is not None else None
            volume = int(raw_volume) if raw_volume is not None else None
            
            if ts is None or price is None:
                return False

            # Shioaji 的 datetime 是 string 還是 datetime object? 
            # 通常是 str "2023-10-27 13:45:00.123456" 或者是 datetime object
            # 假設傳入的是 datetime object, 如果是 str 需解析
            if isinstance(ts, str):
                # 簡單解析，實際格式需視 API 回傳而定，這裡假設已轉換或標準格式
                # 為了穩健，這裡假設外部已經 parse 好，或者我們做簡單處理
                # 如果是 shioaji, quote.datetime 通常是 datetime.datetime
                ts = datetime.fromisoformat(ts) 

            # K 線時間對齊
            if self.timeframe >= 60:
                # 簡單處理 60 分鐘 (及以上, 假設是 60 的倍數)
                # 對應到該小時的開始
                 bar_time = ts.replace(minute=0, second=0, microsecond=0)
            else:
                # 分鐘等級對齊
                minute = (ts.minute // self.timeframe) * self.timeframe
                bar_time = ts.replace(minute=minute, second=0, microsecond=0)

            # 2. 判斷是否需要切換 K 線
            if self.current_bar is None:
                # 第一根 K 線
                self.current_bar = Bar(
                    time=bar_time,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=volume if volume else 0
                )
            elif bar_time > self.current_bar.time:
                # 時間推進，結算上一根 Bar
                self.bars.append(self.current_bar)
                is_new_bar_completed = True
                
                # 印出日誌 (Zeabur Log)
                print(f"[KLine {self.timeframe}m] New Bar: {self.current_bar}", flush=True)

                # 建立新 Bar
                self.current_bar = Bar(
                    time=bar_time,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=volume if volume else 0
                )
            else:
                # 同一週期內，更新當前 Bar
                self.current_bar.high = max(self.current_bar.high, price)
                self.current_bar.low = min(self.current_bar.low, price)
                self.current_bar.close = price
                # volume 在 tick 中通常是 "該筆成交量" 或是 "累計成交量"? 
                # Shioaji Tick 的 volume 通常是 "該筆成交量" (tick volume)
                # 如果是累計量則需要相減，這邊假設是單筆量 (tick volume)
                # 如果是 simtrade 可能會有不同，但在這裡我們假設它是單筆增量
                if volume:
                    self.current_bar.volume += volume
                    
        except Exception as e:
            print(f"Error processing tick: {e}")
            
        return is_new_bar_completed

    def get_dataframe(self):
        """
        將目前的 K 線資料轉換為 Pandas DataFrame
        """
        if not self.bars:
            return pd.DataFrame()
            
        data = [
            {
                'datetime': bar.time,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            }
            for bar in self.bars
        ]
        
        # 如果有當前的 Bar (尚未完成)，也可以考慮加進去，視策略需求而定
        # 通常策略是看「已完成」的 Bar，或者是看「已完成 + 當前即時」
        # 這裡先只回傳已完成的 bars
        
        df = pd.DataFrame(data)
        return df

    def load_historical_dataframe(self, df: pd.DataFrame):
        """
        將歷史 DataFrame 直接轉換為內部 Bar 結構並載入
        df 需包含 datetime, open, high, low, close, volume 欄位
        """
        if df.empty:
            return
            
        for _, row in df.iterrows():
            # 確保 time 欄位為 datetime object
            ts = row['datetime']
            if not isinstance(ts, datetime):
                ts = pd.to_datetime(ts).to_pydatetime()
                
            bar = Bar(
                time=ts,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume']) if pd.notna(row['volume']) else 0
            )
            self.bars.append(bar)
        
        # Optionally print completion
        print(f"[KLine {self.timeframe}m] Preloaded {len(df)} historical bars.")
