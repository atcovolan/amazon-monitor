import re
import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests

logger = logging.getLogger(__name__)

def extract_asin(url: str) -> Optional[str]:
    # Regex matching dp/ASIN or gp/product/ASIN
    match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|\?|$|#)', url, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def normalize_amazon_url(url: str) -> Optional[str]:
    asin = extract_asin(url)
    if asin:
        # Detect host (e.g. amazon.com.br, amazon.com)
        host_match = re.search(r'(amazon\.[a-z\.]+)', url, re.IGNORECASE)
        host = host_match.group(1) if host_match else "amazon.com.br"
        return f"https://www.{host}/dp/{asin}"
    return None

class AmazonScraper:
    def __init__(self):
        self.headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "device-memory": "8",
            "downlink": "10",
            "ect": "4g",
            "rtt": "50",
            "sec-ch-device-memory": "8",
            "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": "Mozilla/5.8 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        }

    def get_product(self, url: str) -> Dict[str, Any]:
        normalized = normalize_amazon_url(url)
        if not normalized:
            raise ValueError("URL da Amazon inválida ou ASIN não encontrado.")
            
        asin = extract_asin(url)
        
        try:
            # Impersonate chrome to bypass simple bot protection
            response = requests.get(
                normalized,
                headers=self.headers,
                impersonate="chrome",
                timeout=30
            )
            
            if response.status_code == 403:
                raise Exception("Bloqueado pela Amazon (HTTP 403)")
            if response.status_code == 429:
                raise Exception("Muitas requisições (HTTP 429)")
            if response.status_code != 200:
                raise Exception(f"Erro HTTP {response.status_code} ao acessar a Amazon")
                
            return self.parse_html(response.text, normalized, asin)
            
        except Exception as e:
            logger.error(f"Erro ao obter produto da Amazon ({asin}): {e}")
            raise e

    def parse_html(self, html: str, url: str, asin: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Extrair Titulo
        title = None
        title_el = soup.select_one("#productTitle")
        if title_el:
            title = title_el.get_text(strip=True)
        else:
            title_meta = soup.find("meta", attrs={"name": "title"})
            if title_meta:
                title = title_meta.get("content", "").strip()
        if not title:
            title = f"Produto Amazon {asin}"
            
        # 2. Extrair Preço
        price = None
        price_selectors = [
            "#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen",
            "#corePrice_feature_div span.a-price span.a-offscreen",
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#price_inside_buybox",
            "#newBuyBoxPrice",
            "span.a-color-price"
        ]
        
        for sel in price_selectors:
            price_el = soup.select_one(sel)
            if price_el:
                price_str = price_el.get_text(strip=True)
                parsed_price = self.clean_price(price_str)
                if parsed_price is not None:
                    price = parsed_price
                    break
                    
        # 3. Extrair Imagem
        image_url = None
        img_selectors = [
            "#landingImage",
            "#imgBlkFront",
            "#main-image",
            "meta[property='og:image']"
        ]
        for sel in img_selectors:
            img_el = soup.select_one(sel)
            if img_el:
                if img_el.name == "meta":
                    image_url = img_el.get("content")
                else:
                    # Pode ter data-old-hires ou src ou data-a-dynamic-image
                    image_url = img_el.get("data-old-hires") or img_el.get("src")
                if image_url:
                    break
                    
        # 4. Disponibilidade
        availability = True
        avail_el = soup.select_one("#availability")
        if avail_el:
            avail_text = avail_el.get_text(strip=True).lower()
            if "indispon" in avail_text or "out of stock" in avail_text or "não disponível" in avail_text:
                availability = False
        else:
            outofstock_el = soup.select_one("#outOfStock")
            if outofstock_el:
                availability = False
                
        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "availability": availability,
            "asin": asin,
            "url": url
        }

    def clean_price(self, price_str: str) -> Optional[Decimal]:
        try:
            # R$ 1.299,90 -> 1299.90
            # R$ 1.299,90 (non-breaking spaces, etc.)
            clean_str = price_str.replace("R$", "").replace(" ", "").replace(" ", "").strip()
            
            # Se usa virgula como separador decimal
            if "," in clean_str:
                # Se tiver ponto antes da virgula (R$ 1.299,90)
                if "." in clean_str:
                    clean_str = clean_str.replace(".", "")
                clean_str = clean_str.replace(",", ".")
                
            # Limpar caracteres nao numericos exceto ponto
            clean_str = re.sub(r'[^\d\.]', '', clean_str)
            if clean_str:
                return Decimal(clean_str)
        except Exception as e:
            logger.warning(f"Erro ao parsear preco '{price_str}': {e}")
        return None
