import collections
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
    def __init__(self):
        """
        初始化 KLineMaker
        :param max_len: K 線佇列的最大長度 (預設 100)
        """
        self.bars = collections.deque(maxlen=100)
        self.current_bar = None

    def update_with_tick(self, tick_data: dict):
        """
        根據傳入的 tick 更新 K 線
        :param tick_data: Shioaji quote.to_dict() 後的字典, 需包含 'datetime', 'close', 'volume'
        """
        # 1. 解析時間與價格
        try:
            ts = tick_data.get('datetime')
            price = tick_data.get('close')
            volume = tick_data.get('volume')
            
            if ts is None or price is None:
                return

            # Shioaji 的 datetime 是 string 還是 datetime object? 
            # 通常是 str "2023-10-27 13:45:00.123456" 或者是 datetime object
            # 假設傳入的是 datetime object, 如果是 str 需解析
            if isinstance(ts, str):
                # 簡單解析，實際格式需視 API 回傳而定，這裡假設已轉換或標準格式
                # 為了穩健，這裡假設外部已經 parse 好，或者我們做簡單處理
                # 如果是 shioaji, quote.datetime 通常是 datetime.datetime
                ts = datetime.fromisoformat(ts) 

            # 取那 5 分鐘的開始時間 (去掉秒跟微秒, 分鐘取 5 的倍數)
            # 例如 10:03 -> 10:00, 10:05 -> 10:05, 10:09 -> 10:05
            minute = (ts.minute // 5) * 5
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
                
                # 印出日誌 (Zeabur Log)
                print(f"[KLine] New Bar: {self.current_bar}", flush=True)

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
                # 同一分鐘內，更新當前 Bar
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
