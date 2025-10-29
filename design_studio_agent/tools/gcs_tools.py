from google.adk import agent
import json
from typing import List, Optional, Dict, Any

from .. import config
from .auth_handler import storage_client

def _read_gcs_file(bucket_name:str, file_path:str) -> Optional[str]:
    """ Helper function to read file from GCS. """
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)
        if not blob.exists():
            print(f"Error: File '{file_path}' not found in bucket '{bucket_name}'.")
            return f"Error: File '{file_path}' not found."
        return blob.download_as_text()
    except Exception as e:
        print(f"Error reading GCS file: {e}")
        return f"Error reading from GCS: {e}"
    

def get_sku_details(sku_names: List[str]) -> str:
    """
    Fetches product details for a list of {config.BRAND_NAME} SKU names.
    
    Args:
        sku_names: A list of product names (SKUs) to look up.
    """
    print(f"Fetching SKU details from: gs://{config.RAG_GCS_BUCKET_NAME}/{config.SKU_FILE_PATH}")

    sku_data_json = _read_gcs_file(
        config.RAG_GCS_BUCKET_NAME, 
        config.SKU_FILE_PATH
    )
    if sku_data_json.startswith("Error:"):
        return sku_data_json
    try:
        all_skus: Dict[str, Any] = json.loads(sku_data_json)
        relevant_skus = {}
        for name in sku_names:
            found = False
            for key, value in all_skus.items():
                if name.lower() in key.lower() or name.lower() in value.get("name", "").lower():
                    relevant_skus[key] = value
                    found = True
            if not found:
                relevant_skus[name] = "SKU not found."
                
        if not relevant_skus:
            return f"No information found for SKUs: {', '.join(sku_names)}"
            
        return json.dumps(relevant_skus, indent=2)
        
    except json.JSONDecodeError:
        return "Error: SKU data file is not valid JSON."
    except Exception as e:
        return f"Error processing SKU data: {e}"
    
    
def list_reference_images() -> List[str]:
    """
    Lists available high-resolution reference images for the {config.BRAND_NAME} brand.
    """
    print(f"Listing images from: gs://{config.RAG_GCS_BUCKET_NAME}/{config.HIGH_RES_IMAGES_PATH_PREFIX}")
    try:
        blobs = storage_client.list_blobs(
            config.RAG_GCS_BUCKET_NAME, 
            prefix=config.HIGH_RES_IMAGES_PATH_PREFIX
        )
        image_uris = [
            f"gs://{config.RAG_GCS_BUCKET_NAME}/{blob.name}" 
            for blob in blobs 
            if not blob.name.endswith('/')
        ]
        if not image_uris:
            return ["No reference images found."]
        return image_uris
    except Exception as e:
        print(f"Error listing reference images: {e}")
        return [f"Error listing images: {e}"]