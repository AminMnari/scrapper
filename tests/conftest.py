"""
conftest.py — Shared pytest fixtures and configuration.
"""

import pytest
import logging
from unittest.mock import MagicMock, patch
from validators import Product


@pytest.fixture
def sample_product():
    """Create a sample valid product for testing."""
    return Product(
        name="Test Laptop",
        price="1299.99",
        url="https://example.com/laptop",
        currency="USD",
        description="A test laptop",
        image_url="https://example.com/laptop.jpg"
    )


@pytest.fixture
def invalid_product():
    """Create an invalid product (missing name)."""
    return Product(
        name="",  # Invalid: empty name
        price="99.99",
        url="https://example.com/item"
    )


@pytest.fixture
def product_dict():
    """Create a sample product dictionary."""
    return {
        "name": "Gaming Mouse",
        "price": "49.99",
        "url": "https://example.com/mouse",
        "currency": "USD",
        "category": "Accessories"
    }


@pytest.fixture
def products_list():
    """Create a list of sample products."""
    return [
        Product(name="Laptop", price="999.99"),
        Product(name="Mouse", price="29.99"),
        Product(name="Keyboard", price="79.99"),
        Product(name="Monitor", price="299.99"),
        Product(name="Monitor", price="299.99"),  # Duplicate
    ]


@pytest.fixture
def mock_requests_get(monkeypatch):
    """Mock requests.get for API testing."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"products": []}
    mock_response.status_code = 200
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr("requests.get", mock_get)
    return mock_response


@pytest.fixture(autouse=True)
def suppress_logging():
    """Suppress logging during tests for cleaner output."""
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)


@pytest.fixture
def caplog_handler(caplog):
    """Fixture for capturing log messages."""
    caplog.set_level(logging.INFO)
    return caplog
