import os
from dotenv import load_dotenv

load_dotenv()

GCS_AGENT_MODEL: str = os.getenv("GCS_AGENT_MODEL")

GCS_AGENT_MAX_TOKENS: int = 4096
GCS_AGENT_TEMPERATURE: float = 0.3
