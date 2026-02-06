import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

try:
    from src.config import Settings

    print("Config module imported successfully.")
except Exception as e:
    print(f"Config import failed: {e}")

try:
    from src.connection import Trader

    print("Connection module imported successfully.")
except Exception as e:
    print(f"Connection import failed: {e}")

print("Verification script finished.")
