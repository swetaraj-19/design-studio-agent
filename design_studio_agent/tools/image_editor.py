# import adk
# from typing import List
# from vertexai.preview.vision_models import Image

# # Use .. to import from the parent directory
# from .. import config
# # Import the initialized model from your auth handler
# from .auth_handler import imagen_model
# # Import the GCS upload helper
# from .utils import upload_image_to_gcs


# @adk.tool
# def edit_image(
#     prompt: str, 
#     input_image_gcs_uri: str, 
#     number_of_images: int = 2
# ) -> List[str]:
#     """
#     Edits an existing image based on a prompt using the {config.IMAGE_MODEL} model.
#     Use this to change backgrounds, adjust lighting, or modify parts of the image.
    
#     Args:
#         prompt: The prompt describing the *change* to make.
#         input_image_gcs_uri: The GCS URI of the image to edit.
#         number_of_images: The number of edited options to generate (max 4).
#     """
#     print(f"Editing image {input_image_gcs_uri} with model {config.IMAGE_MODEL}...")
#     try:
#         # Load the base image from GCS
#         input_image = Image.load_from_file(input_image_gcs_uri)
        
#         number_of_images = max(1, min(number_of_images, 4))

#         # Use the pre-loaded model directly
#         response = imagen_model.edit_image(
#             prompt=prompt,
#             image=input_image,
#             number_of_images=number_of_images,
#         )
        
#         image_uris = []
#         for img in response.images:
#             full_prompt = f"EDIT: {prompt} | ORIGINAL: {input_image_gcs_uri}"
#             # Use the helper to upload
#             gcs_uri = upload_image_to_gcs(img._image_bytes, full_prompt)
#             image_uris.append(gcs_uri)
            
#         return image_uris

#     except Exception as e:
#         print(f"Error during image editing: {e}")
#         return [f"Error during image editing: {e}"]