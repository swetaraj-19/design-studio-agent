import io
import os
import re
import base64
import logging
import warnings
import unicodedata
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional

import google.auth
from google.cloud import storage
from google.auth import compute_engine
from google.auth import impersonated_credentials  # <--- NEW IMPORT
from google.adk.tools import ToolContext
from google.auth.transport import requests

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


def _sanitize_filename(name):
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[^\w\s-]', '', name).strip()
    name = re.sub(r'[-\s]+', '_', name)
    return str(name)


def decode_b64_str(b64_str: str) -> bytes:
    """
    Tool to decode a base64 encoded string, optionally handling data URI format.
    """
    if isinstance(b64_str, str) and b64_str.startswith("data:"):
        parts = b64_str.split(",", 1)
        if len(parts) == 2:
            b64_str = parts[1] # Fix: assign to b64_str, don't just create b64_data

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
    custom_name: Optional[str]
):
    """
    Tool to save an image artifact to Google Cloud Storage (GCS) and generate a 
    temporary Signed URL for viewing.

    This tool fetches a generated image from the session artifacts, sanitizes 
    the provided filename, and uploads it to a secure GCS bucket. It returns a 
    Signed URL that allows the user to view the image without public access.

    Args:
        image_artifact_id (str): The unique ID of the image artifact to be saved.
        tool_context (ToolContext): Context of the tool execution.
        custom_name (Optional[str]): An optional user-provided name for the file without the extension (if any)
            * If no name is provided by the user, pass `use_default`.

    Returns:
        dict: A dictionary containing the operation result:
            - 'status': "success" if the URL was signed, "partial_success" if 
              uploaded but signing failed, or "error".
            - 'signed_url': A time-limited (30 min) URL for the image, or a 
              'gs://' path if signing failed.
            - 'filename': The final name of the file saved in GCS.
            - 'note': Contextual information regarding the URL status.
            - 'message': (Optional) Detailed error message if the status is "error".
    """
    logger.info("Tool 'save_image_to_gcs' called for artifact ID: '%s'", image_artifact_id)

    try:
        OUTPUT_BUCKET = os.getenv("GCS_BUCKET_AGENT_OUTPUTS")
        SIGNER_EMAIL = os.getenv("GCS_SIGNER_SERVICE_ACCOUNT")

        if not OUTPUT_BUCKET:
            raise ValueError("GCS_BUCKET_AGENT_OUTPUTS not found in .env file")
        
        # 1. Load Artifact
        logger.info("Attempting to load artifact: %s", image_artifact_id)
        image_artifact = await tool_context.load_artifact(filename=image_artifact_id)

        if image_artifact and image_artifact.inline_data:
            image_mime = image_artifact.inline_data.mime_type
            image_bytes = image_artifact.inline_data.data
        else:
            return {"status": "error", "message": f"Artifact {image_artifact_id} not found."}

        # 2. Determine Extension
        extension = "png"
        if "/" in image_mime:
            ext_candidate = image_mime.split("/")[-1].lower()
            if ext_candidate in ["jpg", "jpeg", "png"]:
                extension = ext_candidate
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S%f")

        if custom_name and custom_name.lower() != 'use_default':
            filename = f"{_sanitize_filename(custom_name)}.{extension}"
        else:
            filename = f"{timestamp}.{extension}"
    
        # 3. Upload File
        client = storage.Client()
        bucket = client.bucket(OUTPUT_BUCKET)
        blob = bucket.blob(filename)
        
        blob.upload_from_file(io.BytesIO(image_bytes), content_type=image_mime)
        logger.info("File uploaded to gs://%s/%s", OUTPUT_BUCKET, filename)

        # 4. Generate Signed URL (Robust Method)
        signed_url = "Unavailable"
        is_url_signed = False
        error_msg = ""

        try:
            # Detect default credentials
            source_credentials, project_id = google.auth.default()
            
            # If we explicitly set a signer email in ENV, use it. 
            # Otherwise fall back to the detected service account email.
            target_principal = SIGNER_EMAIL or source_credentials.service_account_email

            if not target_principal:
                 # Local testing often has User Credentials which have no service_account_email
                 # In that case, we can't sign unless SIGNER_EMAIL is set manually
                 logger.warning("No Service Account email detected for signing.")
            
            # Create Impersonated Credentials (The Key Fix)
            # This asks GCP: "Please sign this using the target_principal's authority"
            impersonated_signer = impersonated_credentials.Credentials(
                source_credentials=source_credentials,
                target_principal=target_principal,
                target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                lifetime=3600
            )

            # Refresh to get the token
            auth_request = requests.Request()
            impersonated_signer.refresh(auth_request)

            # Generate the URL
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=30),
                service_account_email=target_principal,
                access_token=impersonated_signer.token, # Pass the impersonated token
                method="GET",
            )
            is_url_signed = True
            logger.info("Successfully generated Signed URL.")

        except Exception as e:
            is_url_signed = False
            error_msg = str(e)
            logger.error("Failed to generate signed URL: %s", e)
            
            # FALLBACK: If signing fails, return the gs:// URI. 
            # Internal tools can often use this directly.
            signed_url = f"gs://{OUTPUT_BUCKET}/{filename}"

        return {
            "status": "success" if is_url_signed else "partial_success",
            "signed_url": signed_url,
            "filename": filename,
            "note": "If signed_url is a gs:// path, ensure your viewer has GCS permissions." if not is_url_signed else ""
        }

    except Exception as error:
        logger.error("Critical error in 'save_image_to_gcs': %s", error, exc_info=True)
        return {
            "status": "error",
            "message": f"Error saving image: {str(error)}",
        }
