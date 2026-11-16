from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json

# ---------- SETUP DRIVER ----------

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

# ---------- CONFIG ----------

BASE_URL = "https://www.mytek.tn/informatique/ordinateur-de-bureau/pc-de-bureau.html"
WAIT_TIME = 2

# ---------- CLEAN PRICE ----------

def clean_price(price_text):
    if not price_text:
        return ""

    return (
        price_text
        .replace("TND", "")
        .replace("\xa0", "")
        .replace(",", ".")
        .replace("Â", "")
        .strip()
    )

# ---------- SAFE FIND ----------

def safe_find(element, selector):
    try:
        return element.find_element(By.CSS_SELECTOR, selector).text
    except:
        return ""

# ---------- SCRAPE FUNCTION ----------

def scrape_page(page):
    url = f"{BASE_URL}?p={page}"
    print("Loading:", url)

    driver.get(url)

    wait = WebDriverWait(driver, 20)

    # Wait page body
    wait.until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    # Scroll to trigger lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    # Try multiple selectors (real-world robust scraping)
    selectors = [
        ".product-item",
        ".item.product.product-item",
        "[data-product-id]"
    ]

    products = []

    for sel in selectors:
        products = driver.find_elements(By.CSS_SELECTOR, sel)
        if products:
            print("Using selector:", sel)
            break

    print("Products found:", len(products))

    data = []

    data = []

    for p in products:
        try:
            name = ""
            price = ""

        # Try name globally inside container
            try:
                name = p.find_element(By.XPATH, ".//a[contains(@class,'product-item-link')]").text
            except:
                pass

        # Try price globally inside container
            try:
                price = p.find_element(By.XPATH, ".//*[contains(@class,'price')]").text
            except:
                pass

            if name and price:
                data.append({
                    "name": name.strip(),
                    "price": clean_price(price)
            })
        except Exception as e:
            continue

    print("Extracted products:", len(data))

    return data



# ---------- MAIN LOOP ----------

all_products = []
page = 1

while True:
    print("\nScraping page", page)

    data = scrape_page(page)

    if not data:
        print("No more products found.")
        break

    all_products.extend(data)

    page += 1
    time.sleep(WAIT_TIME)

# ---------- SAVE ----------

with open("mytek_products.json", "w", encoding="utf-8") as f:
    json.dump(all_products, f, indent=2, ensure_ascii=False)

print("\nDone:", len(all_products))

driver.quit()
