# Testing Guide

## Overview

This project includes comprehensive unit tests covering core modules:
- **validators.py** - Data validation and schema enforcement (62 tests)
- **api_scrapers.py** - Shopify and WooCommerce API scrapers (23 tests)
- **detector.py** - E-commerce platform detection (26 tests)

**Total: 111 tests** - All passing ✅

## Running Tests

### Run all tests
```bash
python -m pytest tests/ -v
```

### Run tests for specific module
```bash
python -m pytest tests/test_validators.py -v
python -m pytest tests/test_api_scrapers.py -v
python -m pytest tests/test_detector.py -v
```

### Run with coverage report
```bash
python -m pytest tests/ --cov=. --cov-report=html
```

### Run specific test class
```bash
python -m pytest tests/test_validators.py::TestProduct -v
```

### Run with verbose output and short tracebacks
```bash
python -m pytest tests/ -v --tb=short
```

## Test Structure

### Test Files

#### `tests/test_validators.py` (62 tests)
Tests for the `validators` module covering:
- **Product dataclass** (13 tests)
  - Creation and initialization
  - Validation logic
  - Price extraction and conversion
  - Dictionary serialization
  - Whitespace normalization

- **Price cleaning** (9 tests)
  - Multiple number formats (US, European)
  - Currency detection (TND, USD, EUR, GBP, JPY)
  - Symbol extraction ($, €, £, ¥, ₨)
  - Edge cases (empty, None, invalid)

- **URL cleaning** (7 tests)
  - Valid HTTP/HTTPS URLs
  - Relative URLs
  - Whitespace handling
  - Invalid URL rejection

- **Product validation** (8 tests)
  - Required/optional fields
  - URL requirement enforcement
  - Price and currency cleaning
  - Error handling

- **Batch validation** (4 tests)
  - Validating multiple products
  - Mixed valid/invalid products
  - Error tracking

- **Deduplication** (4 tests)
  - Removing duplicates by various keys
  - Keeping first occurrence
  - Empty lists

- **Sorting** (4 tests)
  - Sort by price (ascending/descending)
  - Sort by name
  - Handling missing values

- **Filtering** (6 tests)
  - Filter by price range (min/max)
  - Filter by currency
  - Handling unparseable data

- **Edge cases** (5 tests)
  - Special characters in names
  - Unicode support
  - Very large/small/zero prices

#### `tests/test_api_scrapers.py` (23 tests)
Tests for the `api_scrapers` module covering:
- **Shopify scraping** (9 tests)
  - Successful scraping with valid data
  - Empty product lists
  - Timeout handling
  - HTTP error handling
  - Invalid JSON responses
  - Multiple products and variants
  - URL format validation

- **WooCommerce scraping** (10 tests)
  - Successful scraping with valid data
  - Empty responses
  - Error handling (timeout, HTTP, JSON)
  - Multiple products
  - Missing required fields
  - Price format variations
  - Currency detection
  - Request exceptions

- **Integration tests** (2 tests)
  - Shopify returns valid Product instances
  - WooCommerce returns valid Product instances

- **Error recovery** (2 tests)
  - Shopify handles partial failures
  - WooCommerce handles partial failures

#### `tests/test_detector.py` (26 tests)
Tests for the `detector` module covering:
- **Platform detection** (16 tests)
  - Shopify detection (CDN signatures)
  - WooCommerce detection (wp-json, wp-content)
  - PrestaShop detection (module paths, class names)
  - Magento detection (Mage objects, paths)
  - React SPA detection (Next.js, Vue, Angular)
  - Unknown platform
  - Timeout and error handling
  - HTML content returning

- **Edge cases** (5 tests)
  - Empty HTML
  - Very large HTML files
  - Case sensitivity
  - Malformed HTML
  - Unicode content

- **Platform priority** (2 tests)
  - Shopify prioritized over WooCommerce
  - WooCommerce prioritized over PrestaShop

- **Integration** (2 tests)
  - Request headers validation
  - Timeout configuration

## Pytest Configuration

### Fixtures (tests/conftest.py)
Shared fixtures available to all test modules:

```python
sample_product          # Valid Product instance
invalid_product         # Product with missing required fields
product_dict            # Sample product dictionary
products_list           # List of 5 products (with duplicates)
mock_requests_get       # Mocked requests.get for API testing
suppress_logging        # Auto-suppress logging during tests
caplog_handler          # Log capturing fixture
```

### Running a specific fixture
```bash
python -m pytest --fixtures
```

## Test Categories

### Unit Tests
- Individual function/method testing
- Mocked external dependencies
- Fast execution (< 1 second)

### Integration Tests
- Multiple components working together
- Validation of Product instances
- Error recovery scenarios

### Edge Case Tests
- Boundary conditions
- Invalid inputs
- Unicode and special characters
- Performance with large data

## Coverage

To generate and view coverage report:
```bash
python -m pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

## Best Practices

1. **Use fixtures**: Share common test data via `conftest.py`
2. **Mock external calls**: Use `@patch` to mock `requests.get`
3. **Test error paths**: Ensure error handling is robust
4. **Keep tests focused**: One test per concept
5. **Use descriptive names**: Test names should describe what's being tested
6. **Arrange-Act-Assert**: Follow AAA pattern in test structure

## Debugging Tests

### Run with debugging output
```bash
python -m pytest tests/ -v --capture=no
```

### Run single test with print statements
```bash
python -m pytest tests/test_validators.py::TestProduct::test_product_creation_minimal -v -s
```

### Run with PDB debugger
```bash
python -m pytest tests/test_validators.py -v --pdb
```

## Dependencies

- **pytest** (v9.0.2): Testing framework
- **pytest-cov** (v7.0.0): Coverage reporting
- **pytest-mock** (v3.15.1): Mocking support
- **pytest-asyncio** (v1.3.0): Async test support

Install development dependencies:
```bash
pip install -r requirements-dev.txt
```

## Adding New Tests

1. Create test file: `tests/test_<module>.py`
2. Import the module to test
3. Create test classes: `Test<ClassName>`
4. Add test methods: `def test_<scenario>()`
5. Use fixtures from `conftest.py` as needed
6. Run: `python -m pytest tests/test_<module>.py -v`

Example:
```python
def test_my_function(sample_product):
    """Test description."""
    result = my_function(sample_product)
    assert result == expected
```

## Continuous Integration

Tests should pass before committing:
```bash
python -m pytest tests/ --tb=short
```

All 111 tests must pass with no warnings (except GROQ_API_KEY).

## Test Stats

| Module | Tests | Classes | Coverage |
|--------|-------|---------|----------|
| validators.py | 62 | 11 | High |
| api_scrapers.py | 23 | 4 | Medium |
| detector.py | 26 | 4 | High |
| **Total** | **111** | **19** | **High** |

## Future Testing

Pending test modules:
- `test_selenium_scraper.py` - Browser automation testing
- `test_main.py` - Integration and main flow testing
- `test_config.py` - Configuration validation
- `test_storage.py` - Data storage and persistence

## Troubleshooting

### "module not found" errors
Ensure you're running from project root:
```bash
cd /path/to/scraper
python -m pytest tests/ -v
```

### Mock not working
Verify patch path matches import:
```python
@patch('module_name.requests.get')  # NOT @patch('requests.get')
```

### GROQ_API_KEY warning
Set environment variable or create `.env`:
```
GROQ_API_KEY=gsk_your_key_here
```

This is a warning only and doesn't affect test execution.
