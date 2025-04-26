# built-in
import csv
import time
import re
import os
import random
import asyncio
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from contextlib import asynccontextmanager

# external
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd

# internal
from models import Product


class ThrottleConfig:
    """Configuration for handling rate limiting and bot detection."""

    def __init__(self):
        self.enabled = True
        self.base_delay = 2  # Base delay in seconds
        self.detection_count = 0
        self.max_detections = 3

    def calculate_delay(self):
        """Calculate appropriate delay with exponential backoff and jitter."""
        if not self.enabled:
            return 0

        multiplier = min(2**self.detection_count, 8)
        jitter = random.uniform(0.5, 1.5)
        return self.base_delay * multiplier * jitter


class StoreConfig:
    def __init__(
        self,
        name: str,
        search_url_template: str,
        product_selector: str,
        name_selector: str,
        price_selector: str,
        image_selector: str,
        bot_detection_indicators: List[str] = None,
    ):
        self.name = name
        self.search_url_template = search_url_template
        self.product_selector = product_selector
        self.name_selector = name_selector
        self.price_selector = price_selector
        self.image_selector = image_selector
        self.bot_detection_indicators = bot_detection_indicators or [
            "captcha",
            "robot",
            "verification",
            "security check",
        ]


class Store(Enum):
    WALMART = StoreConfig(
        name="Walmart",
        search_url_template="https://www.walmart.com/search?q={product}",
        product_selector="div.mb1.ph1.pa0-xl.bb.b--near-white",
        name_selector="span.w_iUH7",
        price_selector="div.flex.flex-wrap span.w_iUH7",
        image_selector="img[data-testid='product-image']",
    )
    TARGET = StoreConfig(
        name="Target",
        search_url_template="https://www.target.com/s?searchTerm={product}",
        product_selector="div[data-test='product-card']",
        name_selector="a[data-test='product-title']",
        price_selector="span[data-test='current-price']",
        image_selector="img[data-test='product-image']",
    )
    SPROUTS = StoreConfig(
        name="Sprouts",
        search_url_template="https://shop.sprouts.com/search?search_term={product}",
        product_selector="li.e-1g8wfed",
        name_selector="h3.e-7pey2a",
        price_selector="span.e-15php9x",
        image_selector="img.e-1acazxx",
    )
    LIDL = StoreConfig(
        name="Lidl",
        search_url_template="https://www.lidl.com/products?searchTerm={product}",
        product_selector="div.product-card",
        name_selector="h2.product-card__name",
        price_selector="div.product-card__price",
        image_selector="img.product-card__image",
    )


class ScraperConfig:
    """Configuration for the scraper behavior."""

    def __init__(self):
        self.consecutive_errors = 0
        self.consecutive_empty_count = 0
        self.error_threshold = 3
        self.empty_threshold = 4
        self.cooldown_period = 600
        self.batch_size = 10
        self.max_concurrent_scrapers = 3


class WebDriverManager:
    """Manages WebDriver setup and operations."""

    @staticmethod
    def create() -> webdriver.Chrome:
        """Create and configure a new Chrome WebDriver."""
        print("Setting up Chrome WebDriver...")
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )

        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=options
            )
            return driver
        except Exception as e:
            print(f"Error setting up WebDriver: {e}")
            raise

    @staticmethod
    async def scroll_page(driver: webdriver.Chrome, pause_time: float = 1.5) -> None:
        """Scroll the page to load all dynamic content."""
        print("Scrolling page to load dynamic content...")
        try:
            last_height = driver.execute_script("return document.body.scrollHeight")

            for _ in range(3):  # Limit scrolling to 3 times
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                await asyncio.sleep(
                    pause_time
                )

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

        except Exception as e:
            print(f"Error during page scrolling: {e}")


class BotDetector:
    """Detects bot protection mechanisms on websites."""

    @staticmethod
    def is_bot_protection_present(html_content: str, indicators: List[str]) -> bool:
        """Check if the response contains bot protection indicators."""
        if not html_content:
            return False

        matches = sum(
            1 for indicator in indicators if indicator.lower() in html_content.lower()
        )
        return matches >= 1


class ContentExtractor:
    """Extracts product information from HTML."""

    @staticmethod
    def extract_products(html: str, store_config: StoreConfig) -> List[Product]:
        """Extract product information using BeautifulSoup."""
        products = []

        try:
            soup = BeautifulSoup(html, "html.parser")

            selector_dict = ContentExtractor._parse_selector(
                store_config.product_selector
            )
            product_items = soup.find_all(**selector_dict)

            for item in product_items:
                try:
                    name_element = item.select_one(store_config.name_selector)
                    price_element = item.select_one(store_config.price_selector)
                    img_element = item.select_one(store_config.image_selector)

                    if not name_element or not price_element:
                        continue

                    name = name_element.text.strip()
                    price = price_element.text.strip()

                    image_url = None
                    if img_element and "src" in img_element.attrs:
                        image_url = img_element["src"]
                    elif img_element and "data-src" in img_element.attrs:
                        image_url = img_element["data-src"]

                    product_obj = Product(
                        type="",
                        name=name,
                        price=price,
                        store=store_config.name,
                        image_url=image_url,
                    )

                    products.append(product_obj)

                except Exception as e:
                    print(f"Error extracting product from item: {e}")
                    continue

        except Exception as e:
            print(f"Error extracting products: {e}")

        return products

    @staticmethod
    def _parse_selector(selector: str) -> Dict[str, Any]:
        """Parse a CSS selector string into args for BeautifulSoup find methods."""
        if "[" in selector and "]" in selector:
            tag, attrs = selector.split("[", 1)
            attr_content = attrs.rstrip("]")

            if "=" in attr_content:
                attr_name, attr_value = attr_content.split("=", 1)
                attr_value = attr_value.strip("\"'")
                return {"name": tag, "attrs": {attr_name: attr_value}}
            return {"name": tag}
        elif "." in selector:
            parts = selector.split(".", 1)
            tag = parts[0] or None
            class_name = parts[1]
            return {"name": tag, "attrs": {"class": class_name}}
        else:
            return {"name": selector}


class ProductScraper:
    """Main scraper class for product information."""

    def __init__(self, output_dir: str = "product_data"):
        self.throttle_config = ThrottleConfig()
        self.scraper_config = ScraperConfig()
        self.output_dir = output_dir
        self.semaphore = asyncio.Semaphore(self.scraper_config.max_concurrent_scrapers)
        os.makedirs(output_dir, exist_ok=True)

    async def scrape_product(
        self, product_name: str, store: Store, max_retries: int = 3
    ) -> List[Product]:
        """
        Scrape product information from a store with retry logic.
        """
        print(
            f"\n{'=' * 80}\nScraping {product_name} from {store.value.name}\n{'=' * 80}"
        )
        products = []
        driver = None
        retries = 0

        async with self.semaphore:
            try:
                formatted_product = re.sub(r"\s+", "+", product_name.strip())
                url = store.value.search_url_template.format(product=formatted_product)

                delay = self.throttle_config.calculate_delay()
                print(f"Throttling applied: waiting {delay:.2f} seconds before request")
                await asyncio.sleep(delay)  # Using asyncio.sleep instead of time.sleep

                driver = WebDriverManager.create()

                while retries < max_retries:
                    try:
                        driver.get(url)

                        await asyncio.sleep(3)

                        html = driver.page_source

                        if BotDetector.is_bot_protection_present(
                            html, store.value.bot_detection_indicators
                        ):
                            print(f"Bot protection detected for {url}")
                            self.throttle_config.detection_count += 1
                            retries += 1
                            await asyncio.sleep(
                                self.throttle_config.calculate_delay() * 2
                            )
                            continue

                        try:
                            selector = store.value.product_selector
                            css_selector = self._convert_to_css_selector(selector)

                            wait = WebDriverWait(driver, 10)
                            wait.until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, css_selector)
                                )
                            )
                        except Exception as e:
                            print(f"Error waiting for product elements: {e}")
                            retries += 1
                            continue

                        await WebDriverManager.scroll_page(driver)

                        html = driver.page_source

                        products = ContentExtractor.extract_products(html, store.value)

                        for p in products:
                            p.type = product_name

                        if products:
                            if self.throttle_config.detection_count > 0:
                                self.throttle_config.detection_count = max(
                                    0, self.throttle_config.detection_count - 1
                                )
                            break
                        else:
                            print(
                                f"No products found. Retry {retries + 1}/{max_retries}"
                            )
                            retries += 1

                    except Exception as e:
                        print(f"Error during scraping attempt {retries + 1}: {e}")
                        retries += 1

                        if retries < max_retries:
                            print(f"Retrying... ({retries}/{max_retries})")
                            await asyncio.sleep(5)

            except Exception as e:
                print(
                    f"CRITICAL ERROR while processing {product_name} from {store.value.name}:"
                )
                print(f"Error details: {e}")

            finally:
                if driver:
                    driver.quit()

        print(
            f"{'=' * 80}\nScraping completed for {product_name} from {store.value.name}\n{'=' * 80}"
        )
        return products

    def _convert_to_css_selector(self, selector: str) -> str:
        """Convert a selector to valid CSS selector for Selenium."""
        return selector

    async def scrape_products_batch(
        self, products: List[str], stores: List[Store] = None
    ) -> pd.DataFrame:
        """
        Scrape multiple products from multiple stores in parallel and save results.
        """
        if stores is None:
            stores = list(Store)

        all_results = []
        tasks = []

        for product in products:
            for store in stores:
                print(f"Creating scraping task for {product} from {store.value.name}")
                task = asyncio.create_task(self.scrape_product(product, store))
                tasks.append((product, store, task))

        batch_size = self.scraper_config.batch_size
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i : i + batch_size]

            for product, store, task in batch_tasks:
                try:
                    print(f"Awaiting results for {product} from {store.value.name}")
                    products_found = await task

                    all_results.extend([p.dict() for p in products_found])

                    await self._save_interim_results(all_results)

                except Exception as e:
                    print(
                        f"Error processing task for {product} from {store.value.name}: {e}"
                    )

        final_df = pd.DataFrame(all_results) if all_results else pd.DataFrame()

        output_path = os.path.join(self.output_dir, "all_products.csv")
        final_df.to_csv(output_path, index=False)

        return final_df

    async def _save_interim_results(self, results: List[Dict[str, Any]]) -> None:
        """Save interim results to prevent data loss."""
        interim_path = os.path.join(self.output_dir, "interim_results.csv")
        await asyncio.to_thread(
            lambda: pd.DataFrame(results).to_csv(interim_path, index=False)
        )


async def scrape_and_get_products(
    product_names: List[str], stores: List[Store] = None
) -> List[Dict[str, Any]]:
    """Helper function to be used by FastAPI endpoints"""
    scraper = ProductScraper(output_dir="product_data")
    results = await scraper.scrape_products_batch(product_names, stores)
    return results.to_dict("records") if not results.empty else []


async def main():
    scraper = ProductScraper(output_dir="product_data")

    products_to_search = ["organic milk", "gluten free bread", "vegan cheese"]

    results_df = await scraper.scrape_products_batch(
        products_to_search, stores=[Store.WALMART, Store.TARGET]
    )

    print(f"Scraped {len(results_df)} products")
    print(results_df.head())


if __name__ == "__main__":
    asyncio.run(main())
