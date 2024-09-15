import csv
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def scrape_lidl_products(product):
    # Ensure the 'product' input is a string and strip any leading/trailing whitespace
    if isinstance(product, str):
        product = product.strip()
    else:
        raise ValueError("Product must be a string")

    # Format the product string to be URL-friendly
    formatted_product = re.sub(r'\s+', '%20', product)  # Replace spaces with '%20'
    url = f"https://www.lidl.com/search/products/{formatted_product}"

    # Set up Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run Chrome in headless mode
    chrome_options.add_argument("--start-maximized")  # Open in maximized mode
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')

    # Initialize Chrome WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # Open the Lidl website for the product search
    driver.get(url)

    # Wait for the page to load completely
    time.sleep(5)

    # List to store product data
    products = []

    try:
        # Wait until the product elements are present on the page
        WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'product-card')))

        # Find all product containers
        product_container = driver.find_elements(By.CLASS_NAME, 'product-card')

        for product_card in product_container:
            product_info = {}

            # Add product type and store info
            product_info['type'] = product  # The product type (e.g., "flour")
            product_info['store'] = 'Lidl'  # The store name

            # Extract product name (using 'product-card__title')
            try:
                name = product_card.find_element(By.CLASS_NAME, 'product-card__title').text
            except:
                name = 'N/A'
            product_info['name'] = name.strip()

            # Extract product price (new price if available)
            try:
                price = product_card.find_element(By.CLASS_NAME, 'product-price-new__price').text
            except:
                price = 'N/A'
            product_info['price'] = price.strip()

            # Extract product image URL
            try:
                img = product_card.find_element(By.TAG_NAME, 'img').get_attribute('src')
            except:
                img = 'N/A'
            product_info['image_url'] = img

            # Add the product details to the list
            products.append(product_info)

    except Exception as e:
        print(f"Error occurred during scraping: {e}")

    finally:
        driver.quit()  # Close the browser after scraping

    # Ensure the filename is safe for the file system
    safe_product_name = re.sub(r'[^A-Za-z0-9]+', '_', product.lower())  # Make sure 'product' is a string
    filename = f'lidl_{safe_product_name}.csv'

    # Save the extracted data to a CSV file
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        # Write the headers and product details into the CSV, including 'type' and 'store'
        w = csv.DictWriter(f, fieldnames=['type', 'store', 'name', 'price', 'image_url'])
        w.writeheader()
        for product_info in products:
            w.writerow(product_info)

    print(f"Data has been saved to {filename}")
