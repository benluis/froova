# built-in
import os
import time
import random

# external
import pandas as pd
from pydantic import BaseModel, Field
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


# Models
class CampaignData(BaseModel):
    id: str
    project_url: str


class ScrapedStory(BaseModel):
    id: str
    story_content: str
    is_throttled: bool = Field(
        default=False,
        description="Whether content was empty due to throttling/Cloudflare",
    )
    cloudflare_detected: bool = Field(
        default=False, description="Whether Cloudflare challenge was detected"
    )


class ThrottleConfig:
    """Configuration for handling rate limiting and Cloudflare challenges."""

    def __init__(self):
        self.enabled = False
        self.base_delay = 5  # Base delay in seconds
        self.cloudflare_detected_count = 0
        self.max_cloudflare_detections = 3

    def enable(self):
        """Enable throttling."""
        self.enabled = True

    def disable(self):
        """Disable throttling."""
        self.enabled = False

    def increment_cloudflare_count(self):
        """Increment the count of detected Cloudflare challenges."""
        self.cloudflare_detected_count += 1

    def reset_cloudflare_count(self):
        """Reset the count of detected Cloudflare challenges."""
        self.cloudflare_detected_count = 0

    def calculate_delay(self):
        """Calculate the appropriate delay based on current conditions."""
        if not self.enabled:
            return 0

        # Exponential backoff based on Cloudflare detection count
        multiplier = min(2**self.cloudflare_detected_count, 10)
        jitter = random.uniform(0.5, 1.5)
        return self.base_delay * multiplier * jitter


class ScraperConfig(BaseModel):
    consecutive_errors: int = 0
    consecutive_empty_count: int = 0
    error_threshold: int = 3
    empty_threshold: int = 4
    cooldown_period: int = 600  # 10 minutes in seconds
    batch_size: int = 1000


# Instantiate configurations
throttle_config = ThrottleConfig()
scraper_config = ScraperConfig()


class CloudflareDetector:
    """Handles detection of Cloudflare challenge pages."""

    @staticmethod
    def is_challenge_present(html_content: str) -> bool:
        """Check if the response contains Cloudflare challenge page."""
        if not html_content:
            return False

        # More specific indicators that are unique to Cloudflare challenge pages
        cloudflare_indicators = [
            "Just a moment...",
            "challenge-platform/h/g/orchestrate/chl_page",
            "cf-browser-verification",
            "Verify you are human by completing the action below",
        ]

        # Check for multiple indicators to reduce false positives
        matches = sum(
            1 for indicator in cloudflare_indicators if indicator in html_content
        )
        return (
            matches >= 2
        )  # Require at least two indicators to consider it a challenge page


class WebDriverManager:
    """Manages WebDriver setup and operations."""

    @staticmethod
    def create() -> webdriver.Chrome:
        """Create and configure a new Chrome WebDriver."""
        print("Setting up Chrome WebDriver...")
        options = Options()
        # options.add_argument("--headless")  # Uncomment for headless operation
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-images")
        options.add_argument("--disable-javascript")
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
    def scroll_page(driver: webdriver.Chrome, pause_time: float = 1.5) -> None:
        """Scroll the page to load all dynamic content."""
        print("Scrolling page to load dynamic content...")
        try:
            # Get scroll height
            last_height = driver.execute_script("return document.body.scrollHeight")

            while True:
                # Scroll down to bottom
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                # Wait to load page
                time.sleep(pause_time)

                # Calculate new scroll height and compare with last scroll height
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

        except Exception as e:
            print(f"Error during page scrolling: {e}")


class ContentExtractor:
    """Extracts content from Kickstarter pages."""

    @staticmethod
    def extract_story(html: str, url: str) -> str:
        """Extract the story content from HTML using BeautifulSoup."""
        print(f"Extracting story content for {url}")

        try:
            soup = BeautifulSoup(html, "html.parser")
            story_section = soup.find("div", class_="story-content")

            if story_section:
                # Remove unwanted elements
                for element in story_section.select("script, style, iframe"):
                    element.decompose()

                # Get text with proper spacing
                content = ContentExtractor.clean_text(
                    story_section.get_text(separator="\n")
                )
                return content
            else:
                print(f"Story section not found for URL: {url}")
                return ""

        except Exception as e:
            print(f"Error extracting story content: {e}")
            return ""

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean extracted text by removing extra whitespace and normalizing line breaks."""
        if not text:
            return ""

        # Replace multiple newlines with double newlines
        text = "\n\n".join(line.strip() for line in text.split("\n") if line.strip())
        return text


class KickstarterScraper:
    """Main scraper class for Kickstarter campaign stories."""

    @staticmethod
    def scrape_story(campaign_url: str, max_retries: int = 3) -> tuple[str, bool, bool]:
        """
        Scrapes the story section from a Kickstarter campaign page with retry logic.
        """
        print(f"\n{'=' * 80}\nScraping started for URL: {campaign_url}\n{'=' * 80}")
        story_content = ""
        driver = None
        retries = 0
        is_throttled = False
        cloudflare_detected = False

        try:
            # Apply throttling if enabled
            if throttle_config.enabled:
                delay = throttle_config.calculate_delay()
                print(f"Throttling applied: waiting {delay:.2f} seconds before request")
                time.sleep(delay)

            # Setup WebDriver
            driver = WebDriverManager.create()

            while retries < max_retries:
                try:
                    # Navigate to the campaign page
                    driver.get(campaign_url)

                    # Get HTML before waiting for elements (to check for Cloudflare)
                    html = driver.page_source

                    if CloudflareDetector.is_challenge_present(html):
                        print(f"Cloudflare challenge detected for {campaign_url}")
                        cloudflare_detected = True
                        throttle_config.increment_cloudflare_count()
                        throttle_config.enable()

                        # If we've hit Cloudflare too many times, close driver and take a longer break
                        if (
                            throttle_config.cloudflare_detected_count
                            >= throttle_config.max_cloudflare_detections
                        ):
                            cooldown_time = scraper_config.cooldown_period  # 10 minutes
                            print(
                                f"Too many Cloudflare challenges detected. Closing driver and taking a {cooldown_time // 60} minute break."
                            )

                            # Close the driver before cooldown
                            if driver:
                                driver.quit()
                                driver = None

                            # Wait for cooldown period
                            time.sleep(cooldown_time)

                            # Create a new driver after cooldown
                            driver = WebDriverManager.create()
                        else:
                            print("Refreshing page to try again...")
                            time.sleep(5)  # Wait before refresh

                        retries += 1
                        continue  # Skip to next iteration without marking as throttled yet

                    # Wait for story content section
                    try:
                        wait = WebDriverWait(driver, 10)
                        story_section = wait.until(
                            EC.presence_of_element_located(
                                (By.CLASS_NAME, "story-content")
                            )
                        )

                        # Debug information about the story section
                        story_html = story_section.get_attribute("innerHTML")
                        print(f"Found story section. HTML length: {len(story_html)}")
                        if len(story_html) < 100:
                            print(f"Story HTML preview: {story_html[:100]}")
                    except Exception as e:
                        print(f"Error waiting for story-content element: {e}")
                        story_html = ""

                    # Scroll to ensure all content is loaded
                    WebDriverManager.scroll_page(driver)

                    # Get the updated page source
                    html = driver.page_source

                    # Extract the story content
                    story_content = ContentExtractor.extract_story(html, campaign_url)

                    # If content is empty but we found the story section, this might be legitimate
                    if not story_content and story_html:
                        print(
                            f"Story section found but content extraction failed. Retry {retries + 1}/{max_retries}"
                        )
                        retries += 1
                        if retries < max_retries:
                            print(
                                "Page loaded but content missing. Refreshing page and trying again..."
                            )
                            driver.refresh()
                            time.sleep(3)  # Longer wait after refresh
                            continue
                        else:
                            print(
                                "Max retries reached. This may be a legitimately empty story."
                            )
                            # Don't mark as throttled if we've seen the story section HTML
                    elif not story_content:
                        # No story content and no story HTML found
                        print(
                            f"No story content found. Retry {retries + 1}/{max_retries}"
                        )
                        retries += 1
                        if retries < max_retries:
                            print("Refreshing page and trying again...")
                            driver.refresh()
                            time.sleep(3)  # Longer wait after refresh
                            continue
                        else:
                            print(
                                "Max retries reached - possible throttling or empty content."
                            )
                            is_throttled = True  # Only mark as throttled if we couldn't find the section at all
                    else:
                        # Success - gradually reduce throttling if we've been throttling
                        if (
                            throttle_config.enabled
                            and throttle_config.cloudflare_detected_count > 0
                        ):
                            throttle_config.cloudflare_detected_count = max(
                                0, throttle_config.cloudflare_detected_count - 1
                            )

                        # Break the retry loop on success
                        break

                except Exception as e:
                    print(f"Error during scraping attempt {retries + 1}: {e}")
                    retries += 1

                    if retries < max_retries:
                        print(f"Retrying... ({retries}/{max_retries})")
                        time.sleep(5)  # Wait before retry
                    else:
                        print(f"Maximum retries reached.")
                        is_throttled = True

        except Exception as e:
            print(f"CRITICAL ERROR while processing {campaign_url}:")
            print(f"Error type: {type(e).__name__}")
            print(f"Error details: {e}")
            is_throttled = True

        finally:
            if driver:
                driver.quit()

        print(f"{'=' * 80}\nScraping completed for URL: {campaign_url}\n{'=' * 80}")
        return story_content, is_throttled, cloudflare_detected

    @staticmethod
    def process_batch(batch_df: pd.DataFrame, batch_num: int, output_dir: str) -> None:
        """Process a batch of campaigns and save results to a pickle file."""
        print(f"\nProcessing batch {batch_num + 1} with {len(batch_df)} campaigns")
        records = []
        success_count = 0
        failure_count = 0
        throttled_count = 0
        cloudflare_count = 0

        for i, (_, row) in enumerate(batch_df.iterrows()):
            project_id = str(row["id"])
            campaign_url = row["project_url"]

            print(f"\nProcessing project {i + 1}/{len(batch_df)} - ID: {project_id}")
            print(f"URL: {campaign_url}")

            try:
                # Get story content and throttling info
                story_content, is_throttled, cloudflare_detected = (
                    KickstarterScraper.scrape_story(campaign_url)
                )

                # Create record with all info
                record = ScrapedStory(
                    id=project_id,
                    story_content=story_content,
                    is_throttled=is_throttled,
                    cloudflare_detected=cloudflare_detected,
                )
                records.append(record)

                # Update counts for reporting
                if is_throttled:
                    throttled_count += 1
                if cloudflare_detected:
                    cloudflare_count += 1
                if story_content:
                    success_count += 1
                else:
                    failure_count += 1

            except Exception as e:
                print(f"Failed to process project {project_id}: {e}")
                failure_count += 1
                # Still create a record for failed attempts
                records.append(
                    ScrapedStory(id=project_id, story_content="", is_throttled=True)
                )

        # Save batch results
        KickstarterScraper._save_batch_results(records, batch_num, output_dir)

        # Print batch summary
        print(f"\nBatch {batch_num + 1} completed:")
        print(f"- Successful extractions: {success_count}/{len(batch_df)}")
        print(f"- Failed extractions: {failure_count}/{len(batch_df)}")
        print(f"- Throttled requests: {throttled_count}/{len(batch_df)}")
        print(f"- Cloudflare challenges: {cloudflare_count}/{len(batch_df)}")

    @staticmethod
    def _save_batch_results(
        records: list[ScrapedStory], batch_num: int, output_dir: str
    ) -> str:
        """Save batch results to a pickle file and return the path."""
        batch_filename = f"Kickstarter_stories_{batch_num + 1:03d}.pkl"
        batch_path = os.path.join(output_dir, batch_filename)

        batch_df_output = pd.DataFrame([record.model_dump() for record in records])
        batch_df_output.to_pickle(batch_path)

        print(f"- Saved to: {batch_path}")
        return batch_path


def test_scraper(csv_path: str, output_dir: str, num_projects: int = 10) -> None:
    """Test the scraper with a small number of projects."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Load data
    df = pd.read_csv(csv_path)
    test_df = df.head(num_projects)

    print(f"Testing scraper with {len(test_df)} projects")
    KickstarterScraper.process_batch(test_df, 0, output_dir)


# Configuration constants
INPUT_CSV_PATH = "KS_Data_round2.csv"
OUTPUT_DIR = "scraped_stories"
TEST_MODE = True  # Set to False for full run
TEST_SIZE = 10  # Number of campaigns to test if in test mode
BATCH_SIZE = 50  # Number of campaigns per batch


def main():
    """Main entry point for the scraper."""
    print(f"Starting Kickstarter scraper with input file: {INPUT_CSV_PATH}")

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output will be saved to: {OUTPUT_DIR}")

    # Configure scraper
    scraper_config.batch_size = BATCH_SIZE

    if TEST_MODE:
        print(f"Running in test mode with {TEST_SIZE} campaigns")
        test_scraper(INPUT_CSV_PATH, OUTPUT_DIR, TEST_SIZE)
        return

    # Load data for full run
    print("Loading campaign data from CSV")
    df = pd.read_csv(INPUT_CSV_PATH)
    print(f"Loaded {len(df)} campaigns")

    # Process data in batches
    batch_size = scraper_config.batch_size
    num_batches = (len(df) + batch_size - 1) // batch_size  # Ceiling division
    print(f"Processing data in {num_batches} batches of {batch_size}")

    for i in range(num_batches):
        batch_start = i * batch_size
        batch_end = min((i + 1) * batch_size, len(df))
        batch_df = df.iloc[batch_start:batch_end]

        print(f"Processing batch {i + 1}/{num_batches} with {len(batch_df)} campaigns")
        KickstarterScraper.process_batch(batch_df, i, OUTPUT_DIR)


if __name__ == "__main__":
    main()
