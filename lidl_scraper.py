import csv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Set up Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")  # Open the browser in maximized mode

# Set up the WebDriver for Chrome without specifying the path to ChromeDriver
service = Service()  # No executable_path here, assuming ChromeDriver is in system PATH
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open the Lidl website for flour search
driver.get("https://www.lidl.com/search/products/flour")

# Wait for the page to load completely
time.sleep(5)

# Extract product information
products = []

try:
    # Wait until the product elements are present on the page
    WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, 'product-card')))

    # Find all product containers
    product_container = driver.find_elements(By.CLASS_NAME, 'product-card')

    for product in product_container:
        product_info = {}

        # Extract product name (using 'product-card__title')
        try:
            name = product.find_element(By.CLASS_NAME, 'product-card__title').text
        except:
            name = 'N/A'
        product_info['name'] = name.strip()

        # Extract product price (new price if available)
        try:
            price = product.find_element(By.CLASS_NAME, 'product-price-new__price').text
        except:
            price = 'N/A'
        product_info['price'] = price.strip()

        # Extract product image URL
        try:
            img = product.find_element(By.TAG_NAME, 'img').get_attribute('src')
        except:
            img = 'N/A'
        product_info['image_url'] = img

        # Add the product details to the list
        products.append(product_info)

finally:
    driver.quit()  # Close the browser after scraping

# Save the extracted data to a CSV file
filename = 'lidl_flour_products.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    # Write the headers and product details into the CSV
    w = csv.DictWriter(f, fieldnames=['name', 'price', 'image_url'])
    w.writeheader()
    for product in products:
        w.writerow(product)

print(f"Data has been saved to {filename}")
