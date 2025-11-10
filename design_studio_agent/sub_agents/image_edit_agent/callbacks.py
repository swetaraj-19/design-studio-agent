import hashlib
from typing import List

from google.genai.types import Part
from google.adk.models import LlmResponse, LlmRequest
from google.adk.agents.callback_context import CallbackContext


async def _process_user_uploaded_artifact(
    part: Part, 
    callback_context: CallbackContext
) -> List[Part]:
    filename = part.inline_data.display_name or "uploaded_image"

    hash_input = filename.encode("utf-8") + part.inline_data.data
    content_hash = hashlib.sha256(hash_input).hexdigest()[:16]

    mime_type = part.inline_data.mime_type
    extension = mime_type.split("/")[-1]

    artifact_id = f"input_image_{content_hash}.{extension}"

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

async def _process_generated_artifact(
    part: Part, callback_context: CallbackContext
) -> List[Part]:
    artifact_id = part.function_response.response.get("tool_response_artifact_id")

    if not artifact_id:
        return [part]

    artifact = await callback_context.load_artifact(filename=artifact_id)

    caption = f"""
    [Tool Response Artifact] 
    Below is the content of artifact ID : {artifact_id}
    """

    return [part, Part(text=caption), artifact]

async def before_image_edit_model_callback(
    callback_context: CallbackContext, 
    llm_request: LlmRequest
) -> LlmResponse | None:
    for content in llm_request.contents:
        if not content.parts:
            continue

        request_parts = []

        for idx, part in enumerate(content.parts):
            if part.inline_data:
                processed_parts = await _process_user_uploaded_artifact(
                    part, 
                    callback_context
                )

            elif part.function_response:
                if part.function_response.name in [
                    "change_background_tool",
                ]:
                    processed_parts = await _process_generated_artifact(
                        part, 
                        callback_context
                    )

                else:
                    processed_parts = [part]

            else:
                processed_parts = [part]

            request_parts.extend(processed_parts)

        content.parts = request_parts
