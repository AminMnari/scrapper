"""
tests/test_validators.py — Comprehensive tests for validators module.
"""

import pytest
from decimal import Decimal
from validators import (
    Product,
    clean_price,
    clean_url,
    validate_product,
    validate_batch,
    deduplicate_products,
    sort_products,
    filter_by_price,
    filter_by_currency,
    ValidationError,
)


class TestProduct:
    """Test Product dataclass."""
    
    def test_product_creation_minimal(self):
        """Test creating a product with minimal fields."""
        p = Product(name="Item")
        assert p.name == "Item"
        assert p.price is None
        assert p.currency == "TND"  # Default currency
    
    def test_product_creation_full(self, sample_product):
        """Test creating a product with all fields."""
        assert sample_product.name == "Test Laptop"
        assert sample_product.price == "1299.99"
        assert sample_product.url == "https://example.com/laptop"
        assert sample_product.currency == "USD"
        assert sample_product.description == "A test laptop"
    
    def test_product_whitespace_normalization(self):
        """Test that whitespace is trimmed."""
        p = Product(name="  Item  ", price="  99.99  ", currency="  USD  ")
        assert p.name == "Item"
        assert p.price == "99.99"
        assert p.currency == "USD"
    
    def test_product_is_valid_with_name(self):
        """Test is_valid returns True for valid product."""
        p = Product(name="Item")
        assert p.is_valid() is True
    
    def test_product_is_valid_without_name(self, invalid_product):
        """Test is_valid returns False without name."""
        assert invalid_product.is_valid() is False
    
    def test_product_is_valid_require_url(self):
        """Test is_valid with URL requirement."""
        p = Product(name="Item")
        assert p.is_valid(require_url=False) is True
        assert p.is_valid(require_url=True) is False
        
        p2 = Product(name="Item", url="https://example.com")
        assert p2.is_valid(require_url=True) is True
    
    def test_product_get_price_as_float(self):
        """Test extracting numeric price."""
        p = Product(price="99.99")
        assert p.get_price_as_float() == 99.99
        
        p2 = Product(price="1,234.56")
        assert p2.get_price_as_float() == 1234.56
    
    def test_product_get_price_as_float_european_format(self):
        """Test extracting price with European decimal separator."""
        p = Product(price="99,99")
        assert p.get_price_as_float() == 99.99
    
    def test_product_get_price_as_float_with_currency(self):
        """Test extracting price with currency symbol."""
        p = Product(price="$99.99")
        assert p.get_price_as_float() == 99.99
    
    def test_product_get_price_as_float_none(self):
        """Test price as float with no price."""
        p = Product()
        assert p.get_price_as_float() is None
    
    def test_product_get_price_as_float_invalid(self):
        """Test price as float with invalid price."""
        p = Product(price="not_a_number")
        assert p.get_price_as_float() is None
    
    def test_product_to_dict_excludes_none(self):
        """Test to_dict excludes None values."""
        p = Product(name="Item", price="99.99")
        d = p.to_dict()
        assert "name" in d
        assert "price" in d
        assert "url" not in d  # None values excluded
    
    def test_product_to_dict_all_includes_none(self):
        """Test to_dict_all includes all fields."""
        p = Product(name="Item", price="99.99")
        d = p.to_dict_all()
        assert "name" in d
        assert "price" in d
        assert "url" in d  # All fields included
        assert d["url"] is None


class TestCleanPrice:
    """Test price cleaning function."""
    
    def test_clean_price_simple(self):
        """Test cleaning simple numeric price."""
        price, currency = clean_price("99.99")
        assert price == "99.99"
        assert currency == "TND"  # Default
    
    def test_clean_price_with_tnd(self):
        """Test cleaning price with TND."""
        price, currency = clean_price("120.50 TND")
        assert price == "120.50"
        assert currency == "TND"
    
    def test_clean_price_with_usd(self):
        """Test cleaning price with USD symbol."""
        price, currency = clean_price("$99.99")
        assert price == "99.99"
        assert currency == "USD"
    
    def test_clean_price_with_euro(self):
        """Test cleaning price with EUR symbol."""
        price, currency = clean_price("€19.99")
        assert price == "19.99"
        assert currency == "EUR"
    
    def test_clean_price_european_format(self):
        """Test cleaning European price format."""
        price, currency = clean_price("99,99")
        assert price == "99.99"
    
    def test_clean_price_european_with_code(self):
        """Test cleaning European format with code."""
        price, currency = clean_price("99,99 EUR")
        assert price == "99.99"
        assert currency == "EUR"
    
    def test_clean_price_dt_variant(self):
        """Test cleaning DT currency variant."""
        price, currency = clean_price("100 DT")
        assert currency == "TND"  # DT maps to TND
    
    def test_clean_price_empty(self):
        """Test cleaning empty price."""
        price, currency = clean_price("")
        assert price is None
    
    def test_clean_price_none(self):
        """Test cleaning None price."""
        price, currency = clean_price(None)
        assert price is None


class TestCleanUrl:
    """Test URL cleaning function."""
    
    def test_clean_url_valid_https(self):
        """Test cleaning valid HTTPS URL."""
        url = clean_url("https://example.com/product")
        assert url == "https://example.com/product"
    
    def test_clean_url_valid_http(self):
        """Test cleaning valid HTTP URL."""
        url = clean_url("http://example.com")
        assert url == "http://example.com"
    
    def test_clean_url_relative(self):
        """Test cleaning relative URL."""
        url = clean_url("/products/item")
        assert url == "/products/item"
    
    def test_clean_url_with_whitespace(self):
        """Test cleaning URL with whitespace."""
        url = clean_url("  https://example.com  ")
        assert url == "https://example.com"
    
    def test_clean_url_invalid_no_protocol(self):
        """Test invalid URL without protocol."""
        url = clean_url("example.com/product")
        assert url is None
    
    def test_clean_url_empty(self):
        """Test empty URL."""
        url = clean_url("")
        assert url is None
    
    def test_clean_url_none(self):
        """Test None URL."""
        url = clean_url(None)
        assert url is None


class TestValidateProduct:
    """Test validate_product function."""
    
    def test_validate_product_valid(self, product_dict):
        """Test validating valid product."""
        product = validate_product(product_dict)
        assert product is not None
        assert product.name == "Gaming Mouse"
        assert product.price == "49.99"
    
    def test_validate_product_missing_name(self):
        """Test validation fails without name."""
        data = {"price": "99.99"}
        product = validate_product(data)
        assert product is None
    
    def test_validate_product_require_url(self):
        """Test validation with URL requirement."""
        data = {"name": "Item", "price": "99.99"}
        product = validate_product(data, require_url=True)
        assert product is None
        
        data["url"] = "https://example.com"
        product = validate_product(data, require_url=True)
        assert product is not None
    
    def test_validate_product_cleans_price(self):
        """Test that price is cleaned during validation."""
        data = {"name": "Item", "price": "$99.99"}
        product = validate_product(data)
        assert product is not None
        assert product.price == "99.99"
    
    def test_validate_product_detects_currency(self):
        """Test that currency is detected during validation."""
        data = {"name": "Item", "price": "99.99 EUR"}
        product = validate_product(data)
        assert product is not None
        assert product.currency == "EUR"
    
    def test_validate_product_cleans_url(self):
        """Test that URL is cleaned during validation."""
        data = {"name": "Item", "url": "  https://example.com  "}
        product = validate_product(data)
        assert product is not None
        assert product.url == "https://example.com"
    
    def test_validate_product_invalid_type(self):
        """Test validation with invalid type."""
        with pytest.raises(ValidationError):
            validate_product("not a dict")
    
    def test_validate_product_handles_none_values(self):
        """Test that None values are handled."""
        data = {"name": "Item", "price": None}
        product = validate_product(data)
        assert product is not None
        assert product.price is None


class TestValidateBatch:
    """Test batch validation function."""
    
    def test_validate_batch_all_valid(self):
        """Test batch validation with all valid products."""
        data = [
            {"name": "Item1", "price": "99.99"},
            {"name": "Item2", "price": "49.99"},
        ]
        valid, invalid = validate_batch(data)
        assert len(valid) == 2
        assert len(invalid) == 0
    
    def test_validate_batch_mixed(self):
        """Test batch validation with mixed valid/invalid."""
        data = [
            {"name": "Item1", "price": "99.99"},
            {"price": "49.99"},  # Missing name
            {"name": "Item3", "price": "29.99"},
        ]
        valid, invalid = validate_batch(data)
        assert len(valid) == 2
        assert len(invalid) == 1
        assert invalid[0]["index"] == 1
    
    def test_validate_batch_empty(self):
        """Test batch validation with empty list."""
        valid, invalid = validate_batch([])
        assert len(valid) == 0
        assert len(invalid) == 0
    
    def test_validate_batch_with_require_url(self):
        """Test batch validation with URL requirement."""
        data = [
            {"name": "Item1", "url": "https://example.com"},
            {"name": "Item2"},
        ]
        valid, invalid = validate_batch(data, require_url=True)
        assert len(valid) == 1
        assert len(invalid) == 1


class TestDeduplicateProducts:
    """Test deduplication function."""
    
    def test_deduplicate_by_name(self, products_list):
        """Test deduplicating by name."""
        unique = deduplicate_products(products_list, key="name")
        assert len(unique) == 4  # One duplicate removed
        names = [p.name for p in unique]
        assert names.count("Monitor") == 1
    
    def test_deduplicate_keeps_first(self):
        """Test that deduplication keeps first occurrence."""
        products = [
            Product(name="Item", price="99.99"),
            Product(name="Item", price="49.99"),  # Duplicate, different price
        ]
        unique = deduplicate_products(products, key="name")
        assert len(unique) == 1
        assert unique[0].price == "99.99"  # Kept first
    
    def test_deduplicate_empty_list(self):
        """Test deduplication with empty list."""
        unique = deduplicate_products([])
        assert len(unique) == 0
    
    def test_deduplicate_no_duplicates(self):
        """Test deduplication with no duplicates."""
        products = [
            Product(name="Item1"),
            Product(name="Item2"),
        ]
        unique = deduplicate_products(products, key="name")
        assert len(unique) == 2


class TestSortProducts:
    """Test sorting function."""
    
    def test_sort_by_price_ascending(self):
        """Test sorting by price ascending."""
        products = [
            Product(name="A", price="99.99"),
            Product(name="B", price="29.99"),
            Product(name="C", price="49.99"),
        ]
        sorted_prods = sort_products(products, by="price", reverse=False)
        prices = [p.get_price_as_float() for p in sorted_prods]
        assert prices == [29.99, 49.99, 99.99]
    
    def test_sort_by_price_descending(self):
        """Test sorting by price descending."""
        products = [
            Product(name="A", price="99.99"),
            Product(name="B", price="29.99"),
            Product(name="C", price="49.99"),
        ]
        sorted_prods = sort_products(products, by="price", reverse=True)
        prices = [p.get_price_as_float() for p in sorted_prods]
        assert prices == [99.99, 49.99, 29.99]
    
    def test_sort_by_name(self):
        """Test sorting by name."""
        products = [
            Product(name="Zebra"),
            Product(name="Apple"),
            Product(name="Mango"),
        ]
        sorted_prods = sort_products(products, by="name")
        names = [p.name for p in sorted_prods]
        assert names == ["Apple", "Mango", "Zebra"]
    
    def test_sort_with_missing_prices(self):
        """Test sorting with missing prices."""
        products = [
            Product(name="A", price="99.99"),
            Product(name="B"),  # No price
            Product(name="C", price="49.99"),
        ]
        sorted_prods = sort_products(products, by="price")
        # Products without price should be at end (treated as infinity)
        assert sorted_prods[-1].name == "B"


class TestFilterByPrice:
    """Test price filtering function."""
    
    def test_filter_by_min_price(self):
        """Test filtering with minimum price."""
        products = [
            Product(name="A", price="99.99"),
            Product(name="B", price="29.99"),
            Product(name="C", price="49.99"),
        ]
        filtered = filter_by_price(products, min_price=50)
        assert len(filtered) == 1
        assert filtered[0].name == "A"
    
    def test_filter_by_max_price(self):
        """Test filtering with maximum price."""
        products = [
            Product(name="A", price="99.99"),
            Product(name="B", price="29.99"),
            Product(name="C", price="49.99"),
        ]
        filtered = filter_by_price(products, max_price=50)
        assert len(filtered) == 2
        names = [p.name for p in filtered]
        assert set(names) == {"B", "C"}
    
    def test_filter_by_price_range(self):
        """Test filtering with price range."""
        products = [
            Product(name="A", price="99.99"),
            Product(name="B", price="29.99"),
            Product(name="C", price="49.99"),
        ]
        filtered = filter_by_price(products, min_price=30, max_price=60)
        assert len(filtered) == 1
        assert filtered[0].name == "C"
    
    def test_filter_includes_unparseable_prices(self):
        """Test that unparseable prices are included."""
        products = [
            Product(name="A", price="99.99"),
            Product(name="B", price="invalid"),
        ]
        filtered = filter_by_price(products, min_price=50)
        assert len(filtered) == 2  # Includes B (invalid price)


class TestFilterByCurrency:
    """Test currency filtering function."""
    
    def test_filter_by_currency(self):
        """Test filtering by currency."""
        products = [
            Product(name="A", currency="USD"),
            Product(name="B", currency="EUR"),
            Product(name="C", currency="USD"),
        ]
        filtered = filter_by_currency(products, "USD")
        assert len(filtered) == 2
        assert all(p.currency == "USD" for p in filtered)
    
    def test_filter_by_currency_no_matches(self):
        """Test filtering with no matches."""
        products = [
            Product(name="A", currency="USD"),
            Product(name="B", currency="EUR"),
        ]
        filtered = filter_by_currency(products, "GBP")
        assert len(filtered) == 0


class TestValidationError:
    """Test ValidationError exception."""
    
    def test_validation_error_raised(self):
        """Test that ValidationError is raised appropriately."""
        with pytest.raises(ValidationError):
            validate_product("not a dict")
    
    def test_validation_error_message(self):
        """Test ValidationError message."""
        try:
            validate_product("not a dict")
        except ValidationError as e:
            assert "Expected dict" in str(e)


class TestEdgeCases:
    """Test edge cases and special scenarios."""
    
    def test_product_with_special_characters_in_name(self):
        """Test product with special characters."""
        p = Product(name="Item (Pro) - Model X™")
        assert p.is_valid() is True
    
    def test_unicode_in_product_name(self):
        """Test product with unicode characters."""
        p = Product(name="商品 Produit Articolo")
        assert p.is_valid() is True
    
    def test_very_large_price(self):
        """Test product with very large price."""
        p = Product(name="Item", price="999999999.99")
        price_float = p.get_price_as_float()
        assert price_float == 999999999.99
    
    def test_very_small_price(self):
        """Test product with very small price."""
        p = Product(name="Item", price="0.01")
        price_float = p.get_price_as_float()
        assert price_float == 0.01
    
    def test_zero_price(self):
        """Test product with zero price."""
        p = Product(name="Item", price="0.00")
        price_float = p.get_price_as_float()
        assert price_float == 0.0
