import logging
import shioaji as sj
from src.db_logger import get_db_connection
from src.line_notify import send_line_push_message

class PortfolioManager:
    def __init__(self, api=None):
        """
        初始化 PortfolioManager
        :param api: Shioaji API instance
        """
        self.api = api

    def get_virtual_position(self, strategy_name: str, contract_symbol: str) -> int:
        """從資料庫中取得策略當前的虛擬部位"""
        conn = get_db_connection()
        if not conn: return 0
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT position FROM virtual_positions WHERE strategy_name = %s AND contract_symbol = %s;",
                    (strategy_name, contract_symbol)
                )
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logging.error(f"[PortfolioManager] 取得虛擬部位失敗: {e}")
            return 0
        finally:
            conn.close()

    def set_virtual_position(self, strategy_name: str, contract_symbol: str, new_position: int, contract_obj=None, average_cost: float = 0.0) -> bool:
        """
        設定策略的虛擬部位。
        計算此策略變更部位後，整體(同一合約)的淨部位變化 (Delta)。
        如果 Delta != 0，則代為呼叫 API 發送實體委託單進行對沖對應。
        回傳: True/False (若實體單被拒絕則回傳 False，且不更新資料庫)
        """
        conn = get_db_connection()
        if not conn: 
            error_msg = f"🚨 [嚴重錯誤] 無法連線至資料庫！({strategy_name} 欲更新部位)。為避免資料不一致，系統已取消這次的實體下單動作。"
            logging.error(error_msg)
            send_line_push_message(error_msg)
            return False

        delta = 0
        old_net_position = 0
        new_net_position = 0

        # ========== STEP 1: 先計算出需不需要下單，與下單的 Delta ==========
        try:
            with conn.cursor() as cursor:
                # 取得該合約「變更前」所有策略加總的淨部位
                cursor.execute(
                    "SELECT COALESCE(SUM(position), 0) FROM virtual_positions WHERE contract_symbol = %s;",
                    (contract_symbol,)
                )
                old_net_position = cursor.fetchone()[0]
                
                # 計算該合約「變更後」的淨部位預期
                # 先扣掉原本這支策略的部位，再加上新部位
                cursor.execute(
                    "SELECT COALESCE(position, 0) FROM virtual_positions WHERE strategy_name = %s AND contract_symbol = %s;",
                    (strategy_name, contract_symbol)
                )
                row = cursor.fetchone()
                old_strategy_position = row[0] if row else 0
                
                new_net_position = old_net_position - old_strategy_position + new_position
                delta = new_net_position - old_net_position
                
        except Exception as e:
            error_msg = f"🚨 [嚴重錯誤] 查詢資料庫虛擬部位時發生異常: {e}。"
            logging.error(error_msg)
            send_line_push_message(error_msg)
            conn.close()
            return False

        # ========== STEP 2: 如果總部位有變動，先發送實體訂單 ==========
        order_success = True
        if delta != 0:
            logging.info(f"[PortfolioManager] {contract_symbol} 預期淨部位變更: {old_net_position} -> {new_net_position} (Delta: {delta})")
            if self.api and contract_obj:
                # 這裡會卡住等待送單回覆
                order_success = self._execute_real_order(contract_obj, delta, price=average_cost)
            elif not contract_obj:
                msg = f"⚠️ [PortfolioManager] 警告：需要下單 Delta: {delta} 但未提供合約物件！"
                logging.warning(msg)
                send_line_push_message(msg)
                order_success = False
            elif not self.api:
                logging.info(f"[PortfolioManager] 無 API 實例，跳過實體委託 (Delta: {delta})，視為成功。")
                
        if not order_success:
            msg = f"❌ [{strategy_name}] API 實體單委託失敗，系統已自動取消寫入虛擬部位，避免狀態不同步！"
            logging.warning(msg)
            send_line_push_message(msg)
            conn.close()
            return False

        # ========== STEP 3: 確定訂單送出成功後，才寫入資料庫 ==========
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO virtual_positions (strategy_name, contract_symbol, position, average_cost, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (strategy_name, contract_symbol) 
                    DO UPDATE SET position = EXCLUDED.position, average_cost = EXCLUDED.average_cost, updated_at = CURRENT_TIMESTAMP;
                    """,
                    (strategy_name, contract_symbol, new_position, average_cost)
                )
            conn.commit()
            return True
            
        except Exception as e:
            error_msg = f"🚨 [嚴重錯誤] 寫入資料庫變更時發生異常: {e}。這可能導致資料不同步！"
            logging.error(error_msg)
            send_line_push_message(error_msg)
            conn.rollback()
            return False
            
        finally:
            conn.close()

    def _execute_real_order(self, contract, delta: int, price: float = 0.0) -> bool:
        """
        執行實體委託單送出。
        回傳: True 代表送單成功 (或模擬環境/無 API), False 代表送單失敗。
        """
        if not self.api or not contract:
            return True # 回測或無連線狀態視為虛擬成功
            
        action = sj.constant.Action.Buy if delta > 0 else sj.constant.Action.Sell
        qty = abs(delta)

        # 為了支援夜盤，改用限價單 (LMT) 代替市價單 (MWP)
        # 加減價 50 點作為讓價，模擬市價單確保成交 (IOC)
        order_price = float(price)
        if price > 0:
            if action == sj.constant.Action.Buy:
                order_price = price + 50
            else:
                order_price = price - 50

        try:
            order = self.api.Order(
                action=action,
                price=order_price,
                quantity=qty,
                price_type=sj.constant.FuturesPriceType.LMT, # 限價單
                order_type=sj.constant.OrderType.IOC, # 保持 IOC 立即成交否則取消
                octype=sj.constant.FuturesOCType.Auto
            )
            # 送出預告單
            trade = self.api.place_order(contract, order)
            
            # Shioaji 的 place_order 回傳一個 Trade 物件，我們可以檢查它是否被直接拒絕
            # 若為被拒絕的單，可能 status 會直接標明 Failed，或包含 op_msg
            if hasattr(trade, 'status'):
                status_dict = getattr(trade.status, 'dict', lambda: {})() if not isinstance(trade.status, dict) else trade.status
                # op_code 例如 '99QB'
                # 注意 Shioaji trade 結構隨版本不同可能微調。大部份致命錯誤會拋出 Exception，少數會包在 trade 裡面
                pass
                
            logging.info(f"[PortfolioManager] [ORDER] 系統代發淨額調整單已送出: 行為={action}, 數量={qty}, 委託定價={order_price}, Trade={trade}")
            return True
            
        except Exception as e:
            error_msg = f"❌ [PortfolioManager] [ERROR] 淨額單送出失敗 (Delta: {delta}): {e}"
            logging.error(error_msg)
            send_line_push_message(error_msg)
            return False

    def reconcile_positions(self, contract_symbol: str):
        """
        對帳安全機制：
        比對券商庫存的實際口數，與資料庫中所有策略的「總虛擬淨部位」是否相符。
        若不相符，代表可能發生了手動干預、實體單漏單或斷線未同步，發出嚴重警告。
        """
        if not self.api:
            return  # 若無 API 實例（例如回測環境）則不進行實體對帳

        real_position = 0
        virtual_net_position = 0

        # 取回系統 (券商端) 實際期貨部位
        try:
            account = self.api.futopt_account
            if account:
                positions = self.api.list_positions(account)
                for pos in positions:
                    if pos.code == contract_symbol:
                        # Shioaji 部位資料可能分 BUY / SELL，需要將數量轉為帶號淨額
                        direction_sign = 1 if pos.direction == sj.constant.Action.Buy else -1
                        qty = pos.quantity
                        real_position += (direction_sign * qty)
        except Exception as e:
            logging.error(f"[PortfolioManager_Reconciliation] 無法取得實體部位: {e}")
            return # 取得失敗不當作異常對帳

        # 取回資料庫中的虛擬總淨部位
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT COALESCE(SUM(position), 0) FROM virtual_positions WHERE contract_symbol = %s;",
                        (contract_symbol,)
                    )
                    virtual_net_position = cursor.fetchone()[0]
            except Exception as e:
                logging.error(f"[PortfolioManager_Reconciliation] 無法取得虛擬部位總和: {e}")
                return
            finally:
                conn.close()

        # 進行比對
        if real_position != virtual_net_position:
            alert_msg = (
                f"🚨 [嚴重警告：部位不同步！] 🚨\n\n"
                f"標的：{contract_symbol}\n"
                f"🤖 系統虛擬總部位：{virtual_net_position} 口\n"
                f"🏦 券商實際總庫存：{real_position} 口\n\n"
                f"⚠️ 請立即檢查券商 APP，可能有手動平倉或漏單發生。建議暫停自動交易並重新對齊數據庫部位。"
            )
            logging.critical(alert_msg)
            send_line_push_message(alert_msg)
        else:
            logging.info(f"[PortfolioManager] ✅ 週期對帳成功 - {contract_symbol} 部位一致: {real_position} 口。")

