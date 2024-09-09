from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time
import re
import os

def scrape_target_products(product):
    # Format the product string to be URL-friendly
    formatted_product = re.sub(r'\s+', '+', product.strip())  # Replace spaces with '+'
    url = f"https://www.target.com/s?searchTerm={formatted_product}&tref=typeahead%7Cterm%7C{formatted_product}%7C%7C%7Chistory"

    # Initialize Chrome WebDriver with options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode (without opening a window)
    options.add_argument('--disable-gpu')  # Disable GPU rendering
    options.add_argument('--no-sandbox')  # Bypass OS security model
    options.add_argument('--disable-blink-features=AutomationControlled')  # Prevent automation detection
    options.add_argument('--window-size=1920,1080')  # Set the window size for headless mode
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    # Start the WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # Open the URL in the browser
        driver.get(url)

        # Increase wait time to allow the page to load fully
        time.sleep(5)

        # Gradually scroll down the page to trigger lazy loading multiple times
        total_scrolls = 3
        for i in range(total_scrolls):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Allow time for new content to load

        # Get the page source and parse it with BeautifulSoup
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

    except Exception as e:
        print(f"Error while fetching the page: {e}")
        driver.quit()
        return

    finally:
        # Close the browser after fetching the content
        driver.quit()

    # List to store product data
    products = []

    # Find all product cards
    product_cards = soup.find_all('div', {'data-test': '@web/ProductCard/ProductCardVariantDefault'})

    # Check if product cards were found
    if not product_cards:
        print("No products found or unable to load the page correctly.")
        return

    # Loop through each product card and extract the required information
    for card in product_cards:
        product_data = {}

        # Add the product type and store
        product_data['type'] = product  # The product type (e.g., "flour")
        product_data['store'] = "Target"  # The store name

        # Extract the product name
        product_name_tag = card.find('a', {'data-test': 'product-title'})
        if product_name_tag:
            product_data['name'] = product_name_tag.text.strip()
        else:
            product_data['name'] = 'N/A'  # If the name is not found, mark it as 'N/A'

        # Extract the product price
        product_price_tag = card.find('span', {'data-test': 'current-price'})
        if product_price_tag:
            product_data['price'] = product_price_tag.text.strip()
        else:
            product_data['price'] = 'N/A'  # If the price is not found, mark it as 'N/A'

        # Extract the product image URL
        product_image_tag = card.find('picture', {'data-test': '@web/ProductCard/ProductCardImage/primary'})
        if product_image_tag:
            image_tag = product_image_tag.find('img')
            if image_tag and 'src' in image_tag.attrs:
                product_data['image_url'] = image_tag['src']
            else:
                product_data['image_url'] = 'N/A'  # If the image is not found, mark it as 'N/A'
        else:
            product_data['image_url'] = 'N/A'  # If the image tag is not found, mark it as 'N/A'

        # Add the product to the list if any fields were found
        products.append(product_data)

    # Ensure the filename is URL-safe
    safe_product_name = re.sub(r'[^A-Za-z0-9]+', '_', product.strip().lower())
    filename = f'target_{safe_product_name}.csv'

    # Save the extracted data to a CSV file
    csv_path = os.path.join(os.getcwd(), filename)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['type', 'store', 'name', 'price', 'image_url'])
        w.writeheader()
        for product_data in products:
            w.writerow(product_data)

    print(f"Data has been saved to {filename}")