PROJECT_ID = "ai-poc-474306"
LOCATION = "us-central1"
MODEL = "gemini-2.5-flash"
IMAGE_GEMINI_MODEL = "gemini-2.5-pro"
IMAGE_MODEL = "imagen-4.0-fast-generate-preview-06-06"

RAG_BUCKET_NAME   = "cust-grounding-data" 
GCS_OUTPUT_BUCKET = "cust-agent-outputs"  # GCS bucket for generated images
GCS_UPLOAD_BUCKET = "cust-user-uploads"   # GCS bucket for user-uploaded images

GUIDELINES_DIR = "brand_guidelines"
SKU_IMAGES_DIR = "sku_images"
HIGH_RES_IMAGES_DIR = "high_resolution_images"

# Assumes files are named like 'kenra_sku_database.json' inside a 'kenra' folder
SKU_FILE_TEMPLATE = f"{SKU_IMAGES_DIR}/{{brand_name}}/sku_database.json" 

# Assumes guidelines are in 'brand_guidelines/kenra/brand_guidelines.json'
GUIDELINES_FILE_TEMPLATE = f"{GUIDELINES_DIR}/{{brand_name}}/brand_guidelines.txt"

# ---------------------------- ROOT AGENT CONFIG ----------------------------

ROOT_AGENT_MODEL: str = "gemini-2.5-flash"
ROOT_AGENT_MAX_TOKENS: int = 4096
ROOT_AGENT_TEMPERATURE: float = 0.3
