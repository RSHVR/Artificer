"""
Image Extractor API

A FastAPI application for extracting high-resolution product images from web pages.
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, HttpUrl, Field
import os
import uuid
from typing import Dict, Any, Optional, List, Union
import logging
import uvicorn
import time

# Import from our refactored image_extractor module
from image_extractor import extract_images_from_url, download_image, process_product_page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define API Models
class ExtractImageRequest(BaseModel):
    """Request model for image extraction"""
    url: HttpUrl = Field(..., description="URL of the product page to extract images from")
    download_images: bool = Field(True, description="Whether to download the images or just return URLs")
    custom_output_dir: Optional[str] = Field(None, description="Optional custom directory to save images to")

    class Config:
        schema_extra = {
            "example": {
                "url": "https://www.ikea.com/us/en/p/poaeng-armchair-birch-veneer-knisa-light-beige-s49388439/",
                "download_images": True,
                "custom_output_dir": "my_images/poaeng"
            }
        }

class ImageInfo(BaseModel):
    """Image information model"""
    id: str = Field(..., description="Unique identifier for the image")
    url: str = Field(..., description="URL of the image")
    alt: str = Field(..., description="Alt text of the image")
    type: str = Field(..., description="Type of image (main, measurement, etc.)")
    path: Optional[str] = Field(None, description="Local path where image is saved (if downloaded)")

class ExtractImageResponse(BaseModel):
    """Response model for image extraction"""
    request_id: str = Field(..., description="Unique identifier for this request")
    images: Dict[str, Dict[str, Any]] = Field(..., description="Dictionary of extracted images")
    output_dir: Optional[str] = Field(None, description="Directory where images were saved (if downloaded)")
    measurements: Optional[Dict[str, str]] = Field(None, description="Product measurements extracted from the page")
    materials: Optional[Dict[str, str]] = Field(None, description="Product materials extracted from the page")

class ErrorResponse(BaseModel):
    """Error response model"""
    detail: str

# Create API application
app = FastAPI(
    title="Image Extractor API",
    description="API for extracting high-resolution product images from web pages",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    responses={
        500: {"model": ErrorResponse}
    }
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Custom schema customizations can be added here
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Middleware for request timing and logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log requests and their timing"""
    start_time = time.time()
    
    # Process the request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log the request details
    logger.info(
        f"Request {request.method} {request.url.path} "
        f"completed in {duration:.3f}s with status {response.status_code}"
    )
    
    return response

# API Routes
@app.get("/", summary="Welcome endpoint", tags=["General"])
def read_root():
    """Welcome endpoint for the API"""
    return {"message": "Welcome to the Image Extractor API"}

@app.post(
    "/extract",
    response_model=ExtractImageResponse,
    responses={
        200: {"description": "Successfully extracted images"},
        500: {"description": "Server error", "model": ErrorResponse}
    },
    summary="Extract images from a URL",
    tags=["Extraction"]
)
async def extract_images(request: ExtractImageRequest):
    """
    Extract high-resolution images from a product URL.
    
    - **url**: URL of the product page to extract images from
    - **download_images**: Whether to download the images or just return URLs
    - **custom_output_dir**: Optional custom directory to save images to
    
    Returns information about extracted images and product measurements.
    """
    try:
        logger.info(f"Processing extraction request for URL: {request.url}")
        url = str(request.url)  # Convert from Pydantic HttpUrl to string
        
        if request.download_images:
            # Process the page and download images
            logger.info(f"Downloading images to {'custom directory' if request.custom_output_dir else 'default directory'}")
            result = process_product_page(url, request.custom_output_dir)
            return result
        else:
            # Only extract image URLs without downloading
            logger.info("Extracting image URLs without downloading")
            extraction_result = extract_images_from_url(url)
            
            # Convert the result to match our response model
            return {
                "request_id": extraction_result.request_id if hasattr(extraction_result, 'request_id') else extraction_result["requestId"],
                "images": {
                    img_id: {
                        "id": img_id,
                        "url": img_info["url"] if isinstance(img_info, dict) else img_info.url,
                        "alt": img_info["alt"] if isinstance(img_info, dict) else img_info.alt,
                        "type": img_info["type"] if isinstance(img_info, dict) else img_info.type
                    } 
                    for img_id, img_info in (extraction_result.images.items() if hasattr(extraction_result, 'images') else extraction_result["images"].items())
                },
                "measurements": (
                    extraction_result.measurements 
                    if hasattr(extraction_result, 'measurements') 
                    else extraction_result.get("measurements", {})
                ),
                "materials": (
                    extraction_result.materials 
                    if hasattr(extraction_result, 'materials') 
                    else extraction_result.get("materials", {})
                ),
            }

    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing URL: {str(e)}"
        )

@app.get("/health", summary="Health check endpoint", tags=["Monitoring"])
def health_check():
    """
    Health check endpoint for monitoring the API status.
    
    Returns a simple status message indicating the API is healthy.
    """
    return {"status": "healthy", "timestamp": time.time()}

# Run the server directly if the file is executed
if __name__ == "__main__":
    logger.info("Starting Image Extractor API server")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)