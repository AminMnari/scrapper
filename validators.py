"""
validators.py — Data validation and schema enforcement for scraped products.

Provides:
- Product dataclass with type hints
- Validation and cleaning functions
- Batch validation with error handling
- Type conversion and normalization
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Any, Union
import logging
import re
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


@dataclass
class Product:
    """
    Validated product data structure.
    
    All fields are optional during construction to allow partial data,
    but require_all() validates that required fields are non-empty.
    """
    name: str = ""
    price: Optional[Union[str, float]] = None
    url: Optional[str] = None
    currency: str = "TND"  # Default to Tunisian Dinar
    category: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    
    def __post_init__(self):
        """Normalize fields after initialization."""
        # Strip whitespace from string fields
        self.name = str(self.name).strip() if self.name else ""
        self.currency = str(self.currency).strip() if self.currency else "TND"
        self.category = str(self.category).strip() if self.category else None
        self.description = str(self.description).strip() if self.description else None
        self.url = str(self.url).strip() if self.url else None
        self.image_url = str(self.image_url).strip() if self.image_url else None
        
        # Normalize price to string (preserve original format)
        if self.price is not None:
            self.price = str(self.price).strip()
    
    def is_valid(self, require_url: bool = False) -> bool:
        """
        Check if product has minimum required fields.
        
        Args:
            require_url: If True, URL must be non-empty
            
        Returns:
            True if product meets validation criteria
        """
        if not self.name:
            return False
        if require_url and not self.url:
            return False
        return True
    
    def get_price_as_float(self) -> Optional[float]:
        """
        Extract numeric price value.
        
        Returns:
            Float price or None if parsing failed
        """
        if not self.price:
            return None
        
        price_str = str(self.price)
        # Remove common currency symbols and whitespace
        price_clean = re.sub(r'[^\d.,]', '', price_str)
        
        # Handle different decimal separators
        if ',' in price_clean and '.' in price_clean:
            # Both present - take the last as decimal
            if price_clean.rindex(',') > price_clean.rindex('.'):
                price_clean = price_clean.replace('.', '').replace(',', '.')
            else:
                price_clean = price_clean.replace(',', '')
        elif ',' in price_clean:
            # European format
            price_clean = price_clean.replace('.', '').replace(',', '.')
        
        try:
            return float(price_clean)
        except (ValueError, AttributeError):
            logger.debug(f"Could not parse price '{self.price}' as float")
            return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    def to_dict_all(self) -> dict:
        """Convert to dictionary, including all fields."""
        return asdict(self)


class ValidationError(Exception):
    """Raised when product validation fails."""
    pass


def clean_price(price_text: str, currency: str = "TND") -> tuple[Optional[str], str]:
    """
    Clean and normalize price text.
    
    Args:
        price_text: Raw price text (e.g., "120.50 TND", "120,50€")
        currency: Default currency if not detected
        
    Returns:
        Tuple of (cleaned_price_str, detected_currency)
    """
    if not price_text:
        return None, currency
    
    text = str(price_text).strip()
    detected_currency = currency
    
    # Extract currency if present - check for currency codes first
    currency_code_map = {
        'USD': 'USD',
        'EUR': 'EUR',
        'GBP': 'GBP',
        'JPY': 'JPY',
        'TND': 'TND',
        'DT': 'TND',
    }
    
    # Check for currency codes (case-insensitive)
    for code, normalized in currency_code_map.items():
        if re.search(rf'\b{code}\b', text, re.IGNORECASE):
            detected_currency = normalized
            break
    
    # Extract currency symbols
    currency_symbol_map = {
        '₨': 'TND',
        '$': 'USD',
        '€': 'EUR',
        '£': 'GBP',
        '¥': 'JPY',
    }
    
    for symbol, code in currency_symbol_map.items():
        if symbol in text:
            detected_currency = code
            text = text.replace(symbol, '')
            break
    
    # Remove common currency codes
    text = re.sub(r'\b(USD|EUR|GBP|JPY|TND|DT)\b', '', text, flags=re.IGNORECASE)
    
    # Remove non-numeric characters except decimals
    text = re.sub(r'[^\d.,]', '', text)
    
    if not text:
        return None, detected_currency
    
    # Normalize decimal separator
    if ',' in text and '.' in text:
        if text.rindex(',') > text.rindex('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    
    # Validate it's a real number
    try:
        float(text)
        return text, detected_currency
    except ValueError:
        logger.debug(f"Could not clean price: {price_text}")
        return None, detected_currency


def clean_url(url: str) -> Optional[str]:
    """
    Validate and normalize URL.
    
    Args:
        url: URL string
        
    Returns:
        Normalized URL or None if invalid
    """
    if not url:
        return None
    
    url = str(url).strip()
    
    # Check if it looks like a URL
    if not url.startswith(('http://', 'https://', '/')):
        return None
    
    return url


def validate_product(data: dict, require_url: bool = False) -> Optional[Product]:
    """
    Validate and create a Product from dict.
    
    Args:
        data: Product data dictionary
        require_url: If True, product must have a URL
        
    Returns:
        Product instance if valid, None otherwise
        
    Raises:
        ValidationError: If data structure is invalid
    """
    if not isinstance(data, dict):
        raise ValidationError(f"Expected dict, got {type(data)}")
    
    try:
        # Extract and clean fields
        name = str(data.get('name', '')).strip()
        price = data.get('price')
        url = data.get('url')
        currency = data.get('currency', 'TND')
        category = data.get('category')
        description = data.get('description')
        image_url = data.get('image_url')
        
        # Clean price if present
        if price:
            price, detected_currency = clean_price(str(price), currency)
            currency = detected_currency
        
        # Clean URL
        if url:
            url = clean_url(url)
        
        # Create product
        product = Product(
            name=name,
            price=price,
            url=url,
            currency=currency,
            category=category,
            description=description,
            image_url=image_url,
        )
        
        # Validate
        if not product.is_valid(require_url=require_url):
            logger.debug(f"Product validation failed: {name}")
            return None
        
        return product
    
    except (KeyError, TypeError, ValueError) as e:
        logger.debug(f"Error validating product data: {e}")
        raise ValidationError(f"Invalid product data: {e}") from e


def validate_batch(products: list[dict], require_url: bool = False) -> tuple[list[Product], list[dict]]:
    """
    Validate a batch of products.
    
    Args:
        products: List of product dictionaries
        require_url: If True, only return products with URLs
        
    Returns:
        Tuple of (valid_products, invalid_items)
        where invalid_items = [{'data': dict, 'reason': str}, ...]
    """
    valid = []
    invalid = []
    
    for i, item in enumerate(products):
        try:
            product = validate_product(item, require_url=require_url)
            if product:
                valid.append(product)
            else:
                invalid.append({
                    'index': i,
                    'data': item,
                    'reason': 'Validation failed - missing required fields'
                })
        except ValidationError as e:
            invalid.append({
                'index': i,
                'data': item,
                'reason': str(e)
            })
    
    if invalid:
        logger.warning(f"Batch validation: {len(valid)} valid, {len(invalid)} invalid")
    
    return valid, invalid


def deduplicate_products(products: list[Product], key: str = 'name') -> list[Product]:
    """
    Remove duplicate products based on a key field.
    
    Args:
        products: List of Product instances
        key: Field to use for deduplication ('name', 'url', etc.)
        
    Returns:
        Deduplicated list, keeping first occurrence
    """
    seen = set()
    unique = []
    
    for product in products:
        value = getattr(product, key, None)
        if value and value not in seen:
            seen.add(value)
            unique.append(product)
    
    if len(unique) < len(products):
        logger.info(f"Deduplicated {len(products)} → {len(unique)} products")
    
    return unique


def sort_products(products: list[Product], by: str = 'price', reverse: bool = False) -> list[Product]:
    """
    Sort products by a field.
    
    Args:
        products: List of Product instances
        by: Field to sort by ('price', 'name', 'url')
        reverse: Sort descending if True
        
    Returns:
        Sorted list
    """
    if by == 'price':
        # Sort by numeric price
        return sorted(
            products,
            key=lambda p: p.get_price_as_float() or float('inf'),
            reverse=reverse
        )
    else:
        # Sort by string field
        return sorted(
            products,
            key=lambda p: getattr(p, by, '') or '',
            reverse=reverse
        )


def filter_by_price(products: list[Product], 
                   min_price: Optional[float] = None,
                   max_price: Optional[float] = None) -> list[Product]:
    """
    Filter products by price range.
    
    Args:
        products: List of Product instances
        min_price: Minimum price filter
        max_price: Maximum price filter
        
    Returns:
        Filtered list
    """
    filtered = []
    
    for product in products:
        price = product.get_price_as_float()
        if price is None:
            # Include products with unparseable prices
            filtered.append(product)
            continue
        
        if min_price and price < min_price:
            continue
        if max_price and price > max_price:
            continue
        
        filtered.append(product)
    
    logger.info(f"Price filter: {len(products)} → {len(filtered)} products")
    return filtered


def filter_by_currency(products: list[Product], currency: str) -> list[Product]:
    """
    Filter products by currency.
    
    Args:
        products: List of Product instances
        currency: Currency code to filter by
        
    Returns:
        Filtered list
    """
    filtered = [p for p in products if p.currency == currency]
    if len(filtered) < len(products):
        logger.info(f"Currency filter: {len(products)} → {len(filtered)} products")
    return filtered
