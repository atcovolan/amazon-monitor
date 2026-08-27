import asyncio
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.app.storage.json_storage import JsonStorage
from backend.app.services.amazon import AmazonScraper
from backend.app.services.discord import send_price_alert

logger = logging.getLogger(__name__)

class MonitorService:
    def __init__(self, storage: JsonStorage, max_concurrent: int = 3):
        self.storage = storage
        self.scraper = AmazonScraper()
        self.scheduler = AsyncIOScheduler()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.running = False

    def start(self):
        if not self.running:
            self.scheduler.start()
            self.running = True
            logger.info("Scheduler iniciado. Carregando jobs ativos...")
            self._load_active_jobs()

    def shutdown(self):
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Scheduler finalizado.")

    def _load_active_jobs(self):
        monitors = self.storage.get_monitors()
        for m in monitors:
            if m.get("is_active", True):
                self._add_or_update_job(m)

    def _add_or_update_job(self, monitor: Dict[str, Any]):
        monitor_id = monitor["id"]
        interval = monitor.get("check_interval", 300)
        
        # Check if job exists
        job = self.scheduler.get_job(monitor_id)
        if job:
            self.scheduler.remove_job(monitor_id)
            
        # Add new job
        self.scheduler.add_job(
            self.check_monitor_task,
            'interval',
            seconds=interval,
            id=monitor_id,
            args=[monitor_id],
            next_run_time=datetime.now() + timedelta(seconds=5) # Run shortly after start
        )
        logger.info(f"Agendado monitor {monitor_id} ({monitor.get('name')}) a cada {interval}s")
        self._update_next_check_time(monitor_id)

    def remove_job(self, monitor_id: str):
        if self.scheduler.get_job(monitor_id):
            self.scheduler.remove_job(monitor_id)
            logger.info(f"Removido job do scheduler para monitor {monitor_id}")

    def _update_next_check_time(self, monitor_id: str):
        job = self.scheduler.get_job(monitor_id)
        if job and job.next_run_time:
            self.storage.update_monitor(monitor_id, {
                "next_check_at": job.next_run_time.isoformat()
            })

    async def check_monitor_task(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        # concurrency control using Semaphore
        async with self.semaphore:
            return await self._execute_check(monitor_id)

    async def _execute_check(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        monitor = self.storage.get_monitor(monitor_id)
        if not monitor:
            logger.warning(f"Tentativa de rodar monitor inexistente {monitor_id}")
            self.remove_job(monitor_id)
            return None
            
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Verificando {monitor['asin']} - {monitor['name']}")
        
        url = monitor["url"]
        target_price = Decimal(str(monitor["target_price"]))
        alert_triggered = monitor.get("alert_triggered", False)
        
        update_data = {
            "last_checked_at": datetime.now().isoformat()
        }
        
        try:
            # Run scraper in a thread pool executor since it uses blocking requests
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self.scraper.get_product, url)
            
            scraped_price = result["price"] # Decimal or None
            availability = result["availability"]
            
            update_data["availability"] = availability
            update_data["last_error"] = None
            update_data["last_error_at"] = None
            
            if scraped_price is not None:
                current_price = Decimal(str(scraped_price))
                previous_price = Decimal(str(monitor.get("current_price"))) if monitor.get("current_price") else None
                
                update_data["previous_price"] = float(previous_price) if previous_price else None
                update_data["current_price"] = float(current_price)
                
                # Update high/low/average/etc. using history
                history_entry = {
                    "price": float(current_price),
                    "available": availability,
                    "checked_at": datetime.now().isoformat()
                }
                self.storage.append_history(monitor_id, history_entry)
                
                history = self.storage.get_history(monitor_id)
                valid_prices = [Decimal(str(h["price"])) for h in history if h.get("price") is not None]
                
                if valid_prices:
                    update_data["lowest_price"] = float(min(valid_prices))
                    update_data["highest_price"] = float(max(valid_prices))
                
                # Check target price drop
                if current_price <= target_price:
                    if not alert_triggered:
                        # Send alert
                        settings = self.storage.get_settings()
                        default_webhook = os.environ.get("DISCORD_WEBHOOK") or settings.get("discord_webhook")
                        webhook = default_webhook
                        if not monitor.get("use_default_webhook"):
                            webhook = monitor.get("discord_webhook") or default_webhook
                            
                        if webhook:
                            # Send in background or awaitable
                            send_price_alert(
                                webhook_url=webhook,
                                product_name=monitor["name"],
                                product_url=monitor["url"],
                                image_url=result.get("image_url") or monitor.get("image_url"),
                                current_price=current_price,
                                previous_price=previous_price,
                                target_price=target_price,
                                currency=settings.get("currency", "BRL")
                            )
                        else:
                            logger.warning(f"Webhook não configurado para enviar alerta do monitor {monitor_id}")
                        update_data["alert_triggered"] = True
                else:
                    # Reset alert trigger when price goes back above target
                    update_data["alert_triggered"] = False
                    
                update_data["status"] = "target_reached" if current_price <= target_price else "monitoring"
                logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Produto {monitor['asin']} verificado. Preço: {current_price}. Status: {update_data['status']}")
            else:
                update_data["status"] = "out_of_stock" if not availability else "error"
                update_data["last_error"] = "Preço não encontrado na página"
                update_data["last_error_at"] = datetime.now().isoformat()
                logger.warning(f"[{datetime.now().strftime('%H:%M:%S')}] Preço não encontrado para {monitor['asin']}")
                
        except Exception as e:
            update_data["status"] = "error"
            update_data["last_error"] = str(e)
            update_data["last_error_at"] = datetime.now().isoformat()
            logger.error(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR {monitor['asin']} - {e}")
            
        # Update details in storage
        updated = self.storage.update_monitor(monitor_id, update_data)
        self._update_next_check_time(monitor_id)
        return updated

    async def check_now(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        # Manual check ignores scheduler, run immediately
        return await self._execute_check(monitor_id)

    def register_or_update_monitor(self, monitor: Dict[str, Any]):
        if monitor.get("is_active", True):
            self._add_or_update_job(monitor)
        else:
            self.remove_job(monitor["id"])
            self.storage.update_monitor(monitor["id"], {"next_check_at": None})
