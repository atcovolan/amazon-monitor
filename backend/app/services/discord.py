import logging
import httpx
from datetime import datetime
from typing import Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

def mask_webhook_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    # Mask webhook token for security
    if "api/webhooks/" in url:
        parts = url.split("api/webhooks/")
        if len(parts) == 2:
            subparts = parts[1].split("/")
            if len(subparts) >= 2:
                # Mask the token part
                masked_token = "********"
                return f"{parts[0]}api/webhooks/{subparts[0]}/{masked_token}"
    return "https://discord.com/api/webhooks/********"

def send_price_alert(
    webhook_url: str,
    product_name: str,
    product_url: str,
    image_url: Optional[str],
    current_price: Decimal,
    previous_price: Optional[Decimal],
    target_price: Decimal,
    currency: str = "BRL"
) -> bool:
    if not webhook_url:
        logger.warning("Discord webhook URL não fornecido.")
        return False
        
    try:
        # Calculate drops
        diff_val = Decimal("0.00")
        diff_pct = Decimal("0.00")
        if previous_price and previous_price > current_price:
            diff_val = previous_price - current_price
            diff_pct = (diff_val / previous_price) * 100
            
        currency_symbol = "R$" if currency == "BRL" else "$"
        
        # Build embed
        embed = {
            "title": "🔥 PREÇO ALVO ATINGIDO!",
            "description": f"**[{product_name}]({product_url})** está abaixo do preço desejado!",
            "url": product_url,
            "color": 16729156, # Red/Orange
            "fields": [
                {
                    "name": "Preço Atual",
                    "value": f"{currency_symbol} {current_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "inline": True
                },
                {
                    "name": "Preço Alvo",
                    "value": f"{currency_symbol} {target_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        if previous_price:
            embed["fields"].append({
                "name": "Preço Anterior",
                "value": f"{currency_symbol} {previous_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "inline": True
            })
            if diff_val > 0:
                embed["fields"].append({
                    "name": "Economia",
                    "value": f"{currency_symbol} {diff_val:,.2f} ({diff_pct:.1f}%)",
                    "inline": False
                })
                
        if image_url:
            embed["thumbnail"] = {"url": image_url}
            
        payload = {
            "embeds": [embed]
        }
        
        response = httpx.post(webhook_url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            logger.info(f"Alerta enviado ao Discord com sucesso para '{product_name}'")
            return True
        else:
            logger.error(f"Erro ao enviar alerta para o Discord (HTTP {response.status_code}): {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Erro ao enviar alerta para o Discord: {e}")
        return False


def send_restock_alert(
    webhook_url: str,
    product_name: str,
    product_url: str,
    image_url: Optional[str],
    current_price: Optional[Decimal],
    target_price: Decimal,
    currency: str = "BRL"
) -> bool:
    """Notifica quando um produto que estava sem estoque volta a ficar disponivel."""
    if not webhook_url:
        logger.warning("Discord webhook URL não fornecido.")
        return False

    try:
        currency_symbol = "R$" if currency == "BRL" else "$"

        price_text = (
            f"{currency_symbol} {current_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if current_price is not None else "não informado"
        )
        target_text = f"{currency_symbol} {target_price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # Cor verde para reposicao
        embed = {
            "title": "📦 PRODUTO DE VOLTA AO ESTOQUE!",
            "description": f"**[{product_name}]({product_url})** voltou a ficar disponível!",
            "url": product_url,
            "color": 5763719,  # Verde
            "fields": [
                {
                    "name": "Preço Atual",
                    "value": price_text,
                    "inline": True
                },
                {
                    "name": "Preço Alvo",
                    "value": target_text,
                    "inline": True
                }
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if current_price is not None and current_price <= target_price:
            embed["fields"].append({
                "name": "✅ Status",
                "value": "Abaixo do preço alvo!",
                "inline": False
            })

        if image_url:
            embed["thumbnail"] = {"url": image_url}

        payload = {"embeds": [embed]}

        response = httpx.post(webhook_url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            logger.info(f"Alerta de reposição enviado ao Discord para '{product_name}'")
            return True
        else:
            logger.error(f"Erro ao enviar alerta de reposição (HTTP {response.status_code}): {response.text}")
            return False

    except Exception as e:
        logger.error(f"Erro ao enviar alerta de reposição para o Discord: {e}")
        return False
