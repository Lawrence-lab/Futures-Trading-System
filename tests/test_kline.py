
import unittest
from datetime import datetime, timedelta
from src.processors.kline_maker import KLineMaker, Bar

class TestKLineMaker(unittest.TestCase):
    def setUp(self):
        self.maker = KLineMaker()

    def test_single_bar_update(self):
        # 模擬同一 5 分鐘內的 tick
        # 時間 10:00:00 -> 屬於 10:00 bar
        t1 = datetime(2023, 10, 27, 10, 0, 0)
        tick1 = {'datetime': t1, 'close': 100, 'volume': 1}
        self.maker.update_with_tick(tick1)
        
        self.assertIsNotNone(self.maker.current_bar)
        self.assertEqual(self.maker.current_bar.time, datetime(2023, 10, 27, 10, 0, 0))
        self.assertEqual(self.maker.current_bar.open, 100)
        
        # 時間 10:04:59 -> 仍屬於 10:00 bar
        t2 = datetime(2023, 10, 27, 10, 4, 59)
        tick2 = {'datetime': t2, 'close': 105, 'volume': 2}
        self.maker.update_with_tick(tick2)
        
        self.assertEqual(self.maker.current_bar.time, datetime(2023, 10, 27, 10, 0, 0))
        self.assertEqual(self.maker.current_bar.high, 105)
        self.assertEqual(self.maker.current_bar.volume, 3) # 1+2

    def test_new_bar_creation(self):
        # 第一根 K 線 (10:00)
        t1 = datetime(2023, 10, 27, 10, 0, 0)
        self.maker.update_with_tick({'datetime': t1, 'close': 100, 'volume': 1})
        
        # 相同 bar (10:04:59)
        t2 = datetime(2023, 10, 27, 10, 4, 59)
        self.maker.update_with_tick({'datetime': t2, 'close': 101, 'volume': 1})
        
        # 第二根 K 線 (10:05) -> 觸發切換
        t3 = datetime(2023, 10, 27, 10, 5, 0)
        self.maker.update_with_tick({'datetime': t3, 'close': 102, 'volume': 5})
        
        # 確認第一根 bar 已進入 deque
        self.assertEqual(len(self.maker.bars), 1)
        bar0 = self.maker.bars[0]
        self.assertEqual(bar0.time, datetime(2023, 10, 27, 10, 0, 0))
        self.assertEqual(bar0.close, 101)
        
        # 確認當前 bar 是新的 10:05
        self.assertEqual(self.maker.current_bar.time, datetime(2023, 10, 27, 10, 5, 0))
        self.assertEqual(self.maker.current_bar.open, 102)
        self.assertEqual(self.maker.current_bar.volume, 5)

if __name__ == '__main__':
    unittest.main()
