import shioaji as sj
from src.config import settings

class Trader:
    def __init__(self):
        self.api = sj.Shioaji(simulation=settings.simulation)

    def login(self):
        """
        使用設定中的憑證登入 Shioaji API。
        登入成功後回傳帳戶清單。
        """
        try:
            self.api.login(
                api_key=settings.api_key,
                secret_key=settings.secret_key,
                contracts_cb=lambda security_type: print(f"{security_type} 合約載入完成。"),
            )
            # 交易通常需要 CA 憑證，雖然基本登入可能不需要，但為了完整性在此啟用。
            # 提示要求處理 *.pfx，且 Shioaji 下單通常需要 activate_ca。
            
            # 使用列表中的第一個帳戶進行 CA 憑證啟用
            self.api.activate_ca(
                ca_path=settings.cert_path,
                ca_passwd=settings.cert_pass,
                person_id=self.api.list_accounts()[0].person_id,
            )
            
            print("登入與 CA 憑證啟用成功。")
            return self.api.list_accounts()
            
        except Exception as e:
            print(f"登入失敗: {e}")
            raise

if __name__ == "__main__":
    trader = Trader()
    accounts = trader.login()
    print("帳戶清單:", accounts)
