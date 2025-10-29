import uuid
from .. import config
# Import the initialized client from your auth handler
from .auth_handler import storage_client

# Get the pre-configured output bucket
try:
    output_bucket = storage_client.bucket(config.GCS_OUTPUT_BUCKET)
except Exception as e:
    print(f"FATAL: Could not get GCS_OUTPUT_BUCKET '{config.GCS_OUTPUT_BUCKET}': {e}")
    raise

def upload_image_to_gcs(image_bytes: bytes, prompt: str) -> str:
    """
    Helper to upload generated image bytes to the configured GCS output bucket.
    """
    # Create a unique file name
    file_name = f"{config.BRAND_KEY}_generated_{uuid.uuid4()}.png"
    blob = output_bucket.blob(file_name)
    
    # Upload the image
    blob.upload_from_string(image_bytes, content_type="image/png")
    
    # Add metadata
    blob.metadata = {"prompt": prompt, "brand": config.BRAND_NAME}
    blob.patch()
    
    gcs_uri = f"gs://{config.GCS_OUTPUT_BUCKET}/{file_name}"
    print(f"Uploaded image to: {gcs_uri}")
    return gcs_uri