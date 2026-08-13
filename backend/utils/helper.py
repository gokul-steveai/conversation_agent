import inspect
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type, Union

import numpy as np
from core.llm_factory import llm as default_llm
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from models import (
    AgentContextSummaryModel,
    AgentConversationalHistoryModel,
    AgentEntitiesRegistryModel,
    AgentKnowledgeBaseVectorModel,
    AgentToolboxDefinitionModel,
    AgentToolExecutionLogModel,
    AgentWorkflowPatternModel,
    BaseVectorModel,
)
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            elif hasattr(item, "text"):
                parts.append(str(getattr(item, "text")))
            else:
                parts.append(str(item))
        return " ".join(parts)
    return str(content)


class OpenSourceEmbeddings(Embeddings):
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def _hash_vector(self, text_input: str) -> List[float]:
        tokens = re.findall(r"\w+", text_input.lower())
        if not tokens:
            return [0.0] * self.dimension

        vec = np.zeros(self.dimension, dtype=np.float32)
        for i, token in enumerate(tokens):
            idx = hash(token) % self.dimension
            vec[idx] += 1.0
            if i < len(tokens) - 1:
                bigram = f"{token}_{tokens[i + 1]}"
                bigram_idx = hash(bigram) % self.dimension
                vec[bigram_idx] += 0.5

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_vector(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._hash_vector(text)


class HuggingFaceEmbeddingModel(Embeddings):
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._fallback = OpenSourceEmbeddings(dimension=384)
        self._hf_embeddings = None

        try:
            self._hf_embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        except Exception:
            try:
                self._hf_embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
            except Exception:
                pass

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self._hf_embeddings is not None:
            try:
                return self._hf_embeddings.embed_documents(texts)
            except Exception:
                pass
        return self._fallback.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        if self._hf_embeddings is not None:
            try:
                return self._hf_embeddings.embed_query(text)
            except Exception:
                pass
        return self._fallback.embed_query(text)


class AsyncPostgresVectorStore:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        model_cls: Type[BaseVectorModel],
        embedding_function: Optional[Embeddings] = None,
    ):
        self.session_factory = session_factory
        self.model_cls = model_cls
        self.embedding_function = embedding_function or HuggingFaceEmbeddingModel()

    async def add_texts(
        self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        if not texts:
            return []

        metadatas = metadatas or [{} for _ in texts]
        embeddings = self.embedding_function.embed_documents(texts)
        ids = []

        async with self.session_factory() as session:
            for text_val, meta, emb in zip(texts, metadatas, embeddings):
                doc_id = str(uuid.uuid4())
                ids.append(doc_id)
                instance = self.model_cls(
                    id=doc_id,
                    content=text_val,
                    embedding=json.dumps(emb),
                    metadata_json=json.dumps(meta),
                    created_at=datetime.now(timezone.utc),
                )
                session.add(instance)
            await session.commit()
        return ids

    async def similarity_search(
        self, query: str, k: int = 3, filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        query_emb = np.array(
            self.embedding_function.embed_query(query), dtype=np.float32
        )
        q_norm = np.linalg.norm(query_emb)

        async with self.session_factory() as session:
            stmt = select(self.model_cls)
            res = await session.execute(stmt)
            instances = res.scalars().all()

        results = []
        for inst in instances:
            try:
                meta = json.loads(inst.metadata_json) if inst.metadata_json else {}
            except Exception:
                meta = {}

            if filter:
                match = True
                for fk, fv in filter.items():
                    if isinstance(fv, dict) and "$gt" in fv:
                        if meta.get(fk, 0) <= fv["$gt"]:
                            match = False
                            break
                    elif meta.get(fk) != fv:
                        match = False
                        break
                if not match:
                    continue

            try:
                emb = np.array(json.loads(inst.embedding), dtype=np.float32)
                e_norm = np.linalg.norm(emb)
                sim = (
                    (np.dot(query_emb, emb) / (q_norm * e_norm))
                    if (q_norm * e_norm > 0)
                    else 0.0
                )
            except Exception:
                sim = 0.0

            results.append((sim, Document(page_content=inst.content, metadata=meta)))

        results.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in results[:k]]


class MemoryManager:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
        knowledge_base_vs: Optional[AsyncPostgresVectorStore] = None,
        workflow_vs: Optional[AsyncPostgresVectorStore] = None,
        toolbox_vs: Optional[AsyncPostgresVectorStore] = None,
        entity_vs: Optional[AsyncPostgresVectorStore] = None,
        summary_vs: Optional[AsyncPostgresVectorStore] = None,
    ):
        self.session_factory = session_factory
        self.knowledge_base_vs = knowledge_base_vs or AsyncPostgresVectorStore(
            session_factory, AgentKnowledgeBaseVectorModel
        )
        self.workflow_vs = workflow_vs or AsyncPostgresVectorStore(
            session_factory, AgentWorkflowPatternModel
        )
        self.toolbox_vs = toolbox_vs or AsyncPostgresVectorStore(
            session_factory, AgentToolboxDefinitionModel
        )
        self.entity_vs = entity_vs or AsyncPostgresVectorStore(
            session_factory, AgentEntitiesRegistryModel
        )
        self.summary_vs = summary_vs or AsyncPostgresVectorStore(
            session_factory, AgentContextSummaryModel
        )

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
        async with self.session_factory() as session:
            session.add(entry)
            await session.commit()
        return record_id

    async def read_conversational_memory(self, thread_id: str, limit: int = 10) -> str:
        stmt = (
            select(AgentConversationalHistoryModel)
            .where(
                AgentConversationalHistoryModel.thread_id == thread_id,
                AgentConversationalHistoryModel.summary_id.is_(None),
            )
            .order_by(AgentConversationalHistoryModel.timestamp.asc())
            .limit(limit)
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            entries = res.scalars().all()

        messages = [f"[{e.role}] {e.content}" for e in entries]
        messages_formatted = "\n".join(messages) or "(No unsummarized messages found.)"
        return f"## Conversation Memory\n{messages_formatted}"

    async def mark_as_summarized(self, thread_id: str, summary_id: str) -> None:
        stmt = (
            update(AgentConversationalHistoryModel)
            .where(
                AgentConversationalHistoryModel.thread_id == thread_id,
                AgentConversationalHistoryModel.summary_id.is_(None),
            )
            .values(summary_id=summary_id)
        )
        async with self.session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def write_tool_log(
        self,
        thread_id: str,
        tool_name: str,
        tool_args: Any,
        result: str,
        status: str = "success",
        tool_call_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        log_id = str(uuid.uuid4())
        tool_args_str = (
            json.dumps(tool_args)
            if isinstance(tool_args, (dict, list))
            else str(tool_args or "")
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
        async with self.session_factory() as session:
            session.add(entry)
            await session.commit()
        return log_id

    async def read_tool_logs(
        self, thread_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(AgentToolExecutionLogModel)
            .where(AgentToolExecutionLogModel.thread_id == thread_id)
            .order_by(AgentToolExecutionLogModel.timestamp.desc())
            .limit(limit)
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            rows = res.scalars().all()

        logs = []
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
        self, text_input: Union[str, List[str]], metadata: Union[dict, List[dict]]
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
        self, query: str, steps: list, final_answer: str, success: bool = True
    ) -> List[str]:
        steps_text = "\n".join([f"Step {i + 1}: {s}" for i, s in enumerate(steps)])
        content = f"Query: {query}\nSteps:\n{steps_text}\nAnswer: {final_answer[:200]}"
        meta = {
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

    async def write_toolbox(self, text_val: str, metadata: dict) -> List[str]:
        return await self.toolbox_vs.add_texts([text_val], [metadata])

    async def read_toolbox(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        results = await self.toolbox_vs.similarity_search(query, k=k)
        tools = []
        seen = set()
        for doc in results:
            meta = doc.metadata
            name = meta.get("name", "tool")
            if name in seen:
                continue
            seen.add(name)
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": meta.get("description", ""),
                        "parameters": meta.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    },
                }
            )
        return tools

    async def extract_entities(
        self, text_input: str, llm_instance: Any = None
    ) -> List[Dict[str, Any]]:
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
        llm_instance: Any = None,
        text_input: Optional[str] = None,
    ) -> List[str]:
        if text_input:
            entities = await self.extract_entities(text_input, llm_instance)
            ids = []
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
        meta = {
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
        filters = {"id": summary_id}
        if thread_id:
            filters["thread_id"] = thread_id
        results = await self.summary_vs.similarity_search(
            summary_id, k=5, filter=filters
        )
        if not results:
            return f"Summary {summary_id} not found."
        return results[0].metadata.get("summary", "No summary content.")

    async def read_conversations_by_summary_id(self, summary_id: str) -> str:
        stmt = (
            select(AgentConversationalHistoryModel)
            .where(AgentConversationalHistoryModel.summary_id == summary_id)
            .order_by(AgentConversationalHistoryModel.timestamp.asc())
        )
        async with self.session_factory() as session:
            res = await session.execute(stmt)
            rows = res.scalars().all()

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


class ToolMetadata(BaseModel):
    name: str
    description: str
    signature: str
    parameters: dict
    return_type: str


class Toolbox:
    """Toolbox for registering, storing, and semantic retrieval of agent tools."""

    def __init__(self, memory_manager: MemoryManager, llm_instance: Any = None):
        self.memory_manager = memory_manager
        self.llm = llm_instance or default_llm
        self._tools: Dict[str, Callable] = {}

    async def register_tool(self, func: Callable) -> str:
        name = func.__name__
        doc = func.__doc__ or "No description"
        sig = str(inspect.signature(func))
        tool_id = str(uuid.uuid4())

        tool_meta = {
            "name": name,
            "description": doc,
            "signature": sig,
            "parameters": {},
        }
        await self.memory_manager.write_toolbox(f"{name} {doc} {sig}", tool_meta)
        self._tools[name] = func
        return tool_id


MODEL_TOKEN_LIMITS = {"llama-3.3-70b-versatile": 128000, "gpt-5": 256000}


def calculate_context_usage(
    context: str, model: str = "llama-3.3-70b-versatile"
) -> dict:
    tokens = len(context) // 4
    max_tokens = MODEL_TOKEN_LIMITS.get(model, 128000)
    percent = round((tokens / max_tokens) * 100, 1)
    return {"tokens": tokens, "max": max_tokens, "percent": percent}


def monitor_context_window(
    context: str, model: str = "llama-3.3-70b-versatile"
) -> dict:
    res = calculate_context_usage(context, model)
    res["status"] = (
        "ok"
        if res["percent"] < 50
        else ("warning" if res["percent"] < 80 else "critical")
    )
    return res


async def summarise_context_window(
    content: str,
    memory_manager: MemoryManager,
    llm_instance: Any = None,
    thread_id: Optional[str] = None,
) -> dict:
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
    await memory_manager.write_summary(
        summary_id, cleaned, summary_text, desc, thread_id=thread_id
    )
    return {"id": summary_id, "description": desc, "summary": summary_text}


async def summarize_conversation(
    thread_id: str, memory_manager: MemoryManager, llm_instance: Any = None
) -> dict:
    stmt = (
        select(AgentConversationalHistoryModel.content)
        .where(
            AgentConversationalHistoryModel.thread_id == thread_id,
            AgentConversationalHistoryModel.summary_id.is_(None),
        )
        .order_by(AgentConversationalHistoryModel.timestamp.asc())
    )
    async with memory_manager.session_factory() as session:
        res = await session.execute(stmt)
        rows = res.scalars().all()

    if not rows:
        return {"status": "nothing_to_summarize"}

    transcript = "\n".join(rows)
    result = await summarise_context_window(
        transcript, memory_manager, llm_instance, thread_id=thread_id
    )
    if result.get("status") != "nothing_to_summarize":
        await memory_manager.mark_as_summarized(thread_id, result["id"])
    return result
