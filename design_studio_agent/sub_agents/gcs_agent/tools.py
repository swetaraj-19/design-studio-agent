import io
import os
import base64
import logging
import warnings
from fuzzywuzzy import fuzz
from dotenv import load_dotenv
from datetime import datetime, timedelta

import google.auth
from google.genai import types
from google.cloud import storage
from google.auth import compute_engine
from google.adk.tools import ToolContext
from google.auth.transport import requests

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

        blobs = list(bucket.list_blobs(prefix=prefix))
        matching_files = []

        file_count = 0

        for blob in blobs:
            file_count += 1

            clean_filename = blob.name.split("/")[-1].rsplit('.', 1)[0]
            clean_filename = clean_filename.replace('_', ' ').replace('-', ' ')

            score = fuzz.partial_ratio(
                search_query.lower(), 
                clean_filename.lower()
            )

            if score > 75:
                matching_files.append((blob.name, score))

                logger.debug(
                    "Found match: %s with score %d", 
                    blob.name, 
                    score
                )
        
        if not matching_files:
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
