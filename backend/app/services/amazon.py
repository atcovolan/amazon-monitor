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
                timeout=12
            )
            
            if response.status_code == 403:
                raise Exception("Bloqueado pela Amazon (HTTP 403)")
            if response.status_code == 429:
                raise Exception("Muitas requisições (HTTP 429)")
            if response.status_code != 200:
                raise Exception(f"Erro HTTP {response.status_code} ao acessar a Amazon")
                
            if self._looks_like_captcha(response.text):
                raise Exception(
                    "Amazon exigiu verificacao anti-robo (CAPTCHA). "
                    "Provavel bloqueio do IP do servidor (datacenter)."
                )

            return self.parse_html(response.text, normalized, asin)
            
        except Exception as e:
            logger.error(f"Erro ao obter produto da Amazon ({asin}): {e}")
            raise e

    def _looks_like_captcha(self, html: str) -> bool:
        markers = [
            "api-services-support@amazon.com",
            "To discuss automated access",
            "Type the characters you see in this image",
            "Enter the characters you see below",
            "not a robot",
            "/errors/validateCaptcha",
        ]
        low = html.lower()
        return any(m.lower() in low for m in markers)

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
            
        # 2. Extrair Preço (preco principal de compra, ignorando parcelas)
        price = self._extract_price(soup)
                    
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
                    
        # 4. Disponibilidade — multiplos sinais para robustez
        availability = True
        unavail_keywords = (
            "indispon", "out of stock", "não disponível",
            "nao disponivel", "currently unavailable",
            "não temos previsão", "nao temos previsao",
        )
        
        # Checar #availability e #outOfStock (podem coexistir)
        for avail_sel in ("#availability", "#outOfStock"):
            avail_el = soup.select_one(avail_sel)
            if avail_el:
                avail_text = avail_el.get_text(strip=True).lower()
                if any(kw in avail_text for kw in unavail_keywords):
                    availability = False
                    break
        
        # Sinal extra: se nao tem botao de compra, produto indisponivel
        if availability:
            has_add_to_cart = soup.select_one("#add-to-cart-button")
            has_buy_now = soup.select_one("#buy-now-button")
            has_submit_add = soup.select_one("#submit\\.add-to-cart, input[name='submit.add-to-cart']")
            if not has_add_to_cart and not has_buy_now and not has_submit_add:
                # Sem nenhum botao de compra — considerar indisponivel
                availability = False
                
        return {
            "title": title,
            "price": price,
            "image_url": image_url,
            "availability": availability,
            "asin": asin,
            "url": url
        }

    def _price_from_a_price(self, a_price_el) -> Optional[Decimal]:
        # Preco a partir de um <span class="a-price">: usa .a-offscreen se tiver
        # valor; senao reconstroi de .a-price-whole + .a-price-fraction (HTML cru).
        off = a_price_el.select_one(".a-offscreen")
        if off:
            p = self.clean_price(off.get_text(strip=True))
            if p is not None:
                return p
        whole = a_price_el.select_one(".a-price-whole")
        if whole:
            whole_txt = whole.get_text(strip=True)
            frac_el = a_price_el.select_one(".a-price-fraction")
            frac_txt = frac_el.get_text(strip=True) if frac_el else "00"
            sep = "" if whole_txt.endswith((",", ".")) else ","
            return self.clean_price(f"{whole_txt}{sep}{frac_txt}")
        return None

    # Containers conhecidos do buybox — precos fora deles sao de
    # carrosseis, produtos similares, "outros vendedores", etc.
    _BUYBOX_CONTAINERS = (
        "#corePriceDisplay_desktop_feature_div",
        "#corePrice_feature_div",
        "#apex_desktop",
        "#buybox",
        "#buyBoxAccordion",
        "#qualifiedBuybox",
        "#newAccordionRow",
        "#apex_offerDisplay_desktop",
    )

    def _is_inside_buybox(self, el) -> bool:
        """Verifica se o elemento esta dentro de um container do buybox."""
        for container_sel in self._BUYBOX_CONTAINERS:
            if el.find_parent(id=container_sel.lstrip("#")):
                return True
        return False

    def _extract_price(self, soup) -> Optional[Decimal]:
        # Prioriza o preco de compra (priceToPay / base), ignorando parcelas
        # (apex-priceperunit-value) e o preco 'de' riscado (data-a-color=secondary).
        # IMPORTANTE: todos os seletores sao escopados ao buybox para nao
        # capturar precos de carrosseis ou produtos relacionados.
        priority = [
            "#corePriceDisplay_desktop_feature_div span.a-price.priceToPay",
            "#corePrice_feature_div span.a-price.priceToPay",
            "#apex_desktop span.a-price.priceToPay",
            "#buybox span.a-price.priceToPay",
            "span.a-price.priceToPay",
            "span.a-price.apex-pricetopay-value",
            "#corePriceDisplay_desktop_feature_div span.a-price[data-a-color='base']:not(.apex-priceperunit-value)",
            "#corePrice_feature_div span.a-price[data-a-color='base']:not(.apex-priceperunit-value)",
            "#apex_desktop span.a-price[data-a-color='base']:not(.apex-priceperunit-value)",
            "#buybox span.a-price:not(.apex-priceperunit-value)",
        ]
        for sel in priority:
            try:
                els = soup.select(sel)
            except Exception:
                els = []
            for el in els:
                classes = el.get("class") or []
                if "apex-priceperunit-value" in classes:
                    continue
                # Garantir que o elemento esta dentro do buybox
                if not self._is_inside_buybox(el):
                    continue
                p = self._price_from_a_price(el)
                if p is not None and p > 0:
                    return p
        # Fallbacks (layouts antigos), pulando parcelas — tambem escopados
        fallback = [
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#price_inside_buybox",
            "#newBuyBoxPrice",
        ]
        for sel in fallback:
            try:
                els = soup.select(sel)
            except Exception:
                els = []
            for el in els:
                if el.find_parent(class_="apex-priceperunit-value"):
                    continue
                p = self.clean_price(el.get_text(strip=True))
                if p is not None and p > 0:
                    return p
        return None

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
