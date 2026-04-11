import os
import time
from dotenv import load_dotenv
import kgisuperpy as kgi

def test_kgi_quote():
    load_dotenv()
    kgi_id = os.environ.get("KGI_ID")
    kgi_pwd = os.environ.get("KGI_PASSWORD")
    
    if not kgi_id or not kgi_pwd:
        print("Error: Missing KGI credentials", flush=True)
        return
        
    print("Logging into KGI...", flush=True)
    api = kgi.login(
        person_id=kgi_id, 
        person_pwd=kgi_pwd, 
        simulation=False
    )
    
    # Wait for login to complete
    time.sleep(5)
    
    def on_tick(tick):
        print(f"KGI Tick: {tick}", flush=True)
        
    def on_bidask(tick):
        print(f"KGI BidAsk: {tick}", flush=True)

    print("Registering callbacks...", flush=True)
    try:
        api.Quote.set_cb_tick(on_tick)
        api.Quote.set_cb_bidask(on_bidask)
        
        # In Taiwan futures, micro TAIFEX is TMF. 
        # Usually KGI uses symbol like "TMF" but we need to know the correct contract code, maybe MTX?
        # Let's try "MTX05" or "TXF" because KGI usually uses different symbols than Shioaji (which uses TMF).
        # We can just try TXF and MTX.
        api.Quote.subscribe_tick("TXF")
        api.Quote.subscribe_bidask("TXF")
        api.Quote.subscribe_tick("WMX")
        api.Quote.subscribe_bidask("WMX")
        api.Quote.subscribe_tick("MTX")
        api.Quote.subscribe_tick("TMF")
    except Exception as e:
        print(f"Error subscribing via Quote: {e}", flush=True)
        
    try:
        api.FutQuote.set_cb_tick(on_tick)
        api.FutQuote.set_cb_bidask(on_bidask)
        api.FutQuote.subscribe_tick("TXF")
        api.FutQuote.subscribe_tick("MTX")
        api.FutQuote.subscribe_tick("TMF")
    except Exception as e:
        print(f"Error subscribing via FutQuote: {e}", flush=True)
        
    print("Waiting 10 seconds for ticks...", flush=True)
    time.sleep(10)
    print("Done.", flush=True)

if __name__ == "__main__":
    test_kgi_quote()
