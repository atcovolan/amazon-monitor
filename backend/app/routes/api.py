import os
import uuid
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any

from backend.app.schemas.settings import SettingsUpdate, SettingsResponse
from backend.app.schemas.monitor import (
    MonitorCreate, MonitorUpdate, MonitorResponse,
    ProductTestRequest, ProductTestResponse
)
from backend.app.storage.json_storage import JsonStorage
from backend.app.services.monitor import MonitorService
from backend.app.services.discord import mask_webhook_url
from backend.app.services.amazon import AmazonScraper, normalize_amazon_url, extract_asin

router = APIRouter()

# Dependency injection helpers
# These will be set in main.py on startup
_storage: JsonStorage = None
_monitor_service: MonitorService = None

def get_storage() -> JsonStorage:
    return _storage

def get_monitor_service() -> MonitorService:
    return _monitor_service

@router.get("/settings", response_model=SettingsResponse)
def get_settings(storage: JsonStorage = Depends(get_storage)):
    settings = storage.get_settings()
    # Mask webhook URL for safety. If DISCORD_WEBHOOK env var is set,
    # it is the source of truth and is shown (masked) here.
    masked_settings = {**settings}
    effective_webhook = os.environ.get("DISCORD_WEBHOOK") or settings.get("discord_webhook")
    masked_settings["discord_webhook"] = mask_webhook_url(effective_webhook) if effective_webhook else None
    return masked_settings

@router.put("/settings", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdate, storage: JsonStorage = Depends(get_storage)):
    update_dict = payload.model_dump(exclude_unset=True)
    
    # If the webhook is configured via the DISCORD_WEBHOOK env var, it wins
    # and cannot be overridden from the UI.
    if os.environ.get("DISCORD_WEBHOOK"):
        update_dict.pop("discord_webhook", None)

    # If the user edited webhook and passed masked string, ignore it (keep original)
    if "discord_webhook" in update_dict:
        new_webhook = update_dict["discord_webhook"]
        if new_webhook and "********" in new_webhook:
            # Check if there is an existing webhook to keep
            curr = storage.get_settings().get("discord_webhook")
            if curr:
                update_dict["discord_webhook"] = curr
            else:
                update_dict["discord_webhook"] = None
                
    updated = storage.update_settings(update_dict)
    
    masked_updated = {**updated}
    if updated.get("discord_webhook"):
        masked_updated["discord_webhook"] = mask_webhook_url(updated["discord_webhook"])
    return masked_updated

@router.get("/products", response_model=List[MonitorResponse])
def get_products(storage: JsonStorage = Depends(get_storage)):
    monitors = storage.get_monitors()
    masked_monitors = []
    for m in monitors:
        masked = {**m}
        if m.get("discord_webhook"):
            masked["discord_webhook"] = mask_webhook_url(m["discord_webhook"])
        masked_monitors.append(masked)
    return masked_monitors

@router.post("/products", response_model=MonitorResponse)
def create_product(
    payload: MonitorCreate,
    storage: JsonStorage = Depends(get_storage),
    monitor_srv: MonitorService = Depends(get_monitor_service)
):
    url = payload.url
    normalized_url = normalize_amazon_url(url)
    asin = extract_asin(url)
    if not normalized_url or not asin:
        raise HTTPException(status_code=400, detail="URL da Amazon inválida ou ASIN não encontrado.")
        
    # Check if ASIN already exists
    existing = storage.get_monitors()
    for m in existing:
        if m.get("asin") == asin:
            raise HTTPException(status_code=400, detail=f"Já existe um monitor ativo para o ASIN {asin}.")

    # Scrape initially to get fresh details
    scraper = AmazonScraper()
    try:
        scraped = scraper.get_product(url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao validar produto na Amazon: {str(e)}")

    name = payload.name or scraped["title"]
    
    monitor_id = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    
    monitor_data = {
        "id": monitor_id,
        "name": name,
        "asin": asin,
        "original_url": url,
        "url": normalized_url,
        "image_url": scraped.get("image_url"),
        "target_price": payload.target_price,
        "current_price": float(scraped["price"]) if scraped["price"] is not None else None,
        "previous_price": None,
        "lowest_price": float(scraped["price"]) if scraped["price"] is not None else None,
        "highest_price": float(scraped["price"]) if scraped["price"] is not None else None,
        "check_interval": payload.check_interval,
        "is_active": payload.is_active,
        "alert_triggered": False,
        "use_default_webhook": payload.use_default_webhook,
        "discord_webhook": payload.discord_webhook,
        "availability": scraped["availability"],
        "status": "monitoring" if scraped["availability"] else "out_of_stock",
        "last_checked_at": now_str,
        "next_check_at": None,
        "last_error": None,
        "last_error_at": None,
        "created_at": now_str,
        "updated_at": now_str
    }
    
    created = storage.create_monitor(monitor_data)
    
    # Register history if price exists
    if scraped["price"] is not None:
        storage.append_history(monitor_id, {
            "price": float(scraped["price"]),
            "available": scraped["availability"],
            "checked_at": now_str
        })
        
    monitor_srv.register_or_update_monitor(created)
    
    masked = {**created}
    if created.get("discord_webhook"):
        masked["discord_webhook"] = mask_webhook_url(created["discord_webhook"])
    return masked

@router.get("/products/{product_id}", response_model=MonitorResponse)
def get_product(product_id: str, storage: JsonStorage = Depends(get_storage)):
    monitor = storage.get_monitor(product_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor não encontrado.")
    masked = {**monitor}
    if monitor.get("discord_webhook"):
        masked["discord_webhook"] = mask_webhook_url(monitor["discord_webhook"])
    return masked

@router.put("/products/{product_id}", response_model=MonitorResponse)
def update_product(
    product_id: str,
    payload: MonitorUpdate,
    storage: JsonStorage = Depends(get_storage),
    monitor_srv: MonitorService = Depends(get_monitor_service)
):
    monitor = storage.get_monitor(product_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor não encontrado.")
        
    update_dict = payload.model_dump(exclude_unset=True)
    
    # Handle masked webhook URL
    if "discord_webhook" in update_dict:
        new_webhook = update_dict["discord_webhook"]
        if new_webhook and "********" in new_webhook:
            # Keep original
            update_dict["discord_webhook"] = monitor.get("discord_webhook")
            
    update_dict["updated_at"] = datetime.now().isoformat()
    
    updated = storage.update_monitor(product_id, update_dict)
    if not updated:
         raise HTTPException(status_code=500, detail="Erro ao atualizar monitor.")
         
    # Update scheduler configuration
    monitor_srv.register_or_update_monitor(updated)
    
    masked = {**updated}
    if updated.get("discord_webhook"):
        masked["discord_webhook"] = mask_webhook_url(updated["discord_webhook"])
    return masked

@router.delete("/products/{product_id}")
def delete_product(
    product_id: str,
    storage: JsonStorage = Depends(get_storage),
    monitor_srv: MonitorService = Depends(get_monitor_service)
):
    monitor = storage.get_monitor(product_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor não encontrado.")
        
    monitor_srv.remove_job(product_id)
    storage.delete_monitor(product_id)
    return {"message": "Monitor removido com sucesso."}

@router.post("/products/test", response_model=ProductTestResponse)
def test_product(payload: ProductTestRequest):
    url = payload.url
    asin = extract_asin(url)
    normalized = normalize_amazon_url(url)
    if not asin or not normalized:
        raise HTTPException(status_code=400, detail="URL inválida. Não foi possível extrair o ASIN.")
        
    scraper = AmazonScraper()
    try:
        scraped = scraper.get_product(url)
        return {
            "title": scraped["title"],
            "price": float(scraped["price"]) if scraped["price"] is not None else None,
            "image_url": scraped.get("image_url"),
            "availability": scraped["availability"],
            "asin": scraped["asin"],
            "url": scraped["url"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao consultar a Amazon: {str(e)}")

@router.post("/products/{product_id}/check", response_model=MonitorResponse)
async def check_product_now(
    product_id: str,
    storage: JsonStorage = Depends(get_storage),
    monitor_srv: MonitorService = Depends(get_monitor_service)
):
    monitor = storage.get_monitor(product_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor não encontrado.")
        
    updated = await monitor_srv.check_now(product_id)
    if not updated:
        raise HTTPException(status_code=500, detail="Erro ao realizar a verificação.")
        
    masked = {**updated}
    if updated.get("discord_webhook"):
        masked["discord_webhook"] = mask_webhook_url(updated["discord_webhook"])
    return masked

@router.post("/products/{product_id}/pause", response_model=MonitorResponse)
def pause_product(
    product_id: str,
    storage: JsonStorage = Depends(get_storage),
    monitor_srv: MonitorService = Depends(get_monitor_service)
):
    monitor = storage.get_monitor(product_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor não encontrado.")
        
    monitor_srv.remove_job(product_id)
    updated = storage.update_monitor(product_id, {
        "is_active": False,
        "next_check_at": None,
        "status": "paused",
        "updated_at": datetime.now().isoformat()
    })
    
    masked = {**updated}
    if updated.get("discord_webhook"):
        masked["discord_webhook"] = mask_webhook_url(updated["discord_webhook"])
    return masked

@router.post("/products/{product_id}/resume", response_model=MonitorResponse)
def resume_product(
    product_id: str,
    storage: JsonStorage = Depends(get_storage),
    monitor_srv: MonitorService = Depends(get_monitor_service)
):
    monitor = storage.get_monitor(product_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor não encontrado.")
        
    updated = storage.update_monitor(product_id, {
        "is_active": True,
        "status": "monitoring",
        "updated_at": datetime.now().isoformat()
    })
    
    monitor_srv.register_or_update_monitor(updated)
    
    masked = {**updated}
    if updated.get("discord_webhook"):
        masked["discord_webhook"] = mask_webhook_url(updated["discord_webhook"])
    return masked

@router.get("/products/{product_id}/history")
def get_product_history(product_id: str, storage: JsonStorage = Depends(get_storage)):
    monitor = storage.get_monitor(product_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor não encontrado.")
    return storage.get_history(product_id)
