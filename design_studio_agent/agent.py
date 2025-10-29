import logging
import warnings
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from . import config
from .prompt import SYSTEM_PROMPT

from google.genai import types
from .tools import gcs_tools, image_generator, image_editor

warnings.filterwarnings("ignore", category=UserWarning, module=".*pydantic.*")
logger = logging.getLogger(__name__)

root_agent = Agent(
    name="design_studio_agent",
    model="gemini-1.5-pro-001",
    description="An agent for generating and editing images for Henkel brands.",
    instruction="You are an expert AI design assistant. Help users create or edit product images based on their requests. You must infer the brand (kenra or joico) from the prompt. If no brand is specified, you must ask the user to provide one.",
    generate_content_config=types.GenerateContentConfig(
        temperature=MODEL_TEMPERATURE,
        max_output_tokens=MODEL_MAX_TOKENS,
    ),
    sub_agents=[
        image_generation
    ]
)