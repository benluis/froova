from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time
import re
import os

def scrape_sprouts_products(product):
    # Format the product string to be URL-friendly
    formatted_product = re.sub(r'\s+', '+', product.strip())  # Replace spaces with '+'
    url = f"https://shop.sprouts.com/search?search_term={formatted_product}&search_is_autocomplete=false"

    # Initialize Chrome WebDriver with options
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in headless mode (without opening a window)
    options.add_argument('--disable-gpu')  # Disable GPU rendering
    options.add_argument('--no-sandbox')  # Bypass OS security model

    # Start the WebDriver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        # Open the URL in the browser
        driver.get(url)

        # Wait for the page to fully load
        time.sleep(5)  # Adjust this if necessary

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
    product_cards = soup.find_all('li', class_='product-wrapper')

    # Loop through each product card and extract the required information
    for card in product_cards:
        product_data = {}

        # Add the product type and store
        product_data['type'] = product  # The product type (e.g., "flour")
        product_data['store'] = "Sprouts"  # The store name

        # Extract the product name
        product_name_tag = card.find('div', class_='css-15uwigl')
        if product_name_tag:
            product_data['name'] = product_name_tag.text.strip()
        else:
            product_data['name'] = 'N/A'  # If the name is not found, mark it as 'N/A'

        # Extract the product price
        product_price_tag = card.find('span', class_='css-coqxwd')
        if product_price_tag:
            product_data['price'] = product_price_tag.text.strip()
        else:
            product_data['price'] = 'N/A'  # If the price is not found, mark it as 'N/A'

        # Extract the product image URL
        product_image_tag = card.find('img', class_='css-1eer7o2')
        if product_image_tag and 'src' in product_image_tag.attrs:
            product_data['image_url'] = product_image_tag['src']
        else:
            product_data['image_url'] = 'N/A'  # If the image is not found, mark it as 'N/A'

        # Add the product to the list
        products.append(product_data)

    # Ensure the filename is URL-safe
    safe_product_name = re.sub(r'[^A-Za-z0-9]+', '_', product.strip().lower())
    filename = f'sprouts_{safe_product_name}.csv'

    # Save the extracted data to a CSV file
    csv_path = os.path.join(os.getcwd(), filename)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['type', 'store', 'name', 'price', 'image_url'])
        w.writeheader()
        for product_data in products:
            w.writerow(product_data)

    print(f"Data has been saved to {filename}")

