from pydantic import BaseModel, HttpUrl
from typing import Optional

class SettingsUpdate(BaseModel):
    discord_webhook: Optional[str] = None
    default_check_interval: Optional[int] = 300
    theme: Optional[str] = "dark"
    currency: Optional[str] = "BRL"

class SettingsResponse(BaseModel):
    discord_webhook: Optional[str] = None
    default_check_interval: int
    theme: str
    currency: str
