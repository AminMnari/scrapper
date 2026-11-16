# Data Validation & Schema Enforcement - Implementation Summary

## Overview
Implemented comprehensive data validation and schema enforcement for the scraper. All scraped data now flows through a validated Product dataclass with type hints and detailed validation logic.

---

## New Module: `validators.py`

### Product Dataclass
```python
@dataclass
class Product:
    name: str = ""
    price: Optional[Union[str, float]] = None
    url: Optional[str] = None
    currency: str = "TND"
    category: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
```

**Key Features:**
- All fields automatically normalized on initialization (whitespace stripped)
- Type-safe with proper type hints
- Flexible initialization (all fields optional for partial data)
- Immutable structure via dataclass

### Product Instance Methods

| Method | Purpose |
|--------|---------|
| `is_valid(require_url)` | Check if product has required fields |
| `get_price_as_float()` | Extract numeric price (handles multiple formats) |
| `to_dict()` | Convert to dict, excluding None values |
| `to_dict_all()` | Convert to dict, including all fields |

### Validation Functions

#### `validate_product(data, require_url=False)`
- Converts raw dict to validated Product
- Handles price cleaning and currency detection
- Returns None if validation fails
- Tracks errors with logging

#### `clean_price(price_text, currency="TND")`
- Normalizes prices from any format
- Detects currency symbols (TND, $, €, £, ¥)
- Handles multiple decimal separators (. and ,)
- Returns tuple: (cleaned_price, detected_currency)

Example:
```python
clean_price("120,50 TND")        # → ("120.50", "TND")
clean_price("$29.99")             # → ("29.99", "USD")
clean_price("€19,99")             # → ("19.99", "EUR")
```

#### `validate_batch(products, require_url=False)`
- Validates multiple products
- Returns: (valid_list, invalid_list with reasons)
- Logs summary statistics

#### `deduplicate_products(products, key='name')`
- Removes duplicates based on key field
- Keeps first occurrence
- Logs deduplication statistics

#### `sort_products(products, by='price', reverse=False)`
- Sort by field ('price', 'name', 'url')
- Price sorting uses numeric values
- Handles missing prices gracefully

#### `filter_by_price(products, min_price, max_price)`
- Filter products within price range
- Includes products with unparseable prices
- Logs filtering statistics

#### `filter_by_currency(products, currency)`
- Filter by currency code (e.g., 'USD', 'EUR', 'TND')
- Logs filtering statistics

---

## Integration with Scrapers

### 1. API Scrapers (`api_scrapers.py`)
**Before:** Returned `list[dict]`  
**After:** Returns `list[Product]`

```python
# Scrape Shopify
products: list[Product] = scrape_shopify(url, max_pages=1)

# Scrape WooCommerce
products: list[Product] = scrape_woocommerce(url, max_pages=1)
```

**Changes:**
- Each scraped item validated before adding to list
- Currency detected and stored
- URL validation and normalization
- Price cleaning applied

### 2. Selenium Scraper (`selenium_scraper.py`)
**Before:** Returned `list[dict]`  
**After:** Returns `list[Product]`

```python
products: list[Product] = scrape_with_selenium(url, max_pages=1)
```

**Changes:**
- Each DOM-extracted product validated
- Price cleaning via clean_price()
- Invalid products silently skipped
- Page product count logged

### 3. SPA Scraper (`spa_scraper.py`)
**Before:** Returned `list[dict]`  
**After:** Returns `list[Product]`

```python
products: list[Product] = scrape_spa(driver, url)
```

**Changes:**
- XHR-intercepted products validated
- DOM fallback also returns Products
- Currency detection in embedded JSON

### 4. Main Entry Point (`main.py`)

**Updated type hints:**
```python
def run(url: str, max_pages: int = 1) -> list[Product]:
    ...

def save(products: list[Product], filename: str) -> None:
    # Converts Products to dicts for JSON serialization
    products_list = [p.to_dict() for p in products]
    json.dump(products_list, f)

def preview(products: list[Product], n: int = 5) -> None:
    for p in products[:n]:
        print(f"{p.name} - {p.price} {p.currency}")
```

**Post-processing pipeline:**
1. Scrape using appropriate strategy → `list[Product]`
2. Deduplicate by name → fewer duplicates
3. Save to JSON (Products → dicts)
4. Preview first N products

---

## Benefits

### Data Quality
- ✅ **Type Safety** - IDE autocomplete and type checking
- ✅ **Validation** - No invalid data leaks through
- ✅ **Normalization** - Consistent data format
- ✅ **Error Tracking** - Know why data was rejected

### Flexibility
- ✅ **Multi-format Support** - Prices: "99.99", "99,99", "99.99 €", etc.
- ✅ **Currency Detection** - Automatic currency code detection
- ✅ **Partial Data** - Optional fields don't crash validation
- ✅ **Filtering & Sorting** - Built-in utility functions

### Maintainability
- ✅ **Single Source of Truth** - Product schema defined once
- ✅ **Clear Intent** - Type hints document expectations
- ✅ **Logging** - Debug data issues easily
- ✅ **Extensible** - Add fields later without breaking

---

## Example Usage

### Basic Extraction
```python
from main import run, save

# Scrape products
products = run("https://example.com/shop", max_pages=1)

# All products are validated Product instances
for p in products:
    print(f"{p.name}: {p.price} {p.currency}")
    
    # Extract numeric price for calculations
    if p.price:
        numeric_price = p.get_price_as_float()
        print(f"Numeric: {numeric_price}")
```

### Advanced Processing
```python
from validators import (
    deduplicate_products, 
    filter_by_price, 
    sort_products
)

# Filter and deduplicate
unique_products = deduplicate_products(products, key='name')
filtered = filter_by_price(unique_products, min_price=10, max_price=500)
sorted_products = sort_products(filtered, by='price', reverse=False)

# Save
save(sorted_products, "cheap_products.json")
```

### Manual Validation
```python
from validators import validate_product

# Create from dict with validation
data = {
    'name': 'Laptop',
    'price': '1299.99 USD',
    'url': 'https://shop.example.com/laptop'
}

product = validate_product(data)
if product:
    print(f"Valid: {product.name}")
else:
    print("Invalid product data")
```

---

## Testing

All validation functions tested and verified:

```
✅ clean_price() normalizes currency correctly
✅ Product creation and validation works
✅ get_price_as_float() extracts numeric values
✅ to_dict() serialization works
✅ deduplicate_products() removes duplicates
✅ Validation checks work correctly
```

Test file: [test_validators.py](test_validators.py)

---

## Output Format

Saved products (JSON):
```json
[
  {
    "name": "Laptop Pro 15",
    "price": "1299.99",
    "url": "https://example.com/laptop",
    "currency": "USD",
    "description": "High-performance laptop...",
    "image_url": "https://..."
  },
  ...
]
```

---

## Next Steps

Potential enhancements:
1. **Database Storage** - Replace JSON with database (storage.py)
2. **Price Tracking** - Store price history (tracker.py)
3. **Data Cleaning** - Additional cleanup functions (cleaner.py)
4. **Batch Processing** - Handle large datasets efficiently
5. **Export Formats** - Support CSV, Excel, etc.
6. **Schema Validation** - Add JSON Schema validation
7. **Performance** - Caching, parallel validation

---

## Summary

Data validation is now a core part of the scraper. Every scraped product:
- ✅ Has a defined schema (Product dataclass)
- ✅ Is validated before being returned
- ✅ Can be easily filtered, deduplicated, sorted
- ✅ Has normalized pricing and currency
- ✅ Exports as clean JSON

This foundation enables reliable data processing, analytics, and storage downstream.
