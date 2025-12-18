# design_studio_agent/agent.py
import os
import sys
import logging
import warnings
from dotenv import load_dotenv

from google.genai import types
from google.adk import Agent
from google.adk.tools import load_artifacts
# [REMOVED] GcsArtifactService import is not needed here

from .callbacks import before_image_gen_model_callback
from .config import (
    IMAGE_GEN_AGENT_MODEL, 
    IMAGE_GEN_AGENT_TEMPERATURE, 
    IMAGE_GEN_AGENT_MAX_TOKENS
)
from .prompts import IMAGE_GEN_AGENT_DESCRIPTION, IMAGE_GEN_AGENT_INSTRUCTION

from .tools import generate_image_tool, generate_image_without_labels_tool
from ...tools.utils import save_image_to_gcs

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - [%(filename)s:%(lineno)d] - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")


image_gen_agent = Agent(
    model=IMAGE_GEN_AGENT_MODEL,
    name='image_gen_agent',
    description=IMAGE_GEN_AGENT_DESCRIPTION,
    instruction=IMAGE_GEN_AGENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        temperature=IMAGE_GEN_AGENT_TEMPERATURE,
        max_output_tokens=IMAGE_GEN_AGENT_MAX_TOKENS,
    ),
    include_contents="default",
    tools=[
        generate_image_tool,
        generate_image_without_labels_tool,
        save_image_to_gcs,
        load_artifacts
    ],
    before_model_callback=before_image_gen_model_callback
)

# [DELETED] The configuration block that was causing the crash is removed.
# We will handle artifact service injection in deploy.py

# Alias for deploy.py
#root_agent = image_gen_agent