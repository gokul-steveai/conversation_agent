from langfuse.langchain import CallbackHandler

from langfuse import get_client

langfuse = get_client()
langfuse_handler = CallbackHandler()
