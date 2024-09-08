from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time

# Initialize Chrome WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# URL for Trader Joe's search page for "flour"
url = "https://www.traderjoes.com/home/search?q=flour&global=yes"

# Open the URL in the browser
driver.get(url)

# Wait for the page to fully load
time.sleep(5)  # Adjust this if the page takes longer to load

# Get the page source and parse it with BeautifulSoup
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# Close the browser after fetching the content
driver.quit()

# Base URL for Trader Joe's to prepend to relative image URLs
base_url = "https://www.traderjoes.com"

# List to store product data
products = []

# Find all product cards
product_cards = soup.find_all('article', class_='SearchResultCard_searchResultCard__3V-_h')

# Loop through each product card and extract the required information
for card in product_cards:
    product = {}

    # Extract the product name
    product_name_tag = card.find('a', class_='SearchResultCard_searchResultCard__titleLink__2nz6x')
    if product_name_tag:
        product['name'] = product_name_tag.text.strip()
    else:
        product['name'] = 'N/A'  # If the name is not found, mark it as 'N/A'

    # Extract the product price
    product_price_tag = card.find('span', class_='ProductPrice_productPrice__price__3-50j')
    if product_price_tag:
        product['price'] = product_price_tag.text.strip()
    else:
        product['price'] = 'N/A'  # If the price is not found, mark it as 'N/A'

    # Extract the product image URL
    product_image_tag = card.find('picture', class_='SearchResultCard_searchResultCard__image__2Yf2S')
    if product_image_tag:
        image_tag = product_image_tag.find('img')
        if image_tag and 'src' in image_tag.attrs:
            product['image_url'] = base_url + image_tag['src']
        else:
            product['image_url'] = 'N/A'  # If the image is not found, mark it as 'N/A'
    else:
        product['image_url'] = 'N/A'  # If the image tag is not found, mark it as 'N/A'

    # Add the product to the list if any fields were found
    products.append(product)

# Save the extracted data to a CSV file
filename = 'trader_joes_flour_products.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['name', 'price', 'image_url'])
    w.writeheader()
    for product in products:
        w.writerow(product)

print(f"Data has been saved to {filename}")
