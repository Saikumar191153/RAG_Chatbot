import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import html2text
from collections import deque

class AngelOneWebCrawler:
    def __init__(self, base_url="https://www.angelone.in/support", max_pages=1000):
        self.base_url = base_url
        self.max_pages = max_pages
        self.visited_urls = set()
        self.scraped_data = []
        self.url_queue = deque([base_url])
        self.failed_urls = set()
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Setup Selenium WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            self.driver = None
        
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = True

    def normalize_url(self, url):
        """Remove fragments and query params to get the base URL"""
        if not url:
            return None
        
        parsed = urlparse(url)
        # Remove fragment (everything after #) and query parameters
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        
        # Remove trailing slash for consistency
        if normalized.endswith('/') and len(normalized) > 1:
            normalized = normalized[:-1]
            
        return normalized

    def is_support_url(self, url):
        """Check if URL is a valid AngelOne support page"""
        if not url:
            return False
            
        # Normalize the URL first
        normalized_url = self.normalize_url(url)
        
        if not normalized_url or normalized_url in self.visited_urls:
            return False
            
        parsed = urlparse(normalized_url)
        
        # Must be AngelOne domain and under /support path
        return (parsed.netloc == 'www.angelone.in' and 
                parsed.path.startswith('/support') and
                normalized_url not in self.failed_urls)

    def discover_all_support_links(self):
        """Discover all support page links from the main support page"""
        all_links = set()
        
        print(f"Discovering support links from: {self.base_url}")
        
        # First, try with requests
        try:
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract all links that start with /support
            for link in soup.find_all('a', href=True):
                href = link['href']
                full_url = urljoin(self.base_url, href)
                normalized_url = self.normalize_url(full_url)
                
                if self.is_support_url(normalized_url):
                    all_links.add(normalized_url)
                    
        except Exception as e:
            print(f"Error with requests approach: {e}")
        
        # Then try with Selenium for dynamic content
        if self.driver:
            try:
                print("Using Selenium to discover more support links...")
                self.driver.get(self.base_url)
                
                # Wait for page to load
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Scroll to load all content
                last_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_pause_time = 2
                
                while True:
                    # Scroll down to bottom
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause_time)
                    
                    # Calculate new scroll height and compare with last height
                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height
                
                # Try to click any expandable sections or "View All" buttons
                expandable_selectors = [
                    'button[class*="expand"]', 'button[class*="more"]', 
                    'a[class*="view-all"]', 'a[class*="show-all"]',
                    '.expandable', '.collapsible', '[data-toggle]'
                ]
                
                for selector in expandable_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            if element.is_displayed() and element.is_enabled():
                                self.driver.execute_script("arguments[0].click();", element)
                                time.sleep(1)
                    except Exception as e:
                        continue
                
                # Extract all links from the fully loaded page
                selenium_soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                for link in selenium_soup.find_all('a', href=True):
                    href = link['href']
                    full_url = urljoin(self.base_url, href)
                    normalized_url = self.normalize_url(full_url)
                    
                    if self.is_support_url(normalized_url):
                        all_links.add(normalized_url)
                        
            except Exception as e:
                print(f"Selenium discovery error: {e}")
        
        print(f"Discovered {len(all_links)} unique support page links")
        return list(all_links)

    def extract_support_links_from_page(self, url, soup):
        """Extract additional support links from a scraped page"""
        links = set()
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            normalized_url = self.normalize_url(full_url)
            
            if self.is_support_url(normalized_url):
                links.add(normalized_url)
        
        return links

    def scrape_page_content(self, url):
        """Scrape content from a support page"""
        try:
            print(f"Scraping: {url}")
            
            # Try requests first
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for additional support links on this page (normalized)
            new_links = self.extract_support_links_from_page(url, soup)
            for link in new_links:
                if link not in self.visited_urls and link not in [self.normalize_url(u) for u in self.url_queue]:
                    self.url_queue.append(link)
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            
            # Extract title
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text().strip()
            
            # Look for main content with support-specific selectors
            content_selectors = [
                '.support-content', '.help-content', '.faq-content',
                '.article-content', '.main-content', '.content',
                'main', 'article', '.container .row', '.container'
            ]
            
            content_text = ""
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    content_text = self.html_converter.handle(str(content_element))
                    break
            
            # Fallback to body content
            if not content_text:
                body = soup.find('body')
                if body:
                    content_text = self.html_converter.handle(str(body))
            
            # Clean the text
            content_text = self.clean_text(content_text)
            
            # Try Selenium if content is insufficient
            if len(content_text) < 200 and self.driver:
                selenium_content = self.scrape_with_selenium(url)
                if selenium_content and len(selenium_content) > len(content_text):
                    content_text = selenium_content
            
            if content_text and len(content_text.strip()) > 50:
                return {
                    'url': url,
                    'title': title,
                    'content': content_text,
                    'content_length': len(content_text),
                    'source_type': 'support_page',
                    'timestamp': time.time()
                }
            else:
                print(f"Insufficient content found for {url}")
                return None
                
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            self.failed_urls.add(url)
            return None

    def scrape_with_selenium(self, url):
        """Scrape content using Selenium for dynamic pages"""
        if not self.driver:
            return ""
            
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait for content to load
            time.sleep(3)
            
            # Scroll to ensure all content loads
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            
            # Try to find main content
            content_selectors = [
                '.support-content', '.help-content', '.faq-content',
                '.article-content', '.main-content', '.content',
                'main', 'article'
            ]
            
            for selector in content_selectors:
                content_element = soup.select_one(selector)
                if content_element:
                    return self.clean_text(self.html_converter.handle(str(content_element)))
            
            # Fallback to body
            body = soup.find('body')
            if body:
                return self.clean_text(self.html_converter.handle(str(body)))
                
        except Exception as e:
            print(f"Selenium scraping error on {url}: {e}")
        
        return ""

    def clean_text(self, text):
        """Clean and normalize text content"""
        if not text:
            return ""
        
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and len(line) > 3:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def crawl_all_support_pages(self):
        """Crawl all discovered support pages"""
        print("Starting focused support page crawling...")
        
        # First, discover all support links from the main page
        discovered_links = self.discover_all_support_links()
        
        # Add discovered links to queue (normalized)
        for link in discovered_links:
            normalized_link = self.normalize_url(link)
            if normalized_link and normalized_link not in [self.normalize_url(u) for u in self.url_queue]:
                self.url_queue.append(normalized_link)
        
        # Remove duplicates from queue
        unique_queue = []
        seen = set()
        for url in self.url_queue:
            normalized = self.normalize_url(url)
            if normalized and normalized not in seen:
                unique_queue.append(normalized)
                seen.add(normalized)
        
        self.url_queue = deque(unique_queue)
        
        print(f"Total unique support pages to crawl: {len(self.url_queue)}")
        
        scraped_count = 0
        
        while self.url_queue and scraped_count < self.max_pages:
            url = self.url_queue.popleft()
            
            # Normalize URL before checking if visited
            normalized_url = self.normalize_url(url)
            
            if normalized_url in self.visited_urls:
                continue
            
            print(f"Progress: {scraped_count + 1} | Remaining: {len(self.url_queue)} | URL: {normalized_url}")
            
            content = self.scrape_page_content(normalized_url)
            if content:
                self.scraped_data.append(content)
                scraped_count += 1
                print(f"✓ Successfully scraped ({content['content_length']} chars)")
            else:
                print(f"✗ Failed to scrape")
            
            self.visited_urls.add(normalized_url)
            
            # Rate limiting
            time.sleep(1)
            
            # Progress update every 20 pages
            if scraped_count % 20 == 0 and scraped_count > 0:
                print(f"\n--- Progress Update ---")
                print(f"Successfully scraped: {scraped_count} pages")
                print(f"Remaining in queue: {len(self.url_queue)}")
                print(f"Failed URLs: {len(self.failed_urls)}")
                print("----------------------\n")
        
        print(f"\nSupport page crawling completed!")
        print(f"Successfully scraped: {len(self.scraped_data)} support pages")
        print(f"Total URLs processed: {len(self.visited_urls)}")
        print(f"Failed URLs: {len(self.failed_urls)}")
        
        return self.scraped_data

    def save_data(self, filename="angelone_support_focused.json"):
        """Save scraped support data"""
        try:
            summary = {
                "crawl_info": {
                    "base_url": self.base_url,
                    "total_pages_scraped": len(self.scraped_data),
                    "total_content_size": sum(len(item['content']) for item in self.scraped_data),
                    "failed_urls_count": len(self.failed_urls),
                    "crawl_timestamp": time.time()
                },
                "support_pages": self.scraped_data,
                "failed_urls": list(self.failed_urls) if self.failed_urls else []
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(f"Support data saved to {filename}")
            
        except Exception as e:
            print(f"Error saving data: {e}")

    def close(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()

def main():
    """Main function to run the focused support scraper"""
    scraper = AngelOneWebCrawler(max_pages=1000)
    
    try:
        print("Starting AngelOne Support Pages Scraper")
        print("Target: https://www.angelone.in/support and all sub-pages")
        print("=" * 50)
        
        # Crawl all support pages
        data = scraper.crawl_all_support_pages()
        
        # Save the data
        scraper.save_data("angelone_support_pages.json")
        
        # Print summary
        print(f"\n=== SUPPORT SCRAPING SUMMARY ===")
        print(f"Total support pages scraped: {len(data)}")
        if data:
            total_chars = sum(len(item['content']) for item in data)
            print(f"Total content: {total_chars:,} characters")
            print(f"Average per page: {total_chars // len(data):,} characters")
            
            print(f"\nSample pages scraped:")
            for i, page in enumerate(data[:5], 1):
                print(f"{i}. {page['title'][:60]}...")
                print(f"   URL: {page['url']}")
                print(f"   Content: {len(page['content'])} chars")
        
        print("\nFocused support scraping completed successfully!")
            
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()