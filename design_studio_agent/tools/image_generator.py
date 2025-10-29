from google.adk import agent
from typing import List

# Use .. to import from the parent directory
from .. import config 
# Import the initialized model from your auth handler
from .auth_handler import imagen_model 
# Import the GCS upload helper
from .utils import upload_image_to_gcs 

def generate_image(prompt: str, number_of_images: int = 2) -> List[str]:
    """
    Generates new images from a text prompt using the {config.IMAGE_MODEL} model.
    The prompt MUST include brand guidelines and SKU details (if any).
    
    Args:
        prompt: The detailed "meta-prompt" describing the desired image.
        number_of_images: The number of image options to generate (max 4).
    """
    print(f"Generating {number_of_images} images with model {config.IMAGE_MODEL}...")
    try:
        number_of_images = max(1, min(number_of_images, 4))
        
        # Use the pre-loaded model directly
        response = imagen_model.generate_images(
            prompt=prompt,
            number_of_images=number_of_images,
            aspect_ratio="1:1"
        )
        
        image_uris = []
        for img in response.images:
            # Use the helper to upload
            gcs_uri = upload_image_to_gcs(img._image_bytes, prompt)
            image_uris.append(gcs_uri)
            
        return image_uris
        
    except Exception as e:
        print(f"Error during image generation: {e}")
        return [f"Error during image generation: {e}"]