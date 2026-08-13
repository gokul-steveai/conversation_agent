import inspect
import uuid
from typing import Any, Callable, Dict, Optional

from core.llm_factory import llm as default_llm
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel
from services.embedding_service import (
    HuggingFaceEmbeddingModel,
    OpenSourceEmbeddings,
)
from services.memory_service import (
    MemoryService,
    calculate_context_usage,
    monitor_context_window,
    summarise_context_window,
    summarize_conversation,
)
from services.vector_store_service import VectorStoreService

# Aliasing for backwards compatibility
AsyncPostgresVectorStore = VectorStoreService
MemoryManager = MemoryService


class ToolMetadata(BaseModel):
    name: str
    description: str
    signature: str
    parameters: dict
    return_type: str


class Toolbox:
    """Toolbox for registering, storing, and semantic retrieval of agent tools."""

    def __init__(
        self,
        memory_service: MemoryService,
        llm_instance: Optional[BaseLanguageModel] = None,
    ) -> None:
        self.memory_service = memory_service
        self.llm = llm_instance or default_llm
        self._tools: Dict[str, Callable] = {}

    async def register_tool(self, func: Callable) -> str:
        name = func.__name__
        doc = func.__doc__ or "No description"
        sig = str(inspect.signature(func))
        tool_id = str(uuid.uuid4())

        tool_meta: dict[str, Any] = {
            "name": name,
            "description": doc,
            "signature": sig,
            "parameters": {},
        }
        await self.memory_service.write_toolbox(f"{name} {doc} {sig}", tool_meta)
        self._tools[name] = func
        return tool_id


__all__ = [
    "OpenSourceEmbeddings",
    "HuggingFaceEmbeddingModel",
    "AsyncPostgresVectorStore",
    "MemoryManager",
    "MemoryService",
    "ToolMetadata",
    "Toolbox",
    "calculate_context_usage",
    "monitor_context_window",
    "summarise_context_window",
    "summarize_conversation",
]
