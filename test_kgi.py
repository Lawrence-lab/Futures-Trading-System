import os
import time
from dotenv import load_dotenv
import kgisuperpy as kgi

def test_connection():
    load_dotenv()
    
    kgi_id = os.environ.get("KGI_ID")
    kgi_pwd = os.environ.get("KGI_PASSWORD")
    
    if not kgi_id or not kgi_pwd:
        print("Error: Missing KGI_ID or KGI_PASSWORD in .env", flush=True)
        return
        
    print(f"\n[{time.strftime('%H:%M:%S')}] Testing KGI API login for ID: {kgi_id[:3]}******", flush=True)
    
    try:
        # 1. Login to KGI
        print(f"[{time.strftime('%H:%M:%S')}] Calling KGI login function...", flush=True)
        api = kgi.login(
            person_id=kgi_id, 
            person_pwd=kgi_pwd, 
            simulation=False
        )
        print(f"[{time.strftime('%H:%M:%S')}] Login function called. Waiting for async response from C++ DLL...", flush=True)

        
        # 2. Wait for login to complete and show accounts
        # The DLL prints messages asynchronously, so we must wait long enough
        time.sleep(5)
        
        if hasattr(api, 'show_account'):
            print("\nFetching account list:")
            try:
                # show_account prints to stdout internally if logged in
                api.show_account()
            except Exception as e:
                print(f"Error calling show_account: {e}")
            
        time.sleep(2)
        print("\nTest completed.")
        
    except Exception as e:
        print(f"Exception during login: {e}")

if __name__ == "__main__":
    test_connection()
