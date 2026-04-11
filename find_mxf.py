import os
import kgisuperpy as kgi
from dotenv import load_dotenv

def find_mxf():
    load_dotenv()
    kgi_id = os.environ.get("KGI_ID")
    kgi_pwd = os.environ.get("KGI_PASSWORD")
    
    api = kgi.login(
        person_id=kgi_id, 
        person_pwd=kgi_pwd, 
        simulation=False
    )
    
    import time
    time.sleep(3)
    
    # Initialize connection for quotes
    api.FutQuote.get_subscriptions()
    time.sleep(1)
    
    keys = getattr(api.FutQuote, '_list', [])
    print(f"Total keys: {len(keys)}", flush=True)
    
    potential = [k for k in keys if "TMF" in k or "MXF" in k or "MT" in k or "FMF" in k or "TX" in k]
    print(f"Potentials: {potential}", flush=True)

if __name__ == "__main__":
    find_mxf()
