# This file initializes and provides the shared Vertex AI and GCS clients for all tools in this sub-agent.

import vertexai
from google.cloud import storage
from vertexai.preview.vision_models import ImageGenerationModel

from .. import config

# Initialize clients once when this module is imported
try: 
    print(f"Auth Handler: Initializing clients for {config.GCP_PROJECT_ID}...")
    vertexai.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
    storage_client = storage.Client(project=config.GCP_PROJECT_ID)

    # Load the specific Imagen model from config
    print(f"Auth Handler: Loading model {config.IMAGE_MODEL}...")
    imagen_model = ImageGenerationModel.from_pretrained(config.IMAGE_MODEL)
    print("Auth Handler: Vertex AI and GCS clients initialized successfully.")
    
except Exception as e:
    print(f"FATAL: Could not initialize GCP clients: {e}")
    # Re-raise the exception to stop the application if auth fails
    raise
