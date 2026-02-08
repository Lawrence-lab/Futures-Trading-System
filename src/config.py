"""
專案配置模組
負責讀取並驗證環境變數設定。
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    api_key: str = Field(..., description="Shioaji API 金鑰")
    secret_key: str = Field(..., description="Shioaji Secret Key")
    cert_path: str = Field(..., description="PFX 憑證路徑")
    cert_pass: str = Field(..., description="PFX 憑證密碼")
    simulation: bool = Field(False, description="是否使用模擬環境")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


try:
    settings = Settings()
    # Print loaded configuration (masking sensitive data)
    print("Configuration loaded successfully.")
    print(f"Simulation Mode: {settings.simulation}")
    print(f"Cert Path: {settings.cert_path}")
except Exception as e:
    import os
    missing_vars = []
    for field in Settings.model_fields.keys():
        if field.upper() not in os.environ and field not in ['simulation']: # simulation has default
             # Pydantic case-insensitivity might handle this, but explicit check helps debugging
             pass
    
    print(f"CRITICAL ERROR: Failed to load configuration. Error: {e}")
    print("Please ensure the following environment variables are set in Zeabur:")
    print(" - API_KEY")
    print(" - SECRET_KEY")
    print(" - CERT_PATH")
    print(" - CERT_PASS")
    raise ValueError(
        f"配置驗證失敗。請確保 .env 檔案存在或環境變數已設定: {e}"
    ) from e
