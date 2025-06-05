import os
import requests
from bs4 import BeautifulSoup
import trafilatura
from tqdm import tqdm
import json
import time
import logging
import re
from urllib.parse import urljoin
import magic  # For file type detection

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = os.environ.get('OUTPUT_DIR', '/app/data/documents')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Comprehensive list of Red Hat documentation bases
BASE_URLS = [
    "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux",
    "https://access.redhat.com/documentation/en-us/openshift_container_platform",
    "https://access.redhat.com/documentation/en-us/red_hat_jboss_enterprise_application_platform",
    "https://access.redhat.com/documentation/en-us/red_hat_openshift_data_foundation",
    "https://access.redhat.com/documentation/en-us/red_hat_ansible_automation_platform",
    "https://access.redhat.com/documentation/en-us/red_hat_ceph_storage",
    "https://access.redhat.com/documentation/en-us/red_hat_openstack_platform",
    "https://access.redhat.com/documentation/en-us/red_hat_build_of_quarkus",
    "https://access.redhat.com/documentation/en-us/red_hat_build_of_node.js",
    "https://access.redhat.com/documentation/en-us/red_hat_satellite",
]

# User agent to mimic a browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml',
    'Accept-Language': 'en-US,en;q=0.9',
}

class RedHatDocScraper:
    def __init__(self, output_dir=OUTPUT_DIR, base_urls=BASE_URLS):
        self.output_dir = output_dir
        self.base_urls = base_urls
        self.all_doc_urls = []
        self.processed_count = 0
        
    def get_product_versions(self, base_url):
        """Get all product versions from a base product URL"""
        versions = []
        try:
            response = requests.get(base_url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Look for version links
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    # Look for version numbers in URLs
                    if re.search(r'/\d+(\.\d+)*$', href) and href.startswith('/documentation'):
                        full_url = urljoin("https://access.redhat.com", href)
                        if full_url not in versions:
                            versions.append(full_url)
                            logger.info(f"Found product version: {full_url}")
        except Exception as e:
            logger.error(f"Error getting product versions for {base_url}: {e}")
        
        return versions

    def get_documentation_urls(self, version_url):
        """Get all documentation URLs for a product version"""
        doc_urls = []
        
        # First try the documentation landing page
        try:
            logger.info(f"Fetching documentation from: {version_url}")
            response = requests.get(version_url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for links to documentation guides
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/html/' in href and href.startswith('/documentation'):
                        full_url = urljoin("https://access.redhat.com", href)
                        if full_url not in doc_urls:
                            doc_urls.append(full_url)
        except Exception as e:
            logger.error(f"Error getting documentation from {version_url}: {e}")
        
        # Try the HTML/single-page version which might have a TOC
        single_page_url = f"{version_url}/html-single/index/"
        try:
            logger.info(f"Fetching single-page index from: {single_page_url}")
            response = requests.get(single_page_url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for TOC links
                for link in soup.select('.toc a[href]'):
                    href = link.get('href')
                    if href and href.startswith('/documentation'):
                        full_url = urljoin("https://access.redhat.com", href)
                        if full_url not in doc_urls:
                            doc_urls.append(full_url)
        except Exception as e:
            logger.error(f"Error getting single-page index from {single_page_url}: {e}")
        
        # Try any sitemap if available
        sitemap_url = f"{version_url}/sitemap"
        try:
            logger.info(f"Fetching sitemap from: {sitemap_url}")
            response = requests.get(sitemap_url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for links in sitemap
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href.startswith('/documentation') and ('/html/' in href or '/html-single/' in href):
                        full_url = urljoin("https://access.redhat.com", href)
                        if full_url not in doc_urls:
                            doc_urls.append(full_url)
        except Exception as e:
            logger.error(f"Error getting sitemap from {sitemap_url}: {e}")
        
        # Log summary
        logger.info(f"Found {len(doc_urls)} documentation pages for {version_url}")
        return doc_urls

    def download_and_extract_content(self, url):
        """Download and extract content from a documentation URL"""
        try:
            logger.info(f"Downloading content from: {url}")
            downloaded = trafilatura.fetch_url(url, headers=HEADERS)
            if not downloaded:
                logger.error(f"Failed to download content from {url}")
                return None
                
            content = trafilatura.extract(downloaded, include_comments=False, 
                                         include_tables=True, output_format='json')
            if content:
                data = json.loads(content)
                # Add additional metadata for better organization
                metadata = {
                    'url': url,
                    'title': data.get('title', ''),
                    'text': data.get('text', ''),
                    'timestamp': time.time(),
                    'product': self._extract_product_from_url(url),
                    'version': self._extract_version_from_url(url),
                    'document_type': self._extract_document_type_from_url(url)
                }
                return metadata
            else:
                logger.error(f"Failed to extract content from {url}")
        except Exception as e:
            logger.error(f"Error processing {url}: {e}")
        return None

    def _extract_product_from_url(self, url):
        """Extract product name from URL"""
        match = re.search(r'/documentation/en-us/([^/]+)', url)
        if match:
            return match.group(1).replace('_', ' ').title()
        return "Unknown Product"

    def _extract_version_from_url(self, url):
        """Extract version from URL"""
        match = re.search(r'/(\d+(\.\d+)*)/', url)
        if match:
            return match.group(1)
        return "Unknown Version"

    def _extract_document_type_from_url(self, url):
        """Extract document type from URL"""
        if '/html-single/' in url:
            return "Single Page HTML"
        elif '/html/' in url:
            return "HTML"
        elif '/pdf/' in url:
            return "PDF"
        elif '/epub/' in url:
            return "EPUB"
        return "Unknown Type"

    def save_document(self, doc_data, index):
        """Save document to file with proper error handling"""
        if not doc_data or not doc_data.get('text') or len(doc_data['text']) < 100:
            return False
            
        try:
            # Create a more descriptive filename
            product = re.sub(r'[^a-zA-Z0-9]', '_', doc_data['product'])
            version = re.sub(r'[^a-zA-Z0-9]', '_', doc_data['version'])
            doc_type = re.sub(r'[^a-zA-Z0-9]', '_', doc_data.get('document_type', 'unknown'))
            
            filename = f"{self.output_dir}/{product}_{version}_{doc_type}_{index}.json"
            
            with open(filename, 'w') as f:
                json.dump(doc_data, f, indent=2)
            logger.info(f"Saved document {index}: {doc_data['title']} ({len(doc_data['text'])} chars)")
            self.processed_count += 1
            return True
        except Exception as e:
            logger.error(f"Error saving document {index}: {e}")
            return False

    def run(self):
        """Run the scraper to collect all Red Hat documentation"""
        logger.info("Starting Red Hat documentation scraper")
        
        # Get all product versions
        all_versions = []
        for base_url in self.base_urls:
            versions = self.get_product_versions(base_url)
            all_versions.extend(versions)
        
        logger.info(f"Found {len(all_versions)} product versions")
        
        # Get all documentation URLs for each version
        for version_url in all_versions:
            doc_urls = self.get_documentation_urls(version_url)
            self.all_doc_urls.extend(doc_urls)
        
        # Deduplicate URLs
        self.all_doc_urls = list(set(self.all_doc_urls))
        logger.info(f"Found total of {len(self.all_doc_urls)} unique documentation pages")
        
        # Process each URL
        for i, url in enumerate(tqdm(self.all_doc_urls)):
            doc_data = self.download_and_extract_content(url)
            if doc_data:
                self.save_document(doc_data, i)
            
            # Be respectful with rate limiting
            time.sleep(1)
        
        logger.info(f"Scraping complete. Successfully processed {self.processed_count} documents.")

if __name__ == "__main__":
    scraper = RedHatDocScraper()
    scraper.run()
