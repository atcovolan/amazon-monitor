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

# Limite rigido para um unico scraping. Alem disso assumimos que a
# requisicao travou (bloqueio/desafio da Amazon ao IP do servidor) e abortamos.
SCRAPE_TIMEOUT_SECONDS = 25

# Trechos que indicam bloqueio/banimento da Amazon ao IP do servidor.
BLOCK_MARKERS = ("403", "429", "captcha", "robo", "rob\u00f4", "bloque",
                 "verificacao", "verifica\u00e7\u00e3o", "anti-robo")


def _scrape_product_worker(url):
    # Executa em um PROCESSO separado, para que um scraping travado/bloqueante
    # nunca consiga congelar o event loop do app. Cria seu proprio scraper.
    scraper = AmazonScraper()
    return scraper.get_product(url)


class MonitorService:
    def __init__(self, storage: JsonStorage, max_concurrent: int = 3):
        self.storage = storage
        self.scraper = AmazonScraper()
        self.scheduler = AsyncIOScheduler()
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.running = False

    async def scrape_product(self, url):
        # Scraping numa thread com timeout. O timeout do proprio curl (amazon.py)
        # impede que a thread fique presa; nunca roda na thread do event loop.
        loop = asyncio.get_running_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, _scrape_product_worker, url),
            timeout=SCRAPE_TIMEOUT_SECONDS,
        )

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
            # Scraping em processo separado com timeout rigido (nunca trava o app).
            result = await self.scrape_product(url)
            
            scraped_price = result["price"] # Decimal or None
            availability = result["availability"]
            
            update_data["availability"] = availability
            update_data["last_error"] = None
            update_data["last_error_at"] = None
            
            # --- FIX: Produto sem estoque nao atualiza preco nem dispara alerta ---
            if not availability:
                update_data["status"] = "out_of_stock"
                # Grava no historico apenas a indisponibilidade, sem preco
                history_entry = {
                    "price": None,
                    "available": False,
                    "checked_at": datetime.now().isoformat()
                }
                self.storage.append_history(monitor_id, history_entry)
                logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Produto {monitor['asin']} indisponivel - alerta suprimido")
            elif scraped_price is not None:
                current_price = Decimal(str(scraped_price))
                previous_price = Decimal(str(monitor.get("current_price"))) if monitor.get("current_price") else None
                
                # --- FIX: Validacao de sanidade do preco ---
                # Se ja temos historico de precos, rejeitar coletas absurdamente
                # baixas (< 20% do menor preco conhecido). Provavel erro de
                # scraping (parcela, acessorio, elemento errado na pagina).
                history = self.storage.get_history(monitor_id)
                valid_prices = [Decimal(str(h["price"])) for h in history if h.get("price") is not None]
                
                price_seems_valid = True
                if valid_prices and len(valid_prices) >= 3:
                    lowest_known = min(valid_prices)
                    if lowest_known > 0 and current_price < lowest_known * Decimal("0.2"):
                        price_seems_valid = False
                        update_data["status"] = "error"
                        update_data["last_error"] = (
                            f"Preco coletado R$ {current_price:.2f} parece incorreto "
                            f"(menor historico: R$ {lowest_known:.2f}). Coleta descartada."
                        )
                        update_data["last_error_at"] = datetime.now().isoformat()
                        logger.warning(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Preco suspeito para {monitor['asin']}: "
                            f"R$ {current_price} vs minimo historico R$ {lowest_known} - descartado"
                        )
                
                if price_seems_valid:
                    update_data["previous_price"] = float(previous_price) if previous_price else None
                    update_data["current_price"] = float(current_price)
                    
                    # Update high/low/average/etc. using history
                    history_entry = {
                        "price": float(current_price),
                        "available": availability,
                        "checked_at": datetime.now().isoformat()
                    }
                    self.storage.append_history(monitor_id, history_entry)
                    
                    # Recalcular com o historico atualizado
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
                    logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Produto {monitor['asin']} verificado. Preco: {current_price}. Status: {update_data['status']}")
            else:
                update_data["status"] = "error"
                update_data["last_error"] = "Preco nao encontrado na pagina"
                update_data["last_error_at"] = datetime.now().isoformat()
                logger.warning(f"[{datetime.now().strftime('%H:%M:%S')}] Preco nao encontrado para {monitor['asin']}")
                
        except Exception as e:
            update_data["status"] = "error"
            update_data["last_error"] = str(e)
            update_data["last_error_at"] = datetime.now().isoformat()
            logger.error(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR {monitor['asin']} - {e}")
            
        # Registrar no log do monitor (feed global do dashboard)
        self._log_check_result(monitor, update_data)

        # Update details in storage
        updated = self.storage.update_monitor(monitor_id, update_data)
        self._update_next_check_time(monitor_id)
        return updated

    def _log_check_result(self, monitor: Dict[str, Any], update_data: Dict[str, Any]) -> None:
        status = update_data.get("status")
        err = update_data.get("last_error")
        if err:
            low = str(err).lower()
            blocked = any(m in low for m in BLOCK_MARKERS)
            level = "blocked" if blocked else "error"
            message = str(err)
        elif status == "out_of_stock":
            level = "warning"
            message = "Indisponivel / sem estoque"
        else:
            price = update_data.get("current_price")
            price_txt = ("R$ %.2f" % price).replace(".", ",") if price is not None else "preco OK"
            extra = " - PRECO ALVO ATINGIDO" if status == "target_reached" else ""
            level = "success"
            message = f"Consulta OK - {price_txt}{extra}"
        try:
            self.storage.append_log({
                "time": datetime.now().isoformat(),
                "monitor_id": monitor.get("id"),
                "name": monitor.get("name", "?"),
                "asin": monitor.get("asin", "?"),
                "level": level,
                "message": message,
            })
        except Exception as e:
            logger.error(f"Falha ao gravar log do monitor: {e}")

    async def check_now(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        # Manual check ignores scheduler, run immediately
        return await self._execute_check(monitor_id)

    def register_or_update_monitor(self, monitor: Dict[str, Any]):
        if monitor.get("is_active", True):
            self._add_or_update_job(monitor)
        else:
            self.remove_job(monitor["id"])
            self.storage.update_monitor(monitor["id"], {"next_check_at": None})
