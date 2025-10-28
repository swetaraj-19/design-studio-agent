import datetime
import json

# Import the initialized GCS client from its sibling file
from auth_handler import storage_client

# Import config from the parent directory
# Import ALL GCS config from the parent config file
from ..config import (
    GCS_OUTPUT_BUCKET,
    GCS_UPLOAD_BUCKET,
    RAG_BUCKET_NAME,
    SKU_FILE_TEMPLATE,
    GUIDELINES_FILE_TEMPLATE
)

# --- In-Memory Cache (now dictionaries to hold multiple brands) ---
_sku_cache = {}
_guidelines_cache = {}



