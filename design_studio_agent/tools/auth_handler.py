# import json
# import logging
# from typing import Any, Dict, Optional

# from google.adk.tools import ToolContext
# from google.oauth2.credentials import Credentials
# from google.auth.transport.requests import Request
# from .. import config

# conf = config.Config()

# # Key to store creds in the cache (ToolContext)
# CREDS_CACHE_KEY = conf.CREDS_CACHE_KEY
# # Replace with your AUTH_SCOPE
# SCOPES = [conf.AUTH_SCOPE]
# # Replace with your AUTH_ID
# MY_AUTH_ID = conf.AUTH_ID

# logger = logging.getLogger(__name__)

# def auth_handler(tool, args: Dict[str, Any], tool_context: ToolContext) -> Optional[Dict]:
#     """
#     Handles authentication for the tool using credentials from AgentSpace.
#     Args:
#         tool: The tool being called.
#         args: Arguments for the tool.
#         tool_context: The ToolContext object.
#     Returns:
#         None if credentials are valid, a dict with "pending" and "message"
#         if authorization is needed.
#     """
#     creds = _get_agentspace_credentials(tool_context, MY_AUTH_ID)

#     if not creds:
#         tool_context.state["ui:status_update"] = "Authorization required, please authorize the agent."
#         return {"pending": True, "message": "Awaiting user authorization."}

#     tool_context.state["ui:status_update"] = "Authorizing the agent."
#     return None  # Continue execution


# def _get_agentspace_credentials(tool_context: ToolContext, auth_id: str) -> Optional[Credentials]:
#     """
#     Retrieves and refreshes OAuth credentials from the AgentSpace context.
#     Args:
#         tool_context: The ToolContext object.
#         auth_id: The ID of the authorization resource in AgentSpace.
#     Returns:
#         A Credentials object if available, None otherwise.
#     """
#     if not auth_id:
#         logger.error("Error: auth_id is not provided.")
#         return None

#     token_key = f"temp:{auth_id}"
#     logger.info(f"Retrieving token from key: {token_key}")

#     cached_token_info = tool_context.state.get(CREDS_CACHE_KEY)
#     if cached_token_info:
#         try:
#             logger.info("Using cached credentials")
#             creds = Credentials.from_authorized_user_info(cached_token_info, SCOPES)
#         except Exception as e:
#             logger.error(f"Error loading cached credentials: {e}")
#             creds = None

#         if creds and creds.expired and creds.refresh_token:
#             logger.info("Refreshing expired credentials")
#             try:
#                 creds.refresh(Request())
#                 tool_context.state[CREDS_CACHE_KEY] = json.loads(
#                     creds.to_json()
#                 )
#                 logger.info("Credentials refreshed and saved to cache")
#                 return creds
#             except Exception as e:
#                 logger.error(f"Error refreshing credentials: {e}")
#                 return None
#         elif creds and creds.valid:
#             logger.info("Using valid cached credentials")
#             return creds

#     access_token = tool_context.state.get(token_key)
#     if access_token:
#         logger.info("Using token from Agentspace context")
#         try:
#             creds = Credentials(token=access_token, scopes=SCOPES)
#             tool_context.state[CREDS_CACHE_KEY] = json.loads(creds.to_json())
#             logger.info("Credentials saved to cache")
#             return creds
#         except Exception as e:
#             logger.error(f"Error creating credentials from access token: {e}")
#             return None

#     logger.warning("No credentials found")
#     return None
