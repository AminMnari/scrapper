"""
tests/test_detector.py — Tests for platform detection functionality.
"""

import pytest
from unittest.mock import patch, MagicMock
from requests.exceptions import Timeout, RequestException
from detector import detect_platform, detect_content_type


class TestDetectPlatform:
    """Test platform detection."""
    
    @patch('detector.requests.get')
    def test_detect_shopify(self, mock_get):
        """Test detecting Shopify platform."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <script src="https://cdn.shopify.com/shop.js"></script>
            <script>Shopify.theme = {}</script>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'shopify'
        assert 'shopify' in html.lower()
    
    @patch('detector.requests.get')
    def test_detect_shopify_with_files_cdn(self, mock_get):
        """Test detecting Shopify by files.shopify.com CDN."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <link rel="stylesheet" href="https://cdn.shopify.com/s/files/style.css">
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'shopify'
    
    @patch('detector.requests.get')
    def test_detect_woocommerce(self, mock_get):
        """Test detecting WooCommerce platform."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <link rel="alternate" type="application/json" href="https://example.com/wp-json/">
            <script src="/wp-content/plugins/woocommerce.js"></script>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'woocommerce'
    
    @patch('detector.requests.get')
    def test_detect_woocommerce_with_wp_json(self, mock_get):
        """Test detecting WooCommerce by wc store endpoint."""
        mock_response = MagicMock()
        mock_response.text = '<html><link href="/wp-json/wc/store/products"></html>'
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'woocommerce'

    @patch('detector.requests.get')
    def test_detect_wordpress(self, mock_get):
        """Test detecting WordPress platform separately from WooCommerce."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <meta name="generator" content="WordPress 6.5" />
            <link rel="stylesheet" href="/wp-content/themes/theme/style.css" />
        </html>
        """
        mock_get.return_value = mock_response

        platform, _html = detect_platform('https://blog.example.com')

        assert platform == 'wordpress'
    
    @patch('detector.requests.get')
    def test_detect_prestashop(self, mock_get):
        """Test detecting PrestaShop platform."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <script src="/modules/ps_mainmenu/views/js/menu.js"></script>
            <div class="id_product">123</div>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'prestashop'
    
    @patch('detector.requests.get')
    def test_detect_prestashop_by_name(self, mock_get):
        """Test detecting PrestaShop by name."""
        mock_response = MagicMock()
        mock_response.text = '<html><!-- Powered by PrestaShop --></html>'
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'prestashop'
    
    @patch('detector.requests.get')
    def test_detect_magento(self, mock_get):
        """Test detecting Magento platform."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <script>
                var MAGE_URLS = {};
                Mage.Cookies.path = '/';
            </script>
            <link rel="stylesheet" href="/skin/frontend/base/default/css/style.css">
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'magento'
    
    @patch('detector.requests.get')
    def test_detect_magento_by_class(self, mock_get):
        """Test detecting Magento by class name."""
        mock_response = MagicMock()
        mock_response.text = '<html><div class="Magento_Catalog">Content</div></html>'
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'magento'
    
    @patch('detector.requests.get')
    def test_detect_react_spa(self, mock_get):
        """Test detecting React SPA platform."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <div id="root"></div>
            <script src="/_next/static/chunks/main.js"></script>
            <script src="/_next/static/chunks/pages/products.js"></script>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'react_spa'
    
    @patch('detector.requests.get')
    def test_detect_react_spa_by_next_data(self, mock_get):
        """Test detecting React SPA by __NEXT_DATA__."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <script id="__NEXT_DATA__" type="application/json">{}</script>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'react_spa'
    
    @patch('detector.requests.get')
    def test_detect_vue_spa(self, mock_get):
        """Test detecting Vue SPA platform."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <div id="app"></div>
            <script src="/js/app-bundle.js"></script>
            <script src="/js/vue.js"></script>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'react_spa'
    
    @patch('detector.requests.get')
    def test_detect_unknown_platform(self, mock_get):
        """Test detecting unknown platform."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <head><title>Custom Shop</title></head>
            <body>Welcome to our shop</body>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'unknown'
    
    @patch('detector.requests.get')
    def test_detect_platform_timeout(self, mock_get):
        """Test handling request timeout during detection."""
        mock_get.side_effect = Timeout("Connection timeout")
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'unknown'
        assert html == ''
    
    @patch('detector.requests.get')
    def test_detect_platform_request_error(self, mock_get):
        """Test handling request error during detection."""
        mock_get.side_effect = RequestException("Network error")
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'unknown'
        assert html == ''
    
    @patch('detector.requests.get')
    def test_detect_platform_returns_html(self, mock_get):
        """Test that detect_platform returns HTML content."""
        test_html = '<html><div>Test Content</div></html>'
        mock_response = MagicMock()
        mock_response.text = test_html
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert html == test_html
    
    @patch('detector.requests.get')
    def test_detect_platform_with_multiple_signatures(self, mock_get):
        """Test detection when multiple signatures are present."""
        # Should detect the first matching signature (Shopify in this case)
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <script src="https://cdn.shopify.com/shop.js"></script>
            <script src="/wp-content/plugins/plugin.js"></script>
            <div class="Magento_Catalog">Content</div>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        # Shopify is detected first
        assert platform == 'shopify'
    
    @patch('detector.requests.get')
    def test_detect_platform_platform_json_signature(self, mock_get):
        """Test detecting Shopify via platform JSON signature."""
        mock_response = MagicMock()
        mock_response.text = '<html><script>var data = {"platform":"shopify"}</script></html>'
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'shopify'


class TestDetectPlatformEdgeCases:
    """Test edge cases in platform detection."""
    
    @patch('detector.requests.get')
    def test_empty_html(self, mock_get):
        """Test detection with empty HTML."""
        mock_response = MagicMock()
        mock_response.text = ''
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'unknown'
    
    @patch('detector.requests.get')
    def test_very_large_html(self, mock_get):
        """Test detection with large HTML content."""
        # Generate large HTML
        large_html = '<html>' + '<div>Product</div>' * 10000
        large_html += '<script src="https://cdn.shopify.com/shop.js"></script>'
        large_html += '</html>'
        
        mock_response = MagicMock()
        mock_response.text = large_html
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'shopify'
    
    @patch('detector.requests.get')
    def test_case_sensitive_detection(self, mock_get):
        """Test that detection is case-sensitive for some signatures."""
        # "WooCommerce" with capital letters should be detected
        mock_response = MagicMock()
        mock_response.text = '<html><!-- Powered by WooCommerce --></html>'
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        # Should detect WooCommerce (capital W and C)
        assert platform == 'woocommerce'
    
    @patch('detector.requests.get')
    def test_malformed_html(self, mock_get):
        """Test detection with malformed HTML."""
        mock_response = MagicMock()
        mock_response.text = '<html><body<div>broken << html >< /div</body'
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        # Should handle gracefully without crashing
        assert isinstance(platform, str)
        assert isinstance(html, str)
    
    @patch('detector.requests.get')
    def test_unicode_in_html(self, mock_get):
        """Test detection with unicode content."""
        mock_response = MagicMock()
        mock_response.text = '<html><body>商品 продукты αγαθά</body></html>'
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        # Should handle unicode without crashes
        assert isinstance(platform, str)


class TestDetectPlatformPriority:
    """Test platform detection priority when multiple platforms match."""
    
    @patch('detector.requests.get')
    def test_shopify_prioritized_over_woocommerce(self, mock_get):
        """Test that Shopify is detected before WooCommerce."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <script src="https://cdn.shopify.com/shop.js"></script>
            <script src="/wp-content/plugins/plugin.js"></script>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'shopify'
    
    @patch('detector.requests.get')
    def test_woocommerce_prioritized_over_prestashop(self, mock_get):
        """Test that WooCommerce is detected before PrestaShop."""
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <script src="/wp-content/plugins/woocommerce/assets/js/frontend.js"></script>
            <script src="/modules/ps_mainmenu/views/js/menu.js"></script>
        </html>
        """
        mock_get.return_value = mock_response
        
        platform, html = detect_platform('https://shop.example.com')
        
        assert platform == 'woocommerce'


class TestDetectPlatformIntegration:
    """Integration tests for platform detection."""
    
    @patch('detector.requests.get')
    def test_request_headers_sent(self, mock_get):
        """Test that proper headers are sent in the request."""
        mock_response = MagicMock()
        mock_response.text = '<html></html>'
        mock_get.return_value = mock_response
        
        detect_platform('https://shop.example.com')
        
        # Verify that requests.get was called
        mock_get.assert_called_once()
        # Check that headers were passed
        assert mock_get.call_args[1]['headers'] is not None
        assert 'User-Agent' in mock_get.call_args[1]['headers']
    
    @patch('detector.requests.get')
    def test_timeout_configuration(self, mock_get):
        """Test that request timeout is configured."""
        mock_response = MagicMock()
        mock_response.text = '<html></html>'
        mock_get.return_value = mock_response
        
        detect_platform('https://shop.example.com')
        
        # Verify that timeout was set
        assert mock_get.call_args[1]['timeout'] is not None


class TestDetectContentType:
    def test_detect_ecommerce(self):
        html = "<html><button>Add to cart</button></html>"
        assert detect_content_type(html) == "ecommerce"

    def test_detect_jobs(self):
        html = "<html><a>Apply now</a><div>job description</div></html>"
        assert detect_content_type(html) == "jobs"

    def test_detect_real_estate(self):
        html = "<html><span>3 bedrooms</span><span>2 bathrooms</span></html>"
        assert detect_content_type(html) == "real_estate"

    def test_detect_news(self):
        html = "<html><article><h1>Breaking news</h1></article></html>"
        assert detect_content_type(html) == "news"

    def test_detect_unknown(self):
        html = "<html><div>generic content</div></html>"
        assert detect_content_type(html) == "unknown"
