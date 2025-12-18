import os
import logging
import vertexai
from absl import app, flags
from dotenv import load_dotenv

from google.cloud import storage
from google.api_core import exceptions as google_exceptions

# Artifacts & Telemetry
from google.adk.artifacts import GcsArtifactService
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp
from design_studio_agent.agent import root_agent

# --- CONFIGURATION ---
WHL_FILENAME = "design_studio_agent-0.1.0-py3-none-any.whl"

FLAGS = flags.FLAGS
flags.DEFINE_string("project_id", None, "GCP project ID.")
flags.DEFINE_string("location", None, "GCP location.")
flags.DEFINE_string("bucket", None, "GCP bucket name (without gs:// prefix).")
flags.DEFINE_string("resource_id", None, "ReasoningEngine resource ID.")
flags.DEFINE_string("display_name", "Design Studio Agent", "Display name.") 

flags.DEFINE_bool("create", False, "Create a new agent.")
flags.DEFINE_bool("delete", False, "Delete an existing agent.")
flags.mark_bool_flags_as_mutual_exclusive(["create", "delete"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_staging_bucket(project_id: str, location: str, bucket_name: str) -> str:
    """Checks if the staging bucket exists, creates it if not."""
    storage_client = storage.Client(project=project_id)
    try:
        bucket = storage_client.lookup_bucket(bucket_name)
        if bucket:
            logger.info("Staging bucket gs://%s already exists.", bucket_name)
        else:
            logger.info("Staging bucket gs://%s not found. Creating...", bucket_name)
            new_bucket = storage_client.create_bucket(
                bucket_name, project=project_id, location=location
            )
            logger.info("Successfully created staging bucket gs://%s.", new_bucket.name)
            new_bucket.iam_configuration.uniform_bucket_level_access_enabled = True
            new_bucket.patch()
    except google_exceptions.Forbidden as e:
        logger.error("Permission denied for bucket gs://%s: %s", bucket_name, e)
        raise
    except google_exceptions.Conflict:
        logger.warning("Bucket gs://%s likely exists/owned by another.", bucket_name)
    except Exception as e:
        logger.error("Bucket operation failed: %s", e)
        raise

    return f"gs://{bucket_name}"

def create(env_vars: dict[str, str], staging_bucket_uri: str) -> None:
    """Creates and deploys the agent."""
    
    # Check if the wheel exists in ROOT
    if not os.path.exists(WHL_FILENAME):
        logger.error("Agent wheel file not found at: %s", WHL_FILENAME)
        raise FileNotFoundError(f"Agent .whl file not found: {WHL_FILENAME}")

    logger.info("Using agent wheel file: %s", WHL_FILENAME)

    # 1. Configure App with Tracing
    adk_app = AdkApp(
        agent=root_agent,
        enable_tracing=True, 
    )

    # 2. Inject Artifact Service (Bypass Pydantic)
    logger.info(f"Injecting GcsArtifactService with bucket: {staging_bucket_uri}")
    artifact_service = GcsArtifactService(staging_bucket_uri)
    object.__setattr__(adk_app, "artifact_service", artifact_service)

    # 3. Create Remote Agent
    remote_agent = agent_engines.create(
        adk_app,
        requirements=[WHL_FILENAME],
        extra_packages=[WHL_FILENAME],
        env_vars=env_vars,
        display_name=FLAGS.display_name,
    )

    logger.info("Created remote agent: %s", remote_agent.resource_name)
    print(f"\n[✅ SUCCESS] Agent deployed to: {remote_agent.resource_name}")

def delete(resource_id: str) -> None:
    try:
        remote_agent = agent_engines.get(resource_id)
        remote_agent.delete(force=True)
        print(f"[🗑️ DELETED] Agent {resource_id} removed successfully.")
    except Exception as e:
        logger.error("Error deleting agent %s: %s", resource_id, e)

def main(argv: list[str]) -> None:
    load_dotenv()
    env_vars = {}

    project_id = FLAGS.project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = FLAGS.location or os.getenv("GOOGLE_CLOUD_LOCATION")
    
    default_bucket_name = f"{project_id}-adk-staging" if project_id else None
    bucket_name = FLAGS.bucket or os.getenv("GOOGLE_CLOUD_STORAGE_BUCKET", default_bucket_name)

    # Telemetry Settings
    env_vars["GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY"] = "true"
    env_vars["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"

    # [CRITICAL FIX] Pass ALL required model variables to the cloud.
    # Added IMAGE_EDIT_AGENT_MODEL and the background tool models.
    env_var_keys = [
        "GCS_BUCKET_SKU_DATA",
        "GCS_BUCKET_AGENT_OUTPUTS",
        "ROOT_AGENT_MODEL",
        "GCS_AGENT_MODEL",
        "IMAGE_GEN_AGENT_MODEL",
        "IMAGE_GENERATION_TOOL_MODEL",
        "IMAGE_EDIT_AGENT_MODEL",                    # [ADDED]
        "IMAGE_BACKGROUND_FAST_TOOL_MODEL",          # [ADDED]
        "IMAGE_BACKGROUND_CAPABILITY_TOOL_MODEL"     # [ADDED]
    ]

    for key in env_var_keys:
        val = os.getenv(key)
        if val: 
            env_vars[key] = val
        else:
            logger.warning(f"Variable {key} is missing from .env or environment!")

    if not all([project_id, location, bucket_name]):
        raise app.UsageError("Missing Project ID, Location, or Bucket Name.")

    if not FLAGS.create and not FLAGS.delete:
        raise app.UsageError("Specify --create or --delete.")

    staging_bucket_uri = f"gs://{bucket_name}"

    try:
        if FLAGS.create:
            setup_staging_bucket(project_id, location, bucket_name)

        vertexai.init(
            project=project_id,
            location=location,
            staging_bucket=staging_bucket_uri,
        )

        if FLAGS.create:
            create(env_vars, staging_bucket_uri)
        elif FLAGS.delete:
            delete(FLAGS.resource_id)

    except Exception as e:
        logger.exception("Deployment failed")
        print(f"\nDeployment failed: {e}")

if __name__ == "__main__":
    app.run(main)