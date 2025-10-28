# This file initializes and provides the shared Vertex AI and GCS clients for all tools in this sub-agent.

import vertexai
from google.cloud import storage
from vertexai.preview.vision_models import ImageGenerationModel

from ..config import PROJECT_ID,LOCATION

# Initialize clients once when this module is imported
try: 
    client = vertexai.init(project=PROJECT_ID,location=LOCATION)
    storage_client = storage.Client(project=PROJECT_ID)

    # Load the model once
    imagen_model = ImageGenerationModel.from_pretrained("imagegeneration@006")
    print("Auth Handler: Vertex AI and GCS clients initialized.")
except Exception as e:
    print(f"FATAL: Could not initialize GCP clients: {e}")
    raise
