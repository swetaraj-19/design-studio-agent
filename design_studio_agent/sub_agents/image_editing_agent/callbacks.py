import hashlib
import logging
from typing import List

from google.genai.types import Part
from google.adk.models import LlmResponse, LlmRequest
from google.adk.agents.callback_context import CallbackContext

logger = logging.getLogger(__name__)

async def _save_and_load_image_artifact(
    part: Part,
    callback_context: CallbackContext
) -> List[Part]:
    """Saves an image Part as an artifact and returns a text caption."""
    filename = part.inline_data.display_name or "uploaded_image"

    hash_input = filename.encode("utf-8") + part.inline_data.data
    content_hash = hashlib.sha256(hash_input).hexdigest()[:16]

    mime_type = part.inline_data.mime_type
    extension = mime_type.split("/")[-1]

    artifact_id = f"img_{content_hash}.{extension}"

    if artifact_id not in await callback_context.list_artifacts():
        await callback_context.save_artifact(
            filename=artifact_id,
            artifact=part
        )

    caption = f"""
    [User Uploaded Artifact]
    Below is the content of artifact ID : {artifact_id}
    """

    return [Part(text=caption), part]

async def before_image_edit_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest
) -> LlmResponse | None:
    """
    Processes image artifacts before calling the model.
    """
    for content in llm_request.contents:
        if not content.parts:
            continue

        request_parts = []

        for idx, part in enumerate(content.parts):
            if part.inline_data:
                try:
                    processed_parts = await _save_and_load_image_artifact(
                        part,
                        callback_context
                    )
                except Exception as e:
                    logger.error(f"Failed to process artifact: {e}")
                    processed_parts = [Part(text="[Error processing image]")]
            else:
                processed_parts = [part]

            request_parts.extend(processed_parts)

        content.parts = request_parts
    
    return None 