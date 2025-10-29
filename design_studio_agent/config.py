import os
import sys
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- Google Cloud & Vertex AI Config ---
GOOGLE_GENAI_USE_VERTEXAI = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "1")
GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

# --- Model Configuration ---
MODEL = os.environ.get("MODEL", "gemini-1.5-flash-001")
IMAGE_GEMINI_MODEL = os.environ.get("IMAGE_GEMINI_MODEL", "gemini-1.5-pro-001")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "imagegeneration@006")

# --- Brand Configuration ---
BRAND_NAME = os.environ.get("BRAND_NAME")
SUPPORTED_BRANDS = ["kenra", "joico"]

# Helper function to get a simple key from the brand name
def get_brand_key(name: str) -> str:
    if not name:
        return None
    key = name.split()[0].lower()
    return key if key in SUPPORTED_BRANDS else None

BRAND_KEY = get_brand_key(BRAND_NAME)

# --- GCS Bucket Configuration ---
RAG_GCS_BUCKET_NAME = os.environ.get("RAG_GCS_BUCKET_NAME")
GCS_OUTPUT_BUCKET = os.environ.get("GCS_OUTPUT_BUCKET")
GCS_UPLOAD_BUCKET = os.environ.get("GCS_UPLOAD_BUCKET")

# --- GCS Directory Structure ---
GUIDELINES_DIR = os.environ.get("GUIDELINES_DIR", "brand_guidelines")
SKU_IMAGES_DIR = os.environ.get("SKU_IMAGES_DIR", "sku_images")
HIGH_RES_IMAGES_DIR = os.environ.get("HIGH_RES_IMAGES_DIR", "high_resolution_images")

# --- Dynamically Constructed GCS Paths ---
# These are the final paths the tools will use, built from the brand and dirs
GUIDELINES_FILE_PATH = f"{GUIDELINES_DIR}/brand_guidelines.txt"
SKU_FILE_PATH = f"{SKU_IMAGES_DIR}/sku_database.json"
HIGH_RES_IMAGES_PATH_PREFIX = f"{HIGH_RES_IMAGES_DIR}/"

# --- Validation ---
REQUIRED_CONFIGS = [
    "GCP_PROJECT_ID",
    "BRAND_NAME",
    "RAG_GCS_BUCKET_NAME",
    "GCS_OUTPUT_BUCKET",
    "GCS_UPLOAD_BUCKET",
]
missing_configs = [c for c in REQUIRED_CONFIGS if not globals().get(c)]
if missing_configs:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing_configs)}"
    )

# Set project for ADK
os.environ["GOOGLE_CLOUD_PROJECT"] = GCP_PROJECT_ID
print(f"--- Config Loaded for: {BRAND_NAME} ({BRAND_KEY}) ---")
print(f"Project: {GCP_PROJECT_ID}, Location: {GCP_LOCATION}")
print(f"RAG Bucket: gs://{RAG_GCS_BUCKET_NAME}")
print(f"Guidelines: gs://{RAG_GCS_BUCKET_NAME}/{GUIDELINES_FILE_PATH}")
print(f"SKU File: gs://{RAG_GCS_BUCKET_NAME}/{SKU_FILE_PATH}")
print(f"Ref Images: gs://{RAG_GCS_BUCKET_NAME}/{HIGH_RES_IMAGES_PATH_PREFIX}")
print(f"Output Bucket: gs://{GCS_OUTPUT_BUCKET}")
print(f"Upload Bucket: gs://{GCS_UPLOAD_BUCKET}")
print("--------------------------------------------------")