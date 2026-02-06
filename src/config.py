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
except Exception as e:
    raise ValueError(
        f"配置驗證失敗。請確保 .env 檔案存在並包含所有必要的欄位: {e}"
    ) from e
