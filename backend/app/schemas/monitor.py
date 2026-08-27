from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class MonitorCreate(BaseModel):
    url: str
    target_price: float
    check_interval: int = 300
    use_default_webhook: bool = True
    discord_webhook: Optional[str] = None
    name: Optional[str] = None
    is_active: bool = True

class MonitorUpdate(BaseModel):
    name: Optional[str] = None
    target_price: Optional[float] = None
    check_interval: Optional[int] = None
    use_default_webhook: Optional[bool] = None
    discord_webhook: Optional[str] = None
    is_active: Optional[bool] = None

class MonitorResponse(BaseModel):
    id: str
    name: str
    asin: str
    original_url: str
    url: str
    image_url: Optional[str] = None
    target_price: float
    current_price: Optional[float] = None
    previous_price: Optional[float] = None
    lowest_price: Optional[float] = None
    highest_price: Optional[float] = None
    check_interval: int
    is_active: bool
    alert_triggered: bool
    use_default_webhook: bool
    discord_webhook: Optional[str] = None
    availability: bool
    status: str
    last_checked_at: Optional[str] = None
    next_check_at: Optional[str] = None
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
    created_at: str
    updated_at: str

class ProductTestRequest(BaseModel):
    url: str

class ProductTestResponse(BaseModel):
    title: str
    price: Optional[float] = None
    image_url: Optional[str] = None
    availability: bool
    asin: str
    url: str
