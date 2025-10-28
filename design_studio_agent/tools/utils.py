# design_studio_agent/tools/utils.py

import datetime
import json

# Import the initialized GCS client from its sibling file
from .auth_handler import storage_client

# Import config from the parent directory
from ..config import GCS_OUTPUT_BUCKET

# --- Mock RAG Data (Replace with real RAG calls) ---
SKU_DATABASE = {
    "SKU-A": {
        "description": "a premium, 16oz cobalt blue glass bottle of 'Persil' brand liquid laundry detergent",
        "category": "laundry"
    },
    "SKU-B": {
        "description": "a 10oz white plastic tub of 'Got2b' styling gel",
        "category": "haircare"
    }
}

BRAND_GUIDELINES = {
    "default": "Image must be high-resolution. Adhere to a minimalist aesthetic.",
    "countertop": "Lighting must be soft, originating from the left. No reflections. Use only colors from the primary brand palette (neutrals, deep blue).",
    "forest": "Ensure the product lighting is adjusted to match the new background. The forest should be natural and out-of-focus. Maintain a high-quality, professional look.",
    "general_aesthetic": "Colors must be from the primary brand palette. Minimalist background."
}

def get_sku_info(sku_id: str) -> dict:
    """Mock RAG: Fetches SKU information."""
    return SKU_DATABASE.get(sku_id, {"description": "a generic product"})

def get_brand_guidelines(keywords: list[str]) -> str:
    """Mock RAG: Fetches brand guidelines based on keywords."""
    guidelines = [BRAND_GUIDELINES["default"]]
    for key in keywords:
        if key in BRAND_GUIDELINES:
            guidelines.append(BRAND_GUIDELINES[key])
    return " ".join(guidelines)

# --- GCS Helper Function ---
def upload_to_gcs(image_bytes: bytes, tool_name: str) -> str:
    """Uploads image bytes to GCS and returns a signed URL."""
    bucket = storage_client.bucket(GCS_OUTPUT_BUCKET)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    file_name = f"{tool_name}/{timestamp}-{hash(image_bytes) % 1000}.png"
    
    blob = bucket.blob(file_name)
    blob.upload_from_string(image_bytes, content_type="image/png")
    
    signed_url = blob.generate_v4_signed_url(
        version="v4",
        expiration=datetime.timedelta(hours=1),
        method="GET"
    )
    return signed_url