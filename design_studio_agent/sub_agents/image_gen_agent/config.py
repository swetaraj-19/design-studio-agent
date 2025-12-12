import os
from dotenv import load_dotenv

load_dotenv()


IMAGE_GEN_AGENT_MODEL: str = os.getenv("IMAGE_GEN_AGENT_MODEL")

IMAGE_GEN_AGENT_MAX_TOKENS: int = 4096
IMAGE_GEN_AGENT_TEMPERATURE: float = 0.3

IMAGE_GENERATION_TOOL_MODEL: str =  os.getenv("IMAGE_GENERATION_TOOL_MODEL")
