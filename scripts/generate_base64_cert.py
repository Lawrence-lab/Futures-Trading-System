import base64
import os
import sys

def encode_cert(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    with open(file_path, "rb") as f:
        cert_data = f.read()
        encoded = base64.b64encode(cert_data).decode("utf-8")
        
    print("\n=== Copy the string below (Set CERT_BASE64 in Zeabur) ===")
    print(encoded)
    print("=========================================================\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cert_path = sys.argv[1]
    else:
        # Default fallback or prompt
        possible_paths = [
            "certs/Sinopac.pfx",
            "d:/Lawrence/antigravity/Futures-Trading/certs/Sinopac.pfx"
        ]
        cert_path = next((p for p in possible_paths if os.path.exists(p)), None)
        
        if not cert_path:
            cert_path = input("Please enter path to your .pfx file: ").strip()

    encode_cert(cert_path)
