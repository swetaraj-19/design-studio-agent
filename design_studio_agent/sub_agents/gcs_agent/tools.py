import io
import os
import base64
from fuzzywuzzy import fuzz
from dotenv import load_dotenv
from datetime import datetime, timedelta

from google.cloud import storage
from google.genai import types
from google.adk.tools import ToolContext

load_dotenv()


def search_images_in_gcs(search_query: str):
    """
    Tool to search for image files in Google Cloud Storage (GCS) bucket whose 
    filename closely match a given search query using fuzzy string matching.

    This tool iterates through all objects under the 'high_resolution_images' 
    prefix and calculates a token set ratio score (fuzzy match) against the 
    search query. It returns a sorted list of filenames that meet a matching 
    threshold.

    Args:
        search_query (str): The term or phrase used to find matching image 
                            files in the GCS bucket (e.g., "dry spray").

    Returns:
        dict: A dictionary with:
            - "status" (str): "success" or "error".

            On Success:
            - "images" (list[str]): A list of GCS object names (filepaths) 
              that matched the query, sorted by highest match score first.

            On Error:
            - "message" (str): A human-readable error description 
              (e.g., if the bucket name is missing or no files are found).
    """
    try:
        BUCKET_NAME = os.getenv("GCS_BUCKET_SKU_DATA")

        if not BUCKET_NAME:
            raise ValueError("GCS_BUCKET_SKU_DATA .env variable not set")

        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)

        blobs = bucket.list_blobs(prefix="high_resolution_images")
        matching_files = []

        for blob in blobs:
            score = fuzz.token_set_ratio(
                search_query.lower(), 
                blob.name.lower()
            )

            if score > 80:
                matching_files.append((blob.name, score))

        matching_files.sort(key=lambda x: x[1], reverse=True)

        if matching_files:
            sku_images = []

            for name, _ in matching_files:
                name = name.split("/")[-1]
                sku_images.append(name)

            return {
                "status": "success",
                "images": sku_images,
            }

        return {
            "status": "error",
            "message": "No matching files found.",
        }
    
    except Exception as error:
        return {
            "status": "error",
            "message": f"Error searching GCS: {str(error)}",
        }


async def get_image_from_gcs(image_name: str, tool_context: ToolContext):
    """
    Tool to retrieve a high-resolution image file from Google Cloud Storage 
    and saves it to the tool's artifact store for subsequent use.

    The tool assumes the image is located under the 'high_resolution_images' 
    folder within the configured GCS bucket. If the file exists, it is downloaded 
    as raw bytes and registered as a new artifact in the tool context.

    Args:
        image_name (str): The filename/object name of the image to retrieve 
                          (e.g., 'shampoo_blue_sku_456.png').
        tool_context: The execution context.

    Returns:
        dict: A structured dictionary reporting the result:
            - "status" (str): "success" or "error".

            On success:
            - "artifact_id" (str): The filename assigned to the saved 
              artifact in the tool context (e.g., 'gcs_image_shampoo_...').
            
            On error:
            - "message" (str, if error): A human-readable error description 
              (e.g., if the image is not found in the bucket).
    """
    try:
        BUCKET_NAME = os.getenv("GCS_BUCKET_SKU_DATA")

        if not BUCKET_NAME:
            raise ValueError("GCS_BUCKET_SKU_DATA .env variable not set")

        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)

        blob = bucket.blob(f"high_resolution_images/{image_name}")

        if blob.exists():
            image_bytes = blob.download_as_bytes()

            img_artifact = types.Part.from_bytes(
                data=base64.b64encode(image_bytes).decode("utf-8"),
                mime_type="image/png",
            )

            filename = f"gcs_image_{image_name}"

            await tool_context.save_artifact(
                filename=filename, 
                artifact=img_artifact
            )

            return {
                "status": "success",
                "artifact_id": filename,
            }

        return {
            "status": "error",
            "message": f"Image {image_name} not found in GCS bucket."
        }

    except Exception as error:
        return {
            "status": "error",
            "message": f"Error fetching image from GCS: {str(error)}",
        }


async def save_image_to_gcs(
    image_artifact_id: str,
    tool_context: ToolContext,
):
    """
    Tool to save a specified image artifact from the tool context to Google 
    Cloud Storage (GCS) and generates a time-limited signed URL for external 
    access.

    This tool is used to publish final image outputs from the agent to a GCS 
    bucket, providing a secure, temporary link for display or use outside the 
    agent.

    Args:
        image_artifact_id (str): The unique ID or filename of the image artifact
                                 to be retrieved from the tool context.
        tool_context: The execution context, providing asynchronous methods for
                      loading input artifacts.

    Returns:
        dict: A structured dictionary reporting the execution result:
            - "status" (str): "success" or "error".
            
            On Success:
            - "signed_url" (str): A temporary URL valid for 120 mins.
            - "filename" (str): The name of the file as saved in GCS 
                                               (e.g., '20251208_0900001234.png').
            
            On Error:
            - "message" (str): A human-readable error description.
    """
    try:
        OUTPUT_BUCKET = os.getenv("GCS_BUCKET_AGENT_OUTPUTS")

        if not OUTPUT_BUCKET:
            raise ValueError("GCS_BUCKET_AGENT_OUTPUTS not found in .env file")
        
        image_artifact = await tool_context.load_artifact(filename=image_artifact_id)

        if image_artifact and image_artifact.inline_data:
            image_mime = image_artifact.inline_data.mime_type
            image_bytes = image_artifact.inline_data.data
        
        else:
            return {
                "status": "error",
                "message": f"Artifact {image_artifact_id} not found.",
            }

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S%f")
        
        try:
            extension = image_mime.split("/")[-1].lower()

            if extension not in ["png", "jpeg", "jpg"]:
                extension = "png"
        
        except:
            extension = "png"
        
        filename = f"{timestamp}.{extension}"

        client = storage.Client()
        bucket = client.bucket(OUTPUT_BUCKET)

        blob = bucket.blob(filename)
        blob.upload_from_file(io.BytesIO(image_bytes), content_type=image_mime)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=120),
            method="GET"
        )

        return {
            "status": "success",
            "signed_url": signed_url,
            "filename": filename,
        }

    except Exception as error:
        return {
            "status": "error",
            "message": f"Error saving image to GCS: {str(error)}",
        }
