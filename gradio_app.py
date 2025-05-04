import gradio as gr
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
            
            # Extract materials (IKEA often has materials in specifications)
            self._extract_materials(soup, result)

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
    
    def _extract_materials(self, soup: BeautifulSoup, result: ExtractionResult) -> None:
        """Extract product materials information"""
        # Look for materials in product details
        materials_section = soup.select_one('div.pip-product-details__container')
        if materials_section:
            material_headers = materials_section.select('h3, h4')
            for header in material_headers:
                if 'material' in header.get_text().lower():
                    # Get the next paragraphs after this header
                    materials_content = []
                    next_element = header.next_sibling
                    while next_element and not (next_element.name == 'h3' or next_element.name == 'h4'):
                        if next_element.name == 'p':
                            materials_content.append(next_element.get_text(strip=True))
                        next_element = next_element.next_sibling
                    
                    if materials_content:
                        result.materials['materials'] = ' '.join(materials_content)


# Create a singleton instance
extractor = ProductExtractor()

def get_product_data_from_url(url):
    """
    Retrieve product data (images, measurements, materials) from a URL directly.
    
    Args:
        url: Product URL to extract data from
        
    Returns:
        Tuple of (image_list, measurements_str, materials_str)
    """
    try:
        # Extract data directly instead of using API
        extraction_result = extractor.extract_images_from_url(url)
        data = extraction_result.to_dict()

        # Extract images
        images = [img["url"] for img in data.get("images", {}).values()]
        
        # Format measurements into markdown
        measurements = data.get("measurements", {})
        if measurements:
            measurements_str = "\n".join([f"- **{k.title()}**: {v}" for k, v in measurements.items()])
        else:
            measurements_str = "No measurements found."
            
        # Format materials into markdown
        materials = data.get("materials", {})
        if materials:
            materials_str = "\n".join([f"- **{k.title()}**: {v}" for k, v in materials.items()])
        else:
            materials_str = "No materials information found."

        return images, measurements_str, materials_str

    except Exception as e:
        error_message = f"Error: {str(e)}"
        return [], error_message, error_message

def create_interface():
    """Create and configure the Gradio interface"""
    with gr.Blocks(title="IKEA Product Image + Measurement Extractor") as demo:
        gr.Markdown("## IKEA Product Image + Measurement Extractor")
        gr.Markdown("Enter an IKEA product URL to extract images, measurements, and materials information.")
        
        with gr.Row():
            with gr.Column(scale=1):
                # Input section
                url_input = gr.Textbox(
                    label="Product URL", 
                    placeholder="https://www.ikea.com/product/...",
                    info="Paste IKEA product URL here"
                )
                submit_btn = gr.Button("Extract Product Data", variant="primary")
                
                # Results section - Measurements and Materials
                with gr.Accordion("Product Information", open=True):
                    measurements_display = gr.Markdown(label="Measurements")
                    materials_display = gr.Markdown(label="Materials")
                    
            with gr.Column(scale=2):
                # Gallery component for displaying images
                image_gallery = gr.Gallery(
                    label="Product Images",
                    show_label=True,
                    columns=2,
                    height=500,
                    object_fit="contain"
                )

        # Add example URLs
        gr.Examples(
            examples=[
                ["https://www.ikea.com/ca/en/p/hammaroen-pergola-gray-beige-dark-gray-beige-20549239/"],
                ["https://www.ikea.com/ca/en/p/fniss-trash-can-white-40295439/"],
                ["https://www.ikea.com/ca/en/p/klimpfjaell-norraryd-table-and-6-chairs-gray-brown-black-s99418424/"]
            ],
            inputs=url_input
        )

        # Set up the click event
        submit_btn.click(
            fn=get_product_data_from_url,
            inputs=url_input,
            outputs=[image_gallery, measurements_display, materials_display]
        )
        
    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch()