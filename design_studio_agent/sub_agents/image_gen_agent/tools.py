import os
import logging
from dotenv import load_dotenv

from google import genai
from google.adk.tools import ToolContext

from .config import IMAGE_GENERATION_TOOL_MODEL

load_dotenv()


client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION"),
)

async def generate_image_tool(
    tool_context: ToolContext,
    description: str,
    image_artifact_ids: list = [],
) -> dict[str, str]:
    """
    Tool to generate a new image based on a text description and the provided 
    reference image(s).

    This tool generates a new image based on the user's text description and 
    the reference image(s), provided in `image_artifact_ids`. It automatically 
    fetches the reference images from the artifacts using the id's provided in 
    the `image_artifact_ids`.

    Args:
        description (str): Text description describing the desired image output.
            * Be detailed and specific with describing the image.
                - e.g., "Image of a shampoo bottle on a spa counter."
        image_artifact_ids (list): List of image IDs to use as reference image.
            * For single image: provide a list with one item 
                - e.g., ["product.png"]
            * For multiple images: provide a list with multiple items 
                - e.g., ["product1.png", "product2.png"]

    Returns:
        dict: A dictionary containing the operation result:
            - 'tool_response_artifact_id': Artifact ID for the generated image
            - 'tool_input_artifact_ids': Comma-separated list of input artifact IDs
            - 'used_prompt': The full image generation prompt used
            - 'status': Success or error status
            - 'message': Additional information or error details
    """
    try:
        if not image_artifact_ids:
            return {
                "status": "error",
                "tool_response_artifact_id": "",
                "tool_input_artifact_ids": "",
                "used_prompt": description,
                "message": "No reference image provided. Please provide a reference image to generate the image.",
            }

        image_artifacts = []
        for img_id in image_artifact_ids:
            artifact = await tool_context.load_artifact(filename=img_id)

            if artifact is None:
                return {
                    "status": "error",
                    "tool_response_artifact_id": "",
                    "tool_input_artifact_ids": "",
                    "used_prompt": description,
                    "message": f"Artifact {img_id} not found",
                }

            image_artifacts.append(artifact)

        image_generation_prompt = (
            f"USER PROMPT: {description}.\n\n---\n"
            "**CRITICAL INSTRUCTION: YOU MUST PRESERVE THE REFERENCE PRODUCT.**\n"
            "1.  **DO NOT ALTER THE PRODUCT:** The reference product (bottle, jar, etc.) must be used *exactly* as-is.\n"
            "2.  **PRESERVE ALL TEXT:** All text, logos, and branding on the reference product must be preserved perfectly. Do not regenerate, misspell, or change any text.\n"
            "3.  **PRESERVE APPEARANCE:** The product's shape, color, design, and label must remain identical to the reference image.\n"
            "4.  **ONLY CHANGE THE BACKGROUND/SCENE:** Your only task is to place the *unaltered* product into the new scene described in the user prompt."
        )

        contents = image_artifacts + [image_generation_prompt]

        response = await client.aio.models.generate_content(
            model=IMAGE_GENERATION_TOOL_MODEL,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                response_modalities=["Image"],
                candidate_count=1
            ),
        )

        artifact_id = ""

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                artifact_id = f"generated_img_{tool_context.function_call_id}.png"

                await tool_context.save_artifact(
                    filename=artifact_id, 
                    artifact=part
                )

        input_ids_str = ", ".join(image_artifact_ids)
        
        return {
            "status": "success",
            "tool_response_artifact_id": artifact_id,
            "tool_input_artifact_ids": input_ids_str,
            "used_prompt": image_generation_prompt,
            "message": f"Image generated successfully using {len(image_artifacts)} input image(s)",
        }

    except Exception as e:
        input_ids_str = ", ".join(image_artifact_ids) if image_artifact_ids else ""

        return {
            "status": "error",
            "tool_response_artifact_id": "",
            "tool_input_artifact_ids": input_ids_str,
            "used_prompt": description,
            "message": f"Error generating image: {str(e)}",
        }
