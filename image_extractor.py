"""
Image Extractor Module

This module extracts high-resolution product images and measurements from web pages.
Designed primarily for IKEA product pages but can be extended for other sites.
"""

import uuid
import re
import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ImageInfo:
    """Class for storing image information"""
    url: str
    alt: str = ""
    type: str = "unknown"
    path: Optional[str] = None
    id: Optional[str] = None


@dataclass
class ExtractionResult:
    """Class for storing the results of a webpage extraction"""
    request_id: str
    images: Dict[str, ImageInfo] = field(default_factory=dict)
    measurements: Dict[str, str] = field(default_factory=dict)
    materials: Dict[str, str] = field(default_factory=dict)
    output_dir: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the extraction result to a dictionary"""
        images_dict = {
            img_id: {
                "id": img_id,
                "url": img_info.url,
                "alt": img_info.alt,
                "type": img_info.type,
                "path": img_info.path
            } for img_id, img_info in self.images.items()
        }
        
        return {
            "request_id": self.request_id,
            "images": images_dict,
            "measurements": self.measurements,
            "materials": self.materials,
            "output_dir": self.output_dir
        }


class SrcsetParser:
    """Helper class for parsing srcset attributes from HTML img tags"""
    
    @staticmethod
    def parse_srcset(srcset: str) -> List[Dict[str, Any]]:
        """
        Parse a srcset attribute into a structured list of image URLs and descriptors.
        
        Args:
            srcset: The srcset attribute from an img tag
            
        Returns:
            List of dictionaries containing parsed srcset components
        """
        if not srcset:
            return []
        
        results = []
        srcset_parts = [part.strip() for part in srcset.split(',')]
        
        for part in srcset_parts:
            parts = part.split()
            if len(parts) < 2:
                continue
                
            url = parts[0]
            descriptor = parts[1]
            
            try:
                width = int(re.search(r'\d+', descriptor).group(0)) if re.search(r'\d+', descriptor) else 0
                results.append({"url": url, "descriptor": descriptor, "width": width})
            except (AttributeError, ValueError):
                continue
                
        return results
    
    @classmethod
    def extract_f_xl_image(cls, srcset: str) -> Optional[str]:
        """
        Extract specifically the image URL with f=xl 900w from a srcset attribute.
        
        Args:
            srcset: The srcset attribute from an img tag
            
        Returns:
            The URL with f=xl 900w descriptor or None if not found
        """
        if not srcset:
            return None
        
        srcset_entries = cls.parse_srcset(srcset)
        
        # First, look for f=xl with 900w
        for entry in srcset_entries:
            if "f=xl" in entry["url"] and entry["descriptor"] == "900w":
                return entry["url"]
        
        # If not found, try any 900w image
        for entry in srcset_entries:
            if entry["descriptor"] == "900w":
                return entry["url"]
        
        # Finally, fall back to highest resolution
        if srcset_entries:
            srcset_entries.sort(key=lambda x: x["width"], reverse=True)
            return srcset_entries[0]["url"]
        
        return None


class ImageDownloader:
    """Helper class for downloading images"""
    
    @staticmethod
    def download_image(image_url: str, save_path: str) -> Optional[str]:
        """
        Download an image from URL and save it to disk.
        
        Args:
            image_url: URL of the image to download
            save_path: Path where the image will be saved
            
        Returns:
            The path to the saved image or None if download failed
        """
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # Get the image content
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            
            # Save the image
            img = Image.open(BytesIO(response.content))
            img.save(save_path)
            
            logger.info(f"Image saved to {save_path}")
            return save_path
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image: {e}")
            return None
        except IOError as e:
            logger.error(f"Error saving image: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while downloading image: {e}")
            return None


class WebPageFetcher:
    """Helper class for fetching web pages"""
    
    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    @classmethod
    def fetch_page(cls, url: str) -> Tuple[str, BeautifulSoup]:
        """
        Fetch a web page and return its content as text and parsed BeautifulSoup.
        
        Args:
            url: The URL to fetch
            
        Returns:
            Tuple containing (raw_html, parsed_soup)
            
        Raises:
            requests.exceptions.RequestException: If the request fails
        """
        logger.info(f"Fetching page: {url}")
        response = requests.get(url, headers=cls.DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        return html, soup


class ProductExtractor:
    """Main class for extracting product information"""
    
    def __init__(self):
        self.srcset_parser = SrcsetParser()
        self.image_downloader = ImageDownloader()
    
    def extract_images_from_url(self, url: str) -> ExtractionResult:
        """
        Extract images with preference for f=xl 900w versions from a URL.
        
        Args:
            url: The URL to extract images from
            
        Returns:
            ExtractionResult object with extracted image information
            
        Raises:
            requests.exceptions.RequestException: If the request fails
            ValueError: If the HTML cannot be parsed correctly
        """
        try:
            logger.info(f"Extracting images from: {url}")
            
            # Fetch the HTML content
            _, soup = WebPageFetcher.fetch_page(url)
            
            # Generate a UUID for this request
            request_uuid = str(uuid.uuid4())
            logger.info(f"Generated request ID: {request_uuid}")
            
            # Initialize result
            result = ExtractionResult(request_id=request_uuid)

            # Extract images
            self._extract_main_product_image(soup, result, request_uuid)
            self._extract_measurement_image(soup, result, request_uuid)
            
            # If no specific images found, try general approach
            if not result.images:
                self._extract_images_general_approach(soup, result, request_uuid)

            # Extract measurements
            self._extract_measurements(soup, result)

            logger.info(f"Total images found: {len(result.images)}")
            logger.info(f"Measurements extracted: {result.measurements}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Error extracting images: {e}")
            raise
    
    def _extract_main_product_image(self, soup: BeautifulSoup, result: ExtractionResult, request_uuid: str) -> None:
        """Extract the main product image"""
        main_image_element = soup.select_one('div[data-type="MAIN_PRODUCT_IMAGE"] img.pip-image')
        if main_image_element and main_image_element.get('srcset'):
            srcset = main_image_element.get('srcset')
            target_url = self.srcset_parser.extract_f_xl_image(srcset)
            if target_url:
                logger.info(f"Found main product image: {target_url}")
                image_id = f"{request_uuid}-main"
                result.images[image_id] = ImageInfo(
                    id=image_id,
                    url=target_url,
                    alt=main_image_element.get('alt', ''),
                    type="main"
                )
    
    def _extract_measurement_image(self, soup: BeautifulSoup, result: ExtractionResult, request_uuid: str) -> None:
        """Extract the measurement illustration image"""
        measurement_image_element = soup.select_one('div[data-type="MEASUREMENT_ILLUSTRATION"] img.pip-image')
        if measurement_image_element and measurement_image_element.get('srcset'):
            srcset = measurement_image_element.get('srcset')
            target_url = self.srcset_parser.extract_f_xl_image(srcset)
            if target_url:
                logger.info(f"Found measurement image: {target_url}")
                image_id = f"{request_uuid}-measurement"
                result.images[image_id] = ImageInfo(
                    id=image_id,
                    url=target_url,
                    alt=measurement_image_element.get('alt', ''),
                    type="measurement"
                )
    
    def _extract_images_general_approach(self, soup: BeautifulSoup, result: ExtractionResult, request_uuid: str) -> None:
        """Extract images using a more general approach"""
        logger.info("No specific images found, trying general approach...")
        for i, img in enumerate(soup.select('img[srcset]')):
            srcset = img.get('srcset')
            target_url = self.srcset_parser.extract_f_xl_image(srcset)
            if target_url:
                img_type = self._determine_image_type(img)
                logger.info(f"Found {img_type} image: {target_url}")
                image_id = f"{request_uuid}-{img_type}-{i}"
                result.images[image_id] = ImageInfo(
                    id=image_id,
                    url=target_url,
                    alt=img.get('alt', ''),
                    type=img_type
                )
    
    def _determine_image_type(self, img_element: BeautifulSoup) -> str:
        """Determine the type of image based on its context"""
        parent_html = str(img_element.parent.parent)
        if "MAIN_PRODUCT_IMAGE" in parent_html or "main" in parent_html.lower():
            return "main"
        elif "MEASUREMENT" in parent_html or "measurement" in parent_html.lower():
            return "measurement"
        return "unknown"
    
    def _extract_measurements(self, soup: BeautifulSoup, result: ExtractionResult) -> None:
        """Extract product measurements"""
        dimensions_ul = soup.select_one('ul.pip-product-dimensions__dimensions-container')
        if dimensions_ul:
            for li in dimensions_ul.select('li.pip-product-dimensions__measurement-wrapper'):
                label_span = li.select_one('span.pip-product-dimensions__measurement-name')
                if label_span:
                    label = label_span.get_text(strip=True).replace(":", "")
                    full_text = li.get_text(strip=True)
                    value = full_text.replace(label_span.get_text(), '').strip()
                    result.measurements[label.lower()] = value
    
    def process_product_page(self, url: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a product page to extract and save high-resolution images.
        
        Args:
            url: The product page URL
            output_dir: Optional custom output directory
            
        Returns:
            Dictionary with paths to downloaded images and other product information
        """
        # Extract images and measurements
        extraction_result = self.extract_images_from_url(url)
        
        # Create a directory for the images using the request ID
        if not output_dir:
            output_dir = f"output/{extraction_result.request_id}"
        
        extraction_result.output_dir = output_dir
        
        # Process all extracted images
        downloaded_images = {}
        
        for image_id, image_info in extraction_result.images.items():
            # Determine filename based on image type
            image_type = image_info.type
            file_ext = os.path.splitext(image_info.url.split('?')[0])[1] or '.jpg'
            filename = f"{image_type}{file_ext}"
            
            # Download the image
            save_path = os.path.join(output_dir, filename)
            image_path = self.image_downloader.download_image(image_info.url, save_path)
            
            if image_path:
                image_info.path = image_path
                downloaded_images[image_type] = {
                    'id': image_id,
                    'path': image_path,
                    'url': image_info.url,
                    'alt': image_info.alt,
                    'type': image_type
                }
        
        logger.info(f"Images downloaded to directory: {output_dir}")
        
        return extraction_result.to_dict()


# Create a singleton instance for easy import
extractor = ProductExtractor()

# Export the main functions for API use
extract_images_from_url = extractor.extract_images_from_url
process_product_page = extractor.process_product_page
download_image = ImageDownloader.download_image