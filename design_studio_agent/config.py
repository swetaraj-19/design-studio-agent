import os
from dotenv import load_dotenv

load_dotenv()


ROOT_AGENT_MODEL: str = os.getenv("ROOT_AGENT_MODEL")

ROOT_AGENT_MAX_TOKENS: int = 4096
ROOT_AGENT_TEMPERATURE: float = 0.3
