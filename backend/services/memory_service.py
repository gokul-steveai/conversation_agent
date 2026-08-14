import json
import uuid
from datetime import datetime, timezone
from typing import (
    Any,
    AsyncContextManager,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

from core.database import get_db
from core.llm_factory import llm as default_llm
from langchain_core.language_models import BaseLanguageModel
from models import (
    AgentContextSummaryModel,
    AgentConversationalHistoryModel,
    AgentEntitiesRegistryModel,
    AgentKnowledgeBaseVectorModel,
    AgentToolboxDefinitionModel,
    AgentToolExecutionLogModel,
    AgentWorkflowPatternModel,
)
from repositories.memory_repository import MemoryRepository
from schemas import (
    CreateSessionRequest,
    SaveSessionRequest,
    SessionDetailResponse,
    SessionResponse,
)
from services.embedding_service import HuggingFaceEmbeddingService
from services.session_service import SessionService
from services.vector_store_service import VectorStoreService
from sqlalchemy.ext.asyncio import AsyncSession


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(parts)
    return str(content)


MODEL_TOKEN_LIMITS = {"llama-3.3-70b-versatile": 128000}


class MemoryService:
    def __init__(
        self,
        session_factory: Optional[
            Callable[[], AsyncContextManager[AsyncSession]]
        ] = None,
        memory_repository: Optional[MemoryRepository] = None,
    ) -> None:
        self.session_factory = session_factory or get_db
        self.memory_repository = memory_repository or MemoryRepository(
            self.session_factory
        )
        self._embedding_function = HuggingFaceEmbeddingService()

        self.knowledge_base_vs = VectorStoreService(
            session_factory=self.session_factory,
            model_cls=AgentKnowledgeBaseVectorModel,
            embedding_function=self._embedding_function,
        )
        self.workflow_vs = VectorStoreService(
            session_factory=self.session_factory,
            model_cls=AgentWorkflowPatternModel,
            embedding_function=self._embedding_function,
        )
        self.toolbox_vs = VectorStoreService(
            session_factory=self.session_factory,
            model_cls=AgentToolboxDefinitionModel,
            embedding_function=self._embedding_function,
        )
        self.entity_vs = VectorStoreService(
            session_factory=self.session_factory,
            model_cls=AgentEntitiesRegistryModel,
            embedding_function=self._embedding_function,
        )
        self.summary_vs = VectorStoreService(
            session_factory=self.session_factory,
            model_cls=AgentContextSummaryModel,
            embedding_function=self._embedding_function,
        )

    # --- Session Operations ---
    @classmethod
    async def create_session(
        cls, request: CreateSessionRequest
    ) -> SessionDetailResponse:
        return await SessionService.create_session(request)

    @classmethod
    async def save_session(
        cls,
        request: SaveSessionRequest,
    ) -> None:
        await SessionService.save_session(request)

    @classmethod
    async def load_session(
        cls, session_id: str, user_id: str
    ) -> Optional[SessionDetailResponse]:
        return await SessionService.load_session(session_id, user_id)

    @classmethod
    async def list_sessions(cls, user_id: str) -> List[SessionResponse]:
        return await SessionService.list_sessions(user_id)

    @classmethod
    async def delete_session(cls, session_id: str, user_id: str) -> None:
        await SessionService.delete_session(session_id, user_id)

    # --- Memory Operations ---
    async def write_conversational_memory(
        self, content: str, role: str, thread_id: str
    ) -> str:
        record_id = str(uuid.uuid4())
        entry = AgentConversationalHistoryModel(
            id=record_id,
            thread_id=thread_id,
            role=role,
            content=content,
            metadata_json="{}",
            timestamp=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        return await self.memory_repository.save_conversational_history(entry)

    async def read_conversational_memory(self, thread_id: str, limit: int = 10) -> str:
        entries = await self.memory_repository.get_unsummarized_messages(thread_id)
        messages = [f"[{e.role}] {e.content}" for e in entries[:limit]]
        messages_formatted = "\n".join(messages) or "(No unsummarized messages found.)"
        return f"## Conversation Memory\n{messages_formatted}"

    async def mark_as_summarized(self, thread_id: str, summary_id: str) -> None:
        await self.memory_repository.mark_messages_summarized(thread_id, summary_id)

    async def write_tool_log(
        self,
        thread_id: str,
        tool_name: str,
        tool_args: Any,
        result: str,
        status: str = "success",
        tool_call_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        log_id = str(uuid.uuid4())
        tool_args_str = (
            json.dumps(tool_args)
            if isinstance(tool_args, (dict, list))
            else tool_args or ""
        )
        result_str = result or ""
        preview = result_str[:2000]
        metadata_str = json.dumps(metadata or {})

        entry = AgentToolExecutionLogModel(
            id=log_id,
            thread_id=thread_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_args=tool_args_str,
            result=result_str,
            result_preview=preview,
            status=status,
            error_message=error_message,
            metadata_json=metadata_str,
            timestamp=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        return await self.memory_repository.save_tool_execution_log(entry)

    async def read_tool_logs(
        self, thread_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        rows = await self.memory_repository.get_tool_execution_logs(
            thread_id, limit=limit
        )
        logs: List[Dict[str, Any]] = []
        for e in rows:
            ts_str = (
                e.timestamp.isoformat()
                if hasattr(e.timestamp, "isoformat")
                else (str(e.timestamp) if e.timestamp else None)
            )
            logs.append(
                {
                    "id": e.id,
                    "tool_call_id": e.tool_call_id,
                    "tool_name": e.tool_name,
                    "tool_args": e.tool_args,
                    "result_preview": e.result_preview,
                    "status": e.status,
                    "error_message": e.error_message,
                    "metadata": e.metadata_json,
                    "timestamp": ts_str,
                }
            )
        return logs

    async def write_knowledge_base(
        self,
        text_input: Union[str, List[str]],
        metadata: Union[Dict[str, Any], List[Dict[str, Any]]],
    ) -> List[str]:
        texts = text_input if isinstance(text_input, list) else [text_input]
        metadatas = metadata if isinstance(metadata, list) else [metadata or {}]
        return await self.knowledge_base_vs.add_texts(texts, metadatas)

    async def read_knowledge_base(self, query: str, k: int = 3) -> str:
        results = await self.knowledge_base_vs.similarity_search(query, k=k)
        content = (
            "\n".join([doc.page_content for doc in results])
            or "(No relevant passages found.)"
        )
        return f"## Knowledge Base Memory\n{content}"

    async def write_workflow(
        self, query: str, steps: List[str], final_answer: str, success: bool = True
    ) -> List[str]:
        steps_text = "\n".join([f"Step {i + 1}: {s}" for i, s in enumerate(steps)])
        content = f"Query: {query}\nSteps:\n{steps_text}\nAnswer: {final_answer[:200]}"
        meta: Dict[str, Any] = {
            "query": query,
            "success": success,
            "num_steps": len(steps),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return await self.workflow_vs.add_texts([content], [meta])

    async def read_workflow(self, query: str, k: int = 3) -> str:
        results = await self.workflow_vs.similarity_search(
            query, k=k, filter={"num_steps": {"$gt": 0}}
        )
        content = (
            "\n---\n".join([doc.page_content for doc in results])
            or "(No relevant workflows found.)"
        )
        return f"## Workflow Memory\n{content}"

    async def write_toolbox(self, text_val: str, metadata: Dict[str, Any]) -> List[str]:
        return await self.toolbox_vs.add_texts([text_val], [metadata])

    async def read_toolbox(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        results = await self.toolbox_vs.similarity_search(query, k=k)
        tools: List[Dict[str, Any]] = []
        seen = set()
        for doc in results:
            meta = doc.metadata
            name = str(meta.get("name", "tool"))
            if name in seen:
                continue
            seen.add(name)
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": str(meta.get("description", "")),
                        "parameters": meta.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    },
                }
            )
        return tools

    async def extract_entities(
        self, text_input: str, llm_instance: Optional[BaseLanguageModel] = None
    ) -> List[Dict[str, str]]:
        if not text_input or len(text_input.strip()) < 5:
            return []
        active_llm = llm_instance or default_llm
        prompt = f'Extract entities from text: "{text_input[:500]}". Return JSON list: [{{"name": "X", "type": "PERSON|PLACE|SYSTEM", "description": "brief"}}]'
        try:
            res = await active_llm.ainvoke(prompt)
            raw_content = res.content if hasattr(res, "content") else res
            content = _extract_text_content(raw_content)
            start, end = content.find("["), content.rfind("]")
            if start != -1 and end != -1:
                return json.loads(content[start : end + 1])
        except Exception:
            pass
        return []

    async def write_entity(
        self,
        name: str = "",
        entity_type: str = "",
        description: str = "",
        llm_instance: Optional[BaseLanguageModel] = None,
        text_input: Optional[str] = None,
    ) -> List[str]:
        if text_input:
            entities = await self.extract_entities(text_input, llm_instance)
            ids: List[str] = []
            for e in entities:
                res_id = await self.entity_vs.add_texts(
                    [f"{e['name']} ({e['type']}): {e['description']}"],
                    [
                        {
                            "name": e["name"],
                            "type": e.get("type", "UNKNOWN"),
                            "description": e.get("description", ""),
                        }
                    ],
                )
                ids.extend(res_id)
            return ids
        return await self.entity_vs.add_texts(
            [f"{name} ({entity_type}): {description}"],
            [{"name": name, "type": entity_type, "description": description}],
        )

    async def read_entity(self, query: str, k: int = 5) -> str:
        results = await self.entity_vs.similarity_search(query, k=k)
        entities = [
            f"• {doc.metadata.get('name', '?')}: {doc.metadata.get('description', '')}"
            for doc in results
        ]
        formatted = "\n".join(entities) or "(No entities found.)"
        return f"## Entity Memory\n{formatted}"

    async def write_summary(
        self,
        summary_id: str,
        full_content: str,
        summary: str,
        description: str,
        thread_id: Optional[str] = None,
    ) -> str:
        meta: Dict[str, Any] = {
            "id": summary_id,
            "full_content": full_content,
            "summary": summary,
            "description": description,
        }
        if thread_id:
            meta["thread_id"] = thread_id
        await self.summary_vs.add_texts([f"{summary_id}: {description}"], [meta])
        return summary_id

    async def read_summary_memory(
        self, summary_id: str, thread_id: Optional[str] = None
    ) -> str:
        filters: Dict[str, Any] = {"id": summary_id}
        if thread_id:
            filters["thread_id"] = thread_id
        results = await self.summary_vs.similarity_search(
            summary_id, k=5, filter=filters
        )
        if not results:
            return f"Summary {summary_id} not found."
        return str(results[0].metadata.get("summary", "No summary content."))

    async def read_conversations_by_summary_id(self, summary_id: str) -> str:
        rows = await self.memory_repository.get_messages_by_summary_id(summary_id)
        if not rows:
            return f"No conversations found for summary_id: {summary_id}"

        lines = [f"## Expanded Conversations for Summary ID: {summary_id}"]
        for e in rows:
            ts_str = (
                e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(e.timestamp, "strftime")
                else (str(e.timestamp) if e.timestamp else "Unknown")
            )
            lines.append(f"[{ts_str}] [{e.role.upper()}]\n{e.content}\n")
        return "\n".join(lines)


# Context monitoring helper functions
def calculate_context_usage(
    context: str, model: str = "llama-3.3-70b-versatile"
) -> Dict[str, Any]:
    tokens = len(context) // 4
    max_tokens = MODEL_TOKEN_LIMITS.get(model, 128000)
    percent = round((tokens / max_tokens) * 100, 1)
    return {"tokens": tokens, "max": max_tokens, "percent": percent}


def monitor_context_window(
    context: str, model: str = "llama-3.3-70b-versatile"
) -> Dict[str, Any]:
    res = calculate_context_usage(context, model)
    percent = float(res["percent"])
    res["status"] = (
        "ok" if percent < 50 else ("warning" if percent < 80 else "critical")
    )
    return res


async def summarise_context_window(
    content: str,
    memory_service: MemoryService,
    llm_instance: Optional[BaseLanguageModel] = None,
    thread_id: Optional[str] = None,
) -> Dict[str, str]:
    cleaned = (content or "").strip()
    if not cleaned:
        return {"status": "nothing_to_summarize"}

    active_llm = llm_instance or default_llm
    prompt = f"Summarize key decisions, technical details, and actions from this conversation:\n{cleaned[:6000]}"
    res = await active_llm.ainvoke(prompt)
    raw_content = res.content if hasattr(res, "content") else res
    summary_text = _extract_text_content(raw_content)

    summary_id = str(uuid.uuid4())[:8]
    desc = f"Context summary for thread {thread_id or 'general'}"
    await memory_service.write_summary(
        summary_id, cleaned, summary_text, desc, thread_id=thread_id
    )
    return {"id": summary_id, "description": desc, "summary": summary_text}


async def summarize_conversation(
    thread_id: str,
    memory_service: MemoryService,
    llm_instance: Optional[BaseLanguageModel] = None,
) -> Dict[str, str]:
    rows = await memory_service.memory_repository.get_unsummarized_messages(thread_id)
    if not rows:
        return {"status": "nothing_to_summarize"}

    transcript = "\n".join([r.content for r in rows])
    result = await summarise_context_window(
        transcript, memory_service, llm_instance, thread_id=thread_id
    )
    if result.get("status") != "nothing_to_summarize":
        await memory_service.mark_as_summarized(thread_id, result["id"])
    return result
