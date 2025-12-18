import io
import os
import base64
import logging
import warnings
from dotenv import load_dotenv
from datetime import datetime, timedelta

import google.auth
from google.cloud import storage
from google.auth import compute_engine
from google.adk.tools import ToolContext
from google.auth.transport import requests

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


def decode_b64_str(b64_str: str) -> bytes:
    """
    Tool to decode a base64 encoded string, optionally handling data URI format.

    This tool first checks if the input str is a data URI (starts with "data:").
    If URI, it extracts the base64 data portion. It then ensures the string is
    correctly padded before attempting to decode it into a bytes object.

    Args:
        b64_str (str): The base64 encoded string.

    Returns:
        (bytes): The decoded content as a bytes object.

    Raises:
        Exception: If the base64 decoding fails (eg. due to invalid characters).
    """
    if isinstance(b64_str, str) and b64_str.startswith("data:"):
        parts = b64_str.split(",", 1)

        if len(parts) == 2:
            b64_data = parts[1]

    b64_str = b64_str.strip()
    padding = len(b64_str) % 4

    if padding:
        b64_str += "=" * (4 - padding)

    try:
        return base64.b64decode(b64_str)
    
    except Exception as error:
        raise


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

        try:
            blob.upload_from_file(io.BytesIO(image_bytes), content_type=image_mime)
            logger.debug("File successfully uploaded to GCS.")

        except Exception as error:
            logger.error(
                "An error occurred when uploading file to GCS: %s", 
                error, 
                exc_info=True
            )

            return {
                "status": "error",
                "message": f"Error uploading file to GCS: {str(error)}",
            }

        try:
            auth_request = requests.Request()
            storage_client = storage.Client()

            data_bucket = storage_client.lookup_bucket(os.getenv("GCS_BUCKET_AGENT_OUTPUTS"))
            signed_blob_path = data_bucket.blob(filename)

            expires_at_ms = datetime.now() + timedelta(minutes=30)

            signing_credentials = compute_engine.IDTokenCredentials(
                auth_request, 
                "", 
                service_account_email=os.getenv("GCS_SIGNER_SERVICE_ACCOUNT")
            )

            signed_url = signed_blob_path.generate_signed_url(
                expires_at_ms, 
                credentials=signing_credentials, 
                version="v4"
            )

            is_url_signed = True
            logger.info("Generated signed URL for file, valid for 120 minutes.")

        
        except Exception as error:
            is_url_signed = False
            is_url_signed_error = str(error)

            logger.error(
                "An error occurred when generating signed URL: %s", 
                error, 
                exc_info=True
            )

        return {
            "status": "success" if is_url_signed else "partial_success. (Image saved. Unable to generate signed URL.)",
            "signed_url": signed_url if is_url_signed else f"Unavailable. Error generating signed url: {is_url_signed_error}",
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

