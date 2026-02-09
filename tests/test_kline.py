
import unittest
from datetime import datetime, timedelta
from src.processors.kline_maker import KLineMaker, Bar

class TestKLineMaker(unittest.TestCase):
    def setUp(self):
        self.maker = KLineMaker()

    def test_single_bar_update(self):
        # 模擬同一分鐘內的 tick
        # 時間 10:00:00
        t1 = datetime(2023, 10, 27, 10, 0, 0)
        tick1 = {'datetime': t1, 'close': 100, 'volume': 1}
        self.maker.update_with_tick(tick1)
        
        self.assertIsNotNone(self.maker.current_bar)
        self.assertEqual(self.maker.current_bar.open, 100)
        self.assertEqual(self.maker.current_bar.high, 100)
        self.assertEqual(self.maker.current_bar.low, 100)
        self.assertEqual(self.maker.current_bar.close, 100)
        self.assertEqual(self.maker.current_bar.volume, 1)

        # 時間 10:00:30, 價格上漲
        t2 = datetime(2023, 10, 27, 10, 0, 30)
        tick2 = {'datetime': t2, 'close': 105, 'volume': 2}
        self.maker.update_with_tick(tick2)
        
        self.assertEqual(self.maker.current_bar.high, 105)
        self.assertEqual(self.maker.current_bar.close, 105)
        self.assertEqual(self.maker.current_bar.volume, 3) # 1+2

        # 時間 10:00:59, 價格下跌
        t3 = datetime(2023, 10, 27, 10, 0, 59)
        tick3 = {'datetime': t3, 'close': 95, 'volume': 1}
        self.maker.update_with_tick(tick3)
        
        self.assertEqual(self.maker.current_bar.low, 95)
        self.assertEqual(self.maker.current_bar.close, 95)
        self.assertEqual(self.maker.current_bar.volume, 4) # 1+2+1

    def test_new_bar_creation(self):
        # 第一根 K 線
        t1 = datetime(2023, 10, 27, 10, 0, 0)
        self.maker.update_with_tick({'datetime': t1, 'close': 100, 'volume': 1})
        
        # 第二根 K 線 (下一分鐘)
        t2 = datetime(2023, 10, 27, 10, 1, 0)
        self.maker.update_with_tick({'datetime': t2, 'close': 102, 'volume': 5})
        
        # 確認第一根 bar 已進入 deque
        self.assertEqual(len(self.maker.bars), 1)
        bar0 = self.maker.bars[0]
        self.assertEqual(bar0.time, datetime(2023, 10, 27, 10, 0, 0))
        self.assertEqual(bar0.close, 100)
        
        # 確認當前 bar 是新的
        self.assertEqual(self.maker.current_bar.time, datetime(2023, 10, 27, 10, 1, 0))
        self.assertEqual(self.maker.current_bar.open, 102)
        self.assertEqual(self.maker.current_bar.volume, 5)

if __name__ == '__main__':
    unittest.main()
