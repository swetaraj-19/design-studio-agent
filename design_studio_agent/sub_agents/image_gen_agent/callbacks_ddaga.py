import hashlib
import logging
import warnings
from typing import List
from dotenv import load_dotenv

from google.genai.types import Part
from google.adk.models import LlmResponse, LlmRequest
from google.adk.agents.callback_context import CallbackContext

load_dotenv()
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")

async def _process_user_uploaded_artifact(
    part: Part, 
    callback_context: CallbackContext
) -> List[Part]:    
    filename = part.inline_data.display_name or "uploaded_image"
    mime_type = part.inline_data.mime_type
    
    logger.debug("Processing Upload | Name: %s | Mime: %s", filename, mime_type)

    hash_input = filename.encode("utf-8") + part.inline_data.data
    content_hash = hashlib.sha256(hash_input).hexdigest()[:16]

    extension = mime_type.split("/")[-1]
    artifact_id = f"input_image_{content_hash}.{extension}"

    try:
        existing_artifacts = await callback_context.list_artifacts()
        if artifact_id not in existing_artifacts:
            logger.info("Saving new user artifact: %s", artifact_id)
            await callback_context.save_artifact(
                filename=artifact_id, 
                artifact=part
            )
        else:
            logger.debug("Artifact already exists (Skipping Save): %s", artifact_id)

    except Exception as error:
        logger.error("Failed to process user upload: %s", error, exc_info=True)

    caption = f"""
    [User Uploaded Artifact] 
    Below is the content of artifact ID : {artifact_id}
    """
    return [Part(text=caption), part]

async def _process_generated_artifact(
    part: Part, callback_context: CallbackContext
) -> List[Part]:
    
    # Check if the tool response actually contains the artifact ID
    if not part.function_response or not part.function_response.response:
         logger.warning("Callback received empty function response.")
         return [part]

    artifact_id = part.function_response.response.get("tool_response_artifact_id")

    if not artifact_id:
        logger.warning("Tool response missing 'tool_response_artifact_id'. Returning original.")
        return [part]

    logger.info("Processing generated artifact ID: %s", artifact_id)

    try:
        artifact = await callback_context.load_artifact(filename=artifact_id)
        if artifact:
            logger.debug("Successfully loaded generated artifact for context injection.")
        else:
            logger.error("Generated artifact %s could not be loaded (returned None).", artifact_id)
    
    except Exception as error:
        logger.error("Error loading generated artifact %s: %s", artifact_id, error, exc_info=True)
        # We return the part even if loading the image fails, to avoid breaking the flow
        return [part]

    caption = f"""
    [Tool Response Artifact] 
    Below is the content of artifact ID : {artifact_id}
    """
    return [part, Part(text=caption), artifact]

async def before_image_gen_model_callback(
    callback_context: CallbackContext, 
    llm_request: LlmRequest
) -> LlmResponse | None:
    logger.info(">>> START: before_image_gen_model_callback")
    
    content_count = len(llm_request.contents)
    logger.debug("Processing %d content block(s).", content_count)

    for content_idx, content in enumerate(llm_request.contents):
        if not content.parts:
            continue

        request_parts = []
        for idx, part in enumerate(content.parts):
            processed_parts = [part] # Default

            if part.inline_data:
                processed_parts = await _process_user_uploaded_artifact(part, callback_context)
            
            elif part.function_response:
                func_name = part.function_response.name
                logger.debug("Processing FunctionResponse: %s", func_name)
                
                if func_name in [
                    "generate_image_tool", 
                    "change_background_capability_tool", 
                    "change_background_fast_tool",
                ]:
                    processed_parts = await _process_generated_artifact(part, callback_context)

            request_parts.extend(processed_parts)

        content.parts = request_parts

    logger.info("<<< END: before_image_gen_model_callback")
    return None
