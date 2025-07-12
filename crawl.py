"""
This script find ALL documents and content on a website.
"""

import argparse
import os
import shutil
import logging
import json
import time
import hashlib
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Set, List


class DeepWebCrawler:
    
    def __init__(self, base_url: str, output_dir: str = "scraped_content", max_workers: int = 8):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.base_path = urlparse(base_url).path.rstrip('/')
        self.output_dir = Path(output_dir)
        self.max_workers = max_workers
        
        # State tracking so that we can resume if interrupted
        self.state_file = self.output_dir / "crawl_state.json"
        self.visited_urls: Set[str] = set()
        self.pending_urls: Set[str] = set([base_url])
        self.downloaded_files: Set[str] = set()
        
        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'documents_downloaded': 0,
            'text_files_saved': 0,
            'total_size': 0,
            'file_types': {}
        }
        
        # Thread safety
        self.url_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        
        # Setup
        self.setup_directories()
        self.setup_session()
        self.load_state()
        
        # Document extensions we want to download
        self.document_extensions = {
            '.pdf', '.doc', '.docx', '.txt', '.odt', '.rtf',
            '.xls', '.xlsx', '.csv', '.ppt', '.pptx'
        }
        
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def setup_directories(self):
        """Create necessary directories"""
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "documents").mkdir(exist_ok=True)
        (self.output_dir / "text_content").mkdir(exist_ok=True)
    
    def setup_session(self):
        """Setup requests session"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        
        # Connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=50,
            pool_maxsize=50,
            max_retries=1
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def save_state(self):
        """Save current state to resume later"""
        state = {
            'visited_urls': list(self.visited_urls),
            'pending_urls': list(self.pending_urls),
            'downloaded_files': list(self.downloaded_files),
            'stats': self.stats,
            'base_url': self.base_url
        }
        
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self):
        """Load state from previous run if exists"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                
                self.visited_urls = set(state.get('visited_urls', []))
                self.pending_urls = set(state.get('pending_urls', [self.base_url]))
                self.downloaded_files = set(state.get('downloaded_files', []))
                self.stats = state.get('stats', self.stats)
                
                self.logger.info(f"Resumed from previous state:")
                self.logger.info(f"{len(self.visited_urls)} pages already visited")
                self.logger.info(f"{len(self.pending_urls)} pages remaining")
                self.logger.info(f"{len(self.downloaded_files)} files already downloaded")
                
            except Exception as e:
                self.logger.warning(f"Could not load previous state: {e}")
                self.visited_urls = set()
                self.pending_urls = set([self.base_url])
    
    def is_same_domain_and_path(self, url: str) -> bool:
        """Check if URL belongs to same domain AND is within the specified path"""
        try:
            parsed = urlparse(url)
            
            # Must be same domain
            if parsed.netloc != self.domain:
                return False
            
            # Must start with the base path (stay within the section)
            url_path = parsed.path.rstrip('/')
            
            # If base_path is empty (root), allow everything on the domain
            if not self.base_path:
                return True
            
            # URL must start with the base path to be considered part of the section
            return url_path.startswith(self.base_path)
            
        except:
            return False
    
    
    def should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped"""
        url_lower = url.lower()
        
        # Skip non-content files
        skip_extensions = {'.css', '.js', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico'}
        if any(url_lower.endswith(ext) for ext in skip_extensions):
            return True
        
        # Skip common non-content paths
        skip_patterns = ['/css/', '/js/', '/images/', '/img/', '/assets/']
        if any(pattern in url_lower for pattern in skip_patterns):
            return True
        
        return False
    
    def extract_links(self, soup: BeautifulSoup, current_url: str) -> List[str]:
        """Extract all links from page"""
        links = []
        skipped_outside_section = 0
        
        # Get all links
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            full_url = urljoin(current_url, href)
            
            if not self.is_same_domain_and_path(full_url):
                skipped_outside_section += 1
                continue
                
            if (not self.should_skip_url(full_url) and
                full_url not in self.visited_urls):
                links.append(full_url)
        
        if skipped_outside_section > 0:
            self.logger.debug(f"⏭️  Skipped {skipped_outside_section} links outside target section")
        
        return links
    
    def extract_document_links(self, soup: BeautifulSoup, current_url: str) -> List[str]:
        """Extract document download links"""
        doc_links = []
        
        # Look for direct document links
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            full_url = urljoin(current_url, href)
            
            # Check if it's a document
            if any(ext in full_url.lower() for ext in self.document_extensions):
                if self.is_same_domain_and_path(full_url):
                    doc_links.append(full_url)
        
        # Also check embedded documents
        for tag in soup.find_all(['embed', 'object', 'iframe'], src=True):
            src = tag['src']
            full_url = urljoin(current_url, src)
            
            if any(ext in full_url.lower() for ext in self.document_extensions):
                if self.is_same_domain_and_path(full_url):
                    doc_links.append(full_url)
        
        return doc_links
    
    def download_document(self, url: str) -> bool:
        """Download a document file"""
        try:
            response = self.session.get(url, stream=True, timeout=15)
            response.raise_for_status()
            
            # Determine file extension and name
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path) or f"document_{hashlib.md5(url.encode()).hexdigest()[:8]}"
            
            # Ensure proper extension
            if not any(filename.lower().endswith(ext) for ext in self.document_extensions):
                # Try to get extension from URL
                for ext in self.document_extensions:
                    if ext in url.lower():
                        if not filename.endswith(ext):
                            filename += ext
                        break
                else:
                    filename += ".bin"  # Fallback
            
            filepath = self.output_dir / "documents" / filename
            
            # Download with progress
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = filepath.stat().st_size
            
            with self.stats_lock:
                self.stats['documents_downloaded'] += 1
                self.stats['total_size'] += file_size
                
                # Track file type
                ext = Path(filename).suffix.lower()
                self.stats['file_types'][ext] = self.stats['file_types'].get(ext, 0) + 1
            
            with self.url_lock:
                self.downloaded_files.add(str(filepath))
            
            self.logger.info(f"Downloaded: {filename} ({self._format_size(file_size)})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download {url}: {e}")
            return False
    
    def save_page_content(self, url: str, soup: BeautifulSoup):
        """Save page text content"""
        try:
            # Extract text content
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            text_content = soup.get_text(separator=' ', strip=True)
            text_content = ' '.join(text_content.split())
            
            if len(text_content) < 100:  # Skip very short content
                return
            
            # Create filename
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            parsed_url = urlparse(url)
            path_parts = [part for part in parsed_url.path.split('/') if part]
            
            if path_parts:
                filename_base = '_'.join(path_parts[-2:])
                filename_base = ''.join(c for c in filename_base if c.isalnum() or c in '_-')
            else:
                filename_base = 'homepage'
            
            filename = f"{filename_base}_{url_hash}.txt"
            filepath = self.output_dir / "text_content" / filename
            
            # Save content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"URL: {url}\n")
                f.write(f"Title: {soup.title.get_text() if soup.title else 'No Title'}\n")
                f.write("=" * 50 + "\n\n")
                f.write(text_content)
            
            file_size = filepath.stat().st_size
            
            with self.stats_lock:
                self.stats['text_files_saved'] += 1
                self.stats['total_size'] += file_size
            
            self.logger.info(f"Saved content: {filename} ({self._format_size(file_size)})")
            
        except Exception as e:
            self.logger.error(f"Failed to save content for {url}: {e}")
    
    def crawl_page(self, url: str) -> List[str]:
        """Crawl a single page and return new URLs found"""
        new_urls = []
        
        with self.url_lock:
            if url in self.visited_urls:
                return []
            self.visited_urls.add(url)
            self.pending_urls.discard(url)
        
        try:
            self.logger.info(f"Crawling: {url}")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '').lower()
            
            if 'text/html' in content_type:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract and download documents
                doc_links = self.extract_document_links(soup, url)
                for doc_url in doc_links:
                    if doc_url not in self.downloaded_files:
                        self.download_document(doc_url)
                
                # Save page content
                self.save_page_content(url, soup)
                
                # Extract new page links
                page_links = self.extract_links(soup, url)
                new_urls.extend(page_links)
                
                with self.stats_lock:
                    self.stats['pages_crawled'] += 1
                
                self.logger.info(f"Found {len(doc_links)} documents, {len(page_links)} new pages")
            
            elif any(ext in content_type for ext in ['pdf', 'document', 'msword', 'spreadsheet']):
                # This is a direct document link
                self.download_document(url)
            
        except Exception as e:
            self.logger.error(f"Error crawling {url}: {e}")
        
        return new_urls
    
    def crawl_website_deep(self):
        """Main crawling method - goes DEEP until no more links"""
        self.logger.info(f"Starting crawl of {self.base_url}")
        self.logger.info(f"Restricted to section: {self.base_path or '(entire domain)'}")
        self.logger.info(f"Max workers: {self.max_workers}")
        
        try:
            while self.pending_urls:
                current_batch = list(self.pending_urls)[:self.max_workers * 2]
                
                # Update pending URLs
                with self.url_lock:
                    for url in current_batch:
                        self.pending_urls.discard(url)
                
                self.logger.info(f"Processing {len(current_batch)} URLs | "
                               f"Visited: {len(self.visited_urls)} | "
                               f"Pending: {len(self.pending_urls)} | "
                               f"Documents: {self.stats['documents_downloaded']}")
                
                # Process batch in parallel
                new_urls = []
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_url = {executor.submit(self.crawl_page, url): url for url in current_batch}
                    
                    for future in as_completed(future_to_url):
                        try:
                            urls = future.result()
                            new_urls.extend(urls)
                        except Exception as e:
                            url = future_to_url[future]
                            self.logger.error(f"Error processing {url}: {e}")
                
                # Add new URLs to pending
                with self.url_lock:
                    for url in new_urls:
                        if url not in self.visited_urls:
                            self.pending_urls.add(url)
                
                # Save state periodically
                self.save_state()
                
                # let us pause and respect these niggers
                time.sleep(0.1)
        
        except KeyboardInterrupt:
            self.logger.info("Crawl interrupted by user. State saved for resume.")
            self.save_state()
            raise
        
        except Exception as e:
            self.logger.error(f"Crawl failed: {e}")
            self.save_state()
            raise
        
        finally:
            self.show_final_stats()
    
    def show_final_stats(self):
        """Show comprehensive final statistics"""
        # Count actual files
        doc_files = list((self.output_dir / "documents").glob("*"))
        text_files = list((self.output_dir / "text_content").glob("*.txt"))
        
        total_size = sum(f.stat().st_size for f in doc_files + text_files if f.is_file())
        
        print("\n" + "Deep Crawl Completed" + "\n" + "=" * 50)
        print(f"Website: {self.base_url}")
        print(f"Pages crawled: {len(self.visited_urls):,}")
        print(f"Total files found: {len(doc_files) + len(text_files):,}")
        
        # File type breakdown
        file_types = {}
        for f in doc_files:
            ext = f.suffix.lower()
            file_types[ext] = file_types.get(ext, 0) + 1
        
        if file_types:
            print("Document breakdown:")
            for ext, count in sorted(file_types.items()):
                size = sum(f.stat().st_size for f in doc_files if f.suffix.lower() == ext)
                print(f"   {ext.upper()}: {count} files ({self._format_size(size)})")
        
        print(f"Text files (webpage content): {len(text_files):,}")
        print(f"Total size: {self._format_size(total_size)}")
        print("ALL CONTENT READY FOR RAG!")
        print("=" * 50)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )


def crawl_website_comprehensive(url: str, output_dir: str = "scraped_content", max_workers: int = 10):
    """Use the crawler to get ALL content"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Starting crawl of {url}")
    logger.info("This crawler will find EVERY document and page on the website")
    logger.info("can even continue if interrupted")
    
    crawler = DeepWebCrawler(
        base_url=url,
        output_dir=output_dir,
        max_workers=max_workers
    )
    
    crawler.crawl_website_deep()
    
    # Prepare content for RAG
    prepare_rag_content(output_dir)
    
    return output_dir


def prepare_rag_content(scraped_dir: str):
    """Prepare all content for RAG processing in a single directory"""
    logger = logging.getLogger(__name__)
    scraped_path = Path(scraped_dir)
    rag_content_dir = Path("actual_scraped_content")
    
    # Clean and recreate directory
    if rag_content_dir.exists():
        shutil.rmtree(rag_content_dir)
    rag_content_dir.mkdir()
    
    # Copy all files from both subdirectories
    total_files = 0
    total_size = 0
    
    for subdir in ["documents", "text_content"]:
        source_dir = scraped_path / subdir
        if source_dir.exists():
            for file_path in source_dir.iterdir():
                if file_path.is_file():
                    dest_path = rag_content_dir / file_path.name
                    shutil.copy2(file_path, dest_path)
                    total_files += 1
                    total_size += file_path.stat().st_size
                    logger.info(f"Copied: {file_path.name}")
    
    print(f"\nRAG CONTENT PREPARED!")
    print(f"Total files ready: {total_files:,}")
    print(f"Total size: {_format_size(total_size)}")
    print(f"Location: {rag_content_dir.absolute()}")
    print("Ready for RAG processing!")


def _format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def main():
    parser = argparse.ArgumentParser(
        description="Web Crawler for RAG Pipeline", 
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This crawler will find EVERY document and page on the target website:
- PDFs, DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT files
- All webpage content saved as text files
- Resume functionality if interrupted
- Comprehensive statistics and reporting

Examples:
  %(prog)s https://example.com
  %(prog)s https://example.com --output my_crawl --workers 8
        """
    )
    
    parser.add_argument("url", help="Base URL to crawl")
    parser.add_argument("--output", "-o", default="scraped_content", help="Output directory (default: scraped_content)")
    parser.add_argument("--workers", "-w", type=int, default=10, help="Number of worker threads (default: 10)")
    
    args = parser.parse_args()
    
    setup_logging()
    
    try:
        output_dir = crawl_website_comprehensive(args.url, args.output, args.workers)
        print(f"\ncrawl complete!")
        print(f"All content ready in: actual_scraped_content/")
        print(f"Detailed report: {output_dir}/crawl_state.json")
        
    except KeyboardInterrupt:
        print("\nCrawl interrupted. State saved - can resume by running again.")
    except Exception as e:
        print(f"\nCrawl failed: {e}")


if __name__ == "__main__":
    main()
