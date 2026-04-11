import os
from dotenv import load_dotenv

import kgisuperpy as kgi
from kgisuperpy.pushClient.pyTradeCom import TradeComAPI

# Monkey Patch
TradeComAPI._Login_original = TradeComAPI.Login

def login_with_cert(self, user_id, password):
    cert_path = os.environ.get("CERT_PATH")
    cert_pass = os.environ.get("CERT_PASS")
    print(f"[Patch] Attempting to set KGI CA.")
    if cert_path and cert_pass:
        print(f"[Patch] Applying KGI cert from: {cert_path}")
        self.SetCA_PFX(cert_path)
        self.SetCA_PW(cert_pass)
    else:
        print("[Patch] No CERT_PATH or CERT_PASS found in env.")
    self._Login_original(user_id, password)

TradeComAPI.Login = login_with_cert

if __name__ == "__main__":
    load_dotenv()
    kgi_id = os.environ.get("KGI_ID")
    kgi_pwd = os.environ.get("KGI_PASSWORD")
    
    print("Initializing KGI API...")
    try:
        api = kgi.login(
            person_id=kgi_id,
            person_pwd=kgi_pwd,
            simulation=False
        )
        print("Login complete!")
    except Exception as e:
        print(f"Error: {e}")
