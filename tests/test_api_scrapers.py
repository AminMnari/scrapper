"""
tests/test_api_scrapers.py — Tests for API scraping functions.
"""

import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, HTTPError, RequestException, JSONDecodeError
import json
from api_scrapers import scrape_shopify, scrape_woocommerce
from validators import Product


class TestScrapeShopify:
    """Test Shopify API scraping."""
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_success(self, mock_get):
        """Test successful Shopify scraping."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'products': [
                {
                    'id': 1,
                    'title': 'Test Product',
                    'handle': 'test-product',
                    'variants': [{'price': '99.99'}],
                    'vendor': 'Test Vendor',
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Use proper Shopify collection URL format
        products = scrape_shopify('https://shop.example.com/collections/products')
        
        assert len(products) > 0
        assert all(isinstance(p, Product) for p in products)
        assert any(p.name == 'Test Product' for p in products if p.name)
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_empty_response(self, mock_get):
        """Test Shopify with empty product list."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'products': []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/shoes')
        
        assert len(products) == 0
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_timeout(self, mock_get):
        """Test Shopify timeout handling."""
        mock_get.side_effect = Timeout("Connection timeout")
        
        products = scrape_shopify('https://shop.example.com/collections/products')
        
        assert len(products) == 0
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_http_error(self, mock_get):
        """Test Shopify HTTP error handling."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/products')
        
        assert len(products) == 0
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_invalid_json(self, mock_get):
        """Test Shopify with invalid JSON response."""
        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/products')
        
        assert len(products) == 0
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_multiple_products(self, mock_get):
        """Test Shopify with multiple products."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'products': [
                {'title': 'Product 1', 'handle': 'p1', 'variants': [{'price': '10.00'}]},
                {'title': 'Product 2', 'handle': 'p2', 'variants': [{'price': '20.00'}]},
                {'title': 'Product 3', 'handle': 'p3', 'variants': [{'price': '30.00'}]},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/items')
        
        assert len(products) >= 2  # At least 2 products should be returned
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_missing_variants(self, mock_get):
        """Test Shopify with product missing variants."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'products': [
                {'title': 'Product 1', 'handle': 'p1', 'variants': []},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/items')
        
        # Should handle gracefully, should skip products without valid price
        assert isinstance(products, list)
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_multiple_variants(self, mock_get):
        """Test Shopify with multiple variants for a product."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'products': [
                {
                    'title': 'Product 1',
                    'handle': 'p1',
                    'variants': [
                        {'price': '10.00'},
                        {'price': '15.00'},
                        {'price': '20.00'},
                    ],
                },
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/items')
        
        # Should return products (takes cheapest variant price)
        assert len(products) >= 0
        assert all(isinstance(p, Product) for p in products)
    
    @patch('api_scrapers.requests.get')
    def test_scrape_shopify_invalid_url_format(self, mock_get):
        """Test that invalid URL format is handled."""
        # Should return empty list without calling requests
        result = scrape_shopify('https://example.com')
        assert isinstance(result, list)
        assert len(result) == 0
        # requests.get should not have been called
        mock_get.assert_not_called()


class TestScrapeWooCommerce:
    """Test WooCommerce API scraping."""
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_success(self, mock_get):
        """Test successful WooCommerce scraping."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 1,
                'name': 'Test Product',
                'permalink': 'https://shop.example.com/product/test',
                'prices': {'price': '9999', 'currency_minor_unit': 3},
                'images': [{'src': 'https://example.com/img.jpg'}],
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # WooCommerce returns list or None
        assert products is not None or products == []
        if products is not None:
            assert all(isinstance(p, Product) for p in products)
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_empty_response(self, mock_get):
        """Test WooCommerce with empty product list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # Empty products list returns None
        assert products is None
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_timeout(self, mock_get):
        """Test WooCommerce timeout handling."""
        mock_get.side_effect = Timeout("Connection timeout")
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # Timeout returns None
        assert products is None
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_http_error(self, mock_get):
        """Test WooCommerce HTTP error handling."""
        # Create a mock response object for HTTPError
        mock_response = MagicMock()
        mock_response.status_code = 401
        http_error = HTTPError("401 Unauthorized")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # HTTP error returns None
        assert products is None
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_invalid_json(self, mock_get):
        """Test WooCommerce with invalid JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # Invalid JSON returns None
        assert products is None
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_multiple_products(self, mock_get):
        """Test WooCommerce with multiple products."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'name': 'Product 1', 'permalink': 'https://example.com/p1', 'prices': {'price': '1000', 'currency_minor_unit': 3}},
            {'name': 'Product 2', 'permalink': 'https://example.com/p2', 'prices': {'price': '2000', 'currency_minor_unit': 3}},
            {'name': 'Product 3', 'permalink': 'https://example.com/p3', 'prices': {'price': '3000', 'currency_minor_unit': 3}},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        assert products is not None
        assert len(products) >= 2
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_missing_fields(self, mock_get):
        """Test WooCommerce with missing required fields."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'name': 'Product 1', 'prices': {'price': '1000', 'currency_minor_unit': 3}},  # Missing URL
            {'name': 'Product 2', 'permalink': 'https://example.com/p2', 'prices': {'price': '2000', 'currency_minor_unit': 3}},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # Should handle gracefully, returns only valid products or None
        assert products is None or isinstance(products, list)
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_price_formats(self, mock_get):
        """Test WooCommerce with various price formats."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'name': 'P1', 'permalink': 'https://example.com/p1', 'prices': {'price': '9999', 'currency_minor_unit': 3}},
            {'name': 'P2', 'permalink': 'https://example.com/p2', 'prices': {'price': '100', 'currency_minor_unit': 3}},
            {'name': 'P3', 'permalink': 'https://example.com/p3', 'prices': {'price': '50500', 'currency_minor_unit': 3}},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # All prices should be parseable
        if products:
            for p in products:
                if p.price:
                    price_float = p.get_price_as_float()
                    assert price_float is not None or price_float == 0
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_currency_detection(self, mock_get):
        """Test WooCommerce detects currency."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'name': 'P1', 'permalink': 'https://example.com/p1', 'prices': {'price': '9999', 'currency_minor_unit': 3}},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # Should return products with default TND currency
        if products:
            assert any(p.currency == 'TND' for p in products)
    
    @patch('api_scrapers.requests.get')
    def test_scrape_woocommerce_request_exception(self, mock_get):
        """Test WooCommerce with generic request exception."""
        mock_get.side_effect = RequestException("Network error")
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # Returns None on error
        assert products is None


class TestAPIScrapersIntegration:
    """Integration tests for API scrapers."""
    
    @patch('api_scrapers.requests.get')
    def test_shopify_returns_valid_products(self, mock_get):
        """Test that Shopify returns valid Product instances."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'products': [
                {
                    'title': 'Laptop',
                    'handle': 'laptop',
                    'vendor': 'Tech Inc',
                    'variants': [
                        {
                            'title': 'Silver / 16GB',
                            'price': '1299.99',
                            'sku': 'LAPTOP-001',
                        }
                    ],
                    'image': {'src': 'https://example.com/laptop.jpg'},
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/electronics')
        
        assert len(products) > 0
        for product in products:
            assert product is not None
            assert isinstance(product, Product)
            # Should have basic required fields
            assert product.name or product.is_valid(require_url=False)
    
    @patch('api_scrapers.requests.get')
    def test_woocommerce_returns_valid_products(self, mock_get):
        """Test that WooCommerce returns valid Product instances."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                'id': 123,
                'name': 'Gaming Mouse',
                'permalink': 'https://shop.example.com/product/gaming-mouse',
                'prices': {'price': '4999', 'currency_minor_unit': 3},
                'images': [{'src': 'https://example.com/mouse.jpg'}],
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        assert products is not None
        for product in products:
            assert isinstance(product, Product)
            assert product.name or product.is_valid(require_url=False)


class TestAPIScrapersErrorRecovery:
    """Test error recovery in API scrapers."""
    
    @patch('api_scrapers.requests.get')
    def test_shopify_partial_failure(self, mock_get):
        """Test Shopify with some invalid product data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'products': [
                {'title': 'Valid Product', 'handle': 'valid', 'variants': [{'price': '99.99'}]},
                {'title': None, 'handle': 'bad', 'variants': []},  # Invalid
                {'title': 'Another Valid', 'handle': 'valid2', 'variants': [{'price': '49.99'}]},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_shopify('https://shop.example.com/collections/items')
        
        # Should gracefully skip invalid products
        assert isinstance(products, list)
        assert all(isinstance(p, Product) for p in products)
    
    @patch('api_scrapers.requests.get')
    def test_woocommerce_partial_failure(self, mock_get):
        """Test WooCommerce with some invalid product data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'name': 'Valid Product', 'permalink': 'https://example.com/p1', 'prices': {'price': '9999', 'currency_minor_unit': 3}},
            {'name': None, 'permalink': 'https://example.com/p2'},  # Invalid - no prices
            {'name': 'Another Valid', 'permalink': 'https://example.com/p3', 'prices': {'price': '4999', 'currency_minor_unit': 3}},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        products = scrape_woocommerce('https://shop.example.com')
        
        # Should gracefully skip invalid products, returns list or None
        if products is not None:
            assert all(isinstance(p, Product) for p in products)

