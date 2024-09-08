from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time

# Initialize Chrome WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# URL for Sprouts search page for "flour"
url = "https://shop.sprouts.com/search?search_term=flour&search_is_autocomplete=false"

# Open the URL in the browser
driver.get(url)

# Wait for the page to fully load
time.sleep(5)  # You can adjust this if needed

# Get the page source and parse it with BeautifulSoup
html = driver.page_source
soup = BeautifulSoup(html, 'html.parser')

# Close the browser after fetching the content
driver.quit()

# List to store product data
products = []

# Find all product cards
product_cards = soup.find_all('li', class_='product-wrapper')

# Loop through each product card and extract the required information
for card in product_cards:
    product = {}

    # Extract the product name
    product_name_tag = card.find('div', class_='css-15uwigl')
    if product_name_tag:
        product['name'] = product_name_tag.text.strip()
    else:
        product['name'] = 'N/A'  # If the name is not found, mark it as 'N/A'

    # Extract the product price
    product_price_tag = card.find('span', class_='css-coqxwd')
    if product_price_tag:
        product['price'] = product_price_tag.text.strip()
    else:
        product['price'] = 'N/A'  # If the price is not found, mark it as 'N/A'

    # Extract the product image URL
    product_image_tag = card.find('img', class_='css-1eer7o2')
    if product_image_tag and 'src' in product_image_tag.attrs:
        product['image_url'] = product_image_tag['src']
    else:
        product['image_url'] = 'N/A'  # If the image is not found, mark it as 'N/A'

    # Add the product to the list if any fields were found
    products.append(product)

# Save the extracted data to a CSV file
filename = 'sprouts_flour_products.csv'
with open(filename, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['name', 'price', 'image_url'])
    w.writeheader()
    for product in products:
        w.writerow(product)

print(f"Data has been saved to {filename}")
