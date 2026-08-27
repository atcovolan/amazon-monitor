import pytest
from decimal import Decimal
from backend.app.services.amazon import extract_asin, normalize_amazon_url, AmazonScraper

def test_extract_asin():
    assert extract_asin("https://www.amazon.com.br/dp/B08PC54QBP?tag=abc") == "B08PC54QBP"
    assert extract_asin("https://www.amazon.com/gp/product/B08PC54QBP") == "B08PC54QBP"
    assert extract_asin("amazon.com.br/dp/B08PC54QBP") == "B08PC54QBP"
    assert extract_asin("https://www.amazon.com.br/dp/B08PC54QBP/") == "B08PC54QBP"
    assert extract_asin("invalid_url") is None

def test_normalize_url():
    assert normalize_amazon_url("https://www.amazon.com.br/dp/B08PC54QBP?tag=abc") == "https://www.amazon.com.br/dp/B08PC54QBP"
    assert normalize_amazon_url("https://www.amazon.com/gp/product/B08PC54QBP") == "https://www.amazon.com/dp/B08PC54QBP"

def test_clean_price():
    scraper = AmazonScraper()
    assert scraper.clean_price("R$ 1.299,90") == Decimal("1299.90")
    assert scraper.clean_price("R$ 599,90") == Decimal("599.90")
    assert scraper.clean_price("R$ 49.99") == Decimal("49.99")
    assert scraper.clean_price("1000,00") == Decimal("1000.00")

def test_parse_html():
    scraper = AmazonScraper()
    mock_html = """
    <html>
      <div id="productTitle">Logitech G Pro X Superlight</div>
      <div id="corePriceDisplay_desktop_feature_div">
        <span class="a-price">
          <span class="a-offscreen">R$ 549,90</span>
        </span>
      </div>
      <div id="availability">
        <span>Em estoque.</span>
      </div>
      <img id="landingImage" src="https://m.media-amazon.com/images/I/img.jpg" />
    </html>
    """
    result = scraper.parse_html(mock_html, "https://www.amazon.com.br/dp/B08PC54QBP", "B08PC54QBP")
    assert result["title"] == "Logitech G Pro X Superlight"
    assert result["price"] == Decimal("549.90")
    assert result["availability"] is True
    assert result["image_url"] == "https://m.media-amazon.com/images/I/img.jpg"
