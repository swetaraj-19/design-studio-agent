from google.genai import types
from google.adk.agents import Agent

from .callbacks import before_image_edit_model_callback
from .config import (
    IMAGE_EDIT_AGENT_MODEL,
    IMAGE_EDIT_AGENT_TEMPERATURE,
    IMAGE_EDIT_AGENT_MAX_TOKENS
)
from .prompts import IMAGE_EDIT_AGENT_DESCRIPTION, IMAGE_EDIT_AGENT_INSTRUCTION
from .tools import edit_image_tool

image_editing_agent = Agent(
    model=IMAGE_EDIT_AGENT_MODEL,
    name='image_editing_agent',
    description=IMAGE_EDIT_AGENT_DESCRIPTION,
    instruction=IMAGE_EDIT_AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        temperature=IMAGE_EDIT_AGENT_TEMPERATURE,
        max_output_tokens=IMAGE_EDIT_AGENT_MAX_TOKENS,
    ),
    include_contents="default",
    tools=[
        edit_image_tool
    ],
    before_model_callback=before_image_edit_model_callback
)