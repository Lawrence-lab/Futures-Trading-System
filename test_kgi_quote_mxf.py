import os
import time
from dotenv import load_dotenv
import kgisuperpy as kgi

def test_kgi_quote_mxf():
    load_dotenv()
    kgi_id = os.environ.get("KGI_ID")
    kgi_pwd = os.environ.get("KGI_PASSWORD")
    
    api = kgi.login(
        person_id=kgi_id, 
        person_pwd=kgi_pwd, 
        simulation=False
    )
    time.sleep(5)
    
    def on_tick(tick):
        # Let's see if we can convert it to dict or getattr
        print(f"KGI MXF Tick: {tick}", flush=True)
        try:
            d = tick.__dict__ if hasattr(tick, "__dict__") else dict(tick)
            print(f"Dict form: {d}", flush=True)
        except Exception as e:
            print(f"Cannot dict: getattr close = {getattr(tick, 'close', None)}", flush=True)
        
    def on_bidask(tick):
        print(f"KGI MXF BidAsk: {tick}", flush=True)

    try:
        api.FutQuote.set_cb_tick(on_tick)
        api.FutQuote.set_cb_bidask(on_bidask)
        # test MXF (Micro TAIFEX)
        api.FutQuote.subscribe_tick("MXF")
        api.FutQuote.subscribe_bidask("MXF")
    except Exception as e:
        print(f"Error subscribing via FutQuote: {e}", flush=True)
        
    print("Waiting 10 seconds...", flush=True)
    time.sleep(10)

if __name__ == "__main__":
    test_kgi_quote_mxf()
