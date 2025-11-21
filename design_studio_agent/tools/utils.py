import io
import os
import base64
import logging
import warnings
from dotenv import load_dotenv
from datetime import datetime, timedelta

from google.cloud import storage
from google.adk.tools import ToolContext

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
