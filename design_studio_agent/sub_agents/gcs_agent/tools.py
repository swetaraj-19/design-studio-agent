import io
import os
import base64
import logging
import warnings
from fuzzywuzzy import fuzz
from dotenv import load_dotenv
from datetime import datetime, timedelta

from google.cloud import storage
from google.genai import types
from google.adk.tools import ToolContext

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


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
    logger.info("Tool 'search_images_in_gcs' called with query: '%s'", search_query)
    
    try:
        BUCKET_NAME = os.getenv("GCS_BUCKET_SKU_DATA")

        if not BUCKET_NAME:
            logger.error("Environment variable GCS_BUCKET_SKU_DATA not set.")
            raise ValueError("GCS_BUCKET_SKU_DATA .env variable not set")

        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)
        prefix = "high_resolution_images"

        logger.info(
            "Listing blobs in bucket '%s' with prefix '%s'...", 
            BUCKET_NAME, 
            prefix
        )

        blobs = bucket.list_blobs(prefix=prefix)
        matching_files = []

        file_count = 0

        for blob in blobs:
            file_count += 1

            score = fuzz.token_set_ratio(
                search_query.lower(), 
                blob.name.lower()
            )

            if score > 75:
                matching_files.append((blob.name, score))
                logger.debug(
                    "Found match: %s with score %d", 
                    blob.name, 
                    score
                )

        logger.info(
            "Finished fuzzy search. Processed %d files. Found %d matches.", 
            file_count, 
            len(matching_files)
        )

        matching_files.sort(key=lambda x: x[1], reverse=True)

        if matching_files:
            sku_images = []

            for name, _ in matching_files:
                name = name.split("/")[-1]
                sku_images.append(name)

            logger.info(
                "Found %d matching images in GCS bucket.", 
                len(sku_images)
            )

            return {
                "status": "success",
                "images": sku_images,
            }

        logger.info("No matching files found for query '%s' with score > 75.", search_query)

        return {
            "status": "error",
            "message": "No matching files found.",
        }
    
    except Exception as error:
        logger.error(
            "An error occurred in 'search_images_in_gcs': %s", 
            error, 
            exc_info=True
        )

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
    logger.info("Tool 'get_image_from_gcs' called for image: '%s'", image_name)

    try:
        BUCKET_NAME = os.getenv("GCS_BUCKET_SKU_DATA")

        if not BUCKET_NAME:
            logger.error("Environment variable GCS_BUCKET_SKU_DATA not set.")
            raise ValueError("GCS_BUCKET_SKU_DATA .env variable not set")

        client = storage.Client()
        bucket = client.bucket(BUCKET_NAME)

        blob_path = f"high_resolution_images/{image_name}"
        blob = bucket.blob(blob_path)

        logger.debug("Checking existence of blob: gs://%s/%s", BUCKET_NAME, blob_path)

        if blob.exists():
            logger.info("Blob found. Downloading image bytes.")
            image_bytes = blob.download_as_bytes()

            img_artifact = types.Part.from_bytes(
                data=base64.b64encode(image_bytes).decode("utf-8"),
                mime_type="image/png",
            )

            filename = f"gcs_image_{image_name}"
            logger.info("Saving artifact to tool context with filename: %s", filename)

            await tool_context.save_artifact(
                filename=filename, 
                artifact=img_artifact
            )

            logger.debug("Successfully saved artifact to tool context.")

            return {
                "status": "success",
                "artifact_id": filename,
            }

        logger.warning(
            "Image '%s' not found in GCS bucket '%s'.", 
            image_name, 
            BUCKET_NAME
        )

        return {
            "status": "error",
            "message": f"Image {image_name} not found in GCS bucket."
        }

    except Exception as error:
        logger.error(
            "An error occurred in 'get_image_from_gcs': %s", 
            error, 
            exc_info=True
        )

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
    logger.info(
        "Tool 'save_image_to_gcs' called for artifact ID: '%s'", 
        image_artifact_id
    )

    try:
        OUTPUT_BUCKET = os.getenv("GCS_BUCKET_AGENT_OUTPUTS")

        if not OUTPUT_BUCKET:
            logger.error("Environment variable GCS_BUCKET_AGENT_OUTPUTS not set.")
            raise ValueError("GCS_BUCKET_AGENT_OUTPUTS not found in .env file")
        
        logger.info("Attempting to load artifact: %s", image_artifact_id)
        image_artifact = await tool_context.load_artifact(filename=image_artifact_id)

        if image_artifact and image_artifact.inline_data:
            image_mime = image_artifact.inline_data.mime_type
            image_bytes = image_artifact.inline_data.data

            logger.debug(
                "Artifact loaded successfully. MIME type: %s, Data size: %d bytes.", 
                image_mime, 
                len(image_bytes)
            )
        
        else:
            logger.warning(
                "Artifact '%s' not found or missing inline_data.", 
                image_artifact_id
            )

            return {
                "status": "error",
                "message": f"Artifact {image_artifact_id} not found.",
            }

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S%f")
        
        try:
            extension = image_mime.split("/")[-1].lower()
            if extension not in ["png", "jpeg", "jpg"]:
                extension = "png"
                logger.debug("MIME type '%s' not supported, defaulting extension to 'png'.", image_mime)
        
        except:
            extension = "png"
            logger.warning("Failed to parse extension from MIME type '%s', defaulting to 'png'.", image_mime)
        
        filename = f"{timestamp}.{extension}"
        logger.info("Generated target filename for GCS: %s", filename)

        client = storage.Client()
        bucket = client.bucket(OUTPUT_BUCKET)

        blob = bucket.blob(filename)
        logger.info("Uploading file to GCS bucket '%s' as '%s'...", OUTPUT_BUCKET, filename)

        blob.upload_from_file(io.BytesIO(image_bytes), content_type=image_mime)
        logger.debug("File successfully uploaded.")

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=120),
            method="GET"
        )
        logger.info("Generated signed URL for file, valid for 120 minutes.")

        return {
            "status": "success",
            "signed_url": signed_url,
            "filename": filename,
        }

    except Exception as error:
        logger.error(
            "An error occurred in 'save_image_to_gcs': %s", 
            error, 
            exc_info=True
        )

        return {
            "status": "error",
            "message": f"Error saving image to GCS: {str(error)}",
        }
