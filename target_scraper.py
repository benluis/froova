from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time

# Initialize Chrome WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# URL for Target search page for "flour"
url = "https://www.target.com/s?searchTerm=flour&tref=typeahead%7Cterm%7Cflour%7C%7C%7Chistory"

# Open the URL in the browser
driver.get(url)

# Wait for the page to fully load
time.sleep(5)  # You can increase this if the content loads slowly

# Get the page source and parse it with BeautifulSoup
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# Close the browser after fetching the content
driver.quit()

# List to store product data
products = []

# Find all product cards
product_cards = soup.find_all('div', {'data-test': '@web/ProductCard/ProductCardVariantDefault'})

# Loop through each product card and extract the required information
for card in product_cards:
    product = {}

    # Extract the product name
    product_name_tag = card.find('a', {'data-test': 'product-title'})
    if product_name_tag:
        product['name'] = product_name_tag.text.strip()
    else:
        product['name'] = 'N/A'  # If the name is not found, mark it as 'N/A'

    # Extract the product price
    product_price_tag = card.find('span', {'data-test': 'current-price'})
    if product_price_tag:
        product['price'] = product_price_tag.text.strip()
    else:
        product['price'] = 'N/A'  # If the price is not found, mark it as 'N/A'

    # Extract the product image URL
    product_image_tag = card.find('picture', {'data-test': '@web/ProductCard/ProductCardImage/primary'})
    if product_image_tag:
        image_tag = product_image_tag.find('img')
        if image_tag and 'src' in image_tag.attrs:
            product['image_url'] = image_tag['src']
        else:
            product['image_url'] = 'N/A'  # If the image is not found, mark it as 'N/A'
    else:
        product['image_url'] = 'N/A'  # If the image tag is not found, mark it as 'N/A'

    # Add the product to the list if any fields were found
    products.append(product)

# Save the extracted data to a CSV file
filename = 'target_flour_products.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['name', 'price', 'image_url'])
    w.writeheader()
    for product in products:
        w.writerow(product)

print(f"Data has been saved to {filename}")
