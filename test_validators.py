"""
Test validators module
"""
from validators import Product, validate_product, clean_price, deduplicate_products

# Test clean_price
price, currency = clean_price('120.50 TND')
assert price == '120.50'
assert currency == 'TND'
print(f'✅ clean_price: {price} {currency}')

# Test Product creation
p = Product(name='Test Product', price='99.99', currency='USD')
assert p.name == 'Test Product'
assert p.price == '99.99'
print(f'✅ Product created: {p.name} - {p.price} {p.currency}')

# Test validate_product
data = {'name': 'Laptop', 'price': '1500', 'url': 'https://example.com'}
p = validate_product(data)
assert p is not None
assert p.name == 'Laptop'
print(f'✅ Product validated: {p.name}')

# Test get_price_as_float
p = Product(name='Item', price='99.99')
float_price = p.get_price_as_float()
assert float_price == 99.99
print(f'✅ Price as float: {float_price}')

# Test to_dict
d = p.to_dict()
assert 'name' in d
assert d['name'] == 'Item'
print(f'✅ Product to dict: {d}')

# Test deduplication
products = [
    Product(name='Laptop'),
    Product(name='Laptop'),  # duplicate
    Product(name='Mouse'),
]
unique = deduplicate_products(products, key='name')
assert len(unique) == 2
print(f'✅ Deduplicated: {len(products)} -> {len(unique)}')

# Test is_valid
p = Product(name='Valid')
assert p.is_valid() == True
p2 = Product(name='')  # invalid - no name
assert p2.is_valid() == False
print(f'✅ Validation checks work correctly')

print('\n✅✅✅ All validators tests passed!')
