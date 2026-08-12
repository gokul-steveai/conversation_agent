import json
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

BASE_API_URL = "http://localhost:8000/api/v1"


class APIClient:
    """Production HTTP Client with connection pooling, retries, and error resilience."""

    _session = None

    @classmethod
    def get_session(cls) -> requests.Session:
        if cls._session is None:
            session = requests.Session()
            retries = Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 503, 504],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(
                max_retries=retries, pool_connections=10, pool_maxsize=20
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            cls._session = session
        return cls._session

    @classmethod
    def register(cls, name: str, email: str, password: str) -> Dict[str, Any]:
        url = f"{BASE_API_URL}/auth/register"
        payload = {"name": name, "email": email, "password": password}
        try:
            http_response = cls.get_session().post(url, json=payload, timeout=10)
            return http_response.json()
        except Exception as exception_detail:
            return {
                "success": False,
                "error": f"Backend connection failed: {str(exception_detail)}",
            }

    @classmethod
    def login(cls, email: str, password: str) -> Dict[str, Any]:
        url = f"{BASE_API_URL}/auth/login"
        payload = {"email": email, "password": password}
        try:
            http_response = cls.get_session().post(url, json=payload, timeout=10)
            return http_response.json()
        except Exception as exception_detail:
            return {
                "success": False,
                "error": f"Backend connection failed: {str(exception_detail)}",
            }

    @classmethod
    def list_sessions(cls, user_id: str) -> List[Dict[str, Any]]:
        url = f"{BASE_API_URL}/sessions"
        try:
            http_response = cls.get_session().get(
                url, params={"user_id": user_id}, timeout=10
            )
            if http_response.status_code == 200:
                return http_response.json()
            return []
        except Exception:
            return []

    @classmethod
    def create_session(
        cls, user_id: str, title: str = "New Chat Session"
    ) -> Optional[Dict[str, Any]]:
        url = f"{BASE_API_URL}/sessions"
        payload = {"user_id": user_id, "title": title}
        try:
            http_response = cls.get_session().post(url, json=payload, timeout=10)
            if http_response.status_code == 200:
                return http_response.json()
            return None
        except Exception:
            return None

    @classmethod
    def load_session(cls, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        url = f"{BASE_API_URL}/sessions/{session_id}"
        try:
            http_response = cls.get_session().get(
                url, params={"user_id": user_id}, timeout=10
            )
            if http_response.status_code == 200:
                return http_response.json()
            return None
        except Exception:
            return None

    @classmethod
    def delete_session(cls, session_id: str, user_id: str) -> bool:
        url = f"{BASE_API_URL}/sessions/{session_id}"
        try:
            http_response = cls.get_session().delete(
                url, params={"user_id": user_id}, timeout=10
            )
            return http_response.status_code == 200
        except Exception:
            return False

    @classmethod
    def send_chat_message(
        cls, user_text: str, session_id: str, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        url = f"{BASE_API_URL}/chat/message"
        payload = {
            "user_text": user_text,
            "session_id": session_id,
            "state": state,
        }
        try:
            http_response = cls.get_session().post(url, json=payload, timeout=60)
            if http_response.status_code == 200:
                return http_response.json()
            return {
                "reply": f"Backend Error: HTTP {http_response.status_code} - {http_response.text}",
                "tool_logs": [],
                "updated_state": state,
            }
        except Exception as exception_detail:
            return {
                "reply": f"Unable to reach FastAPI backend: {str(exception_detail)}. Please check if `uvicorn main:app --port 8000` is running.",
                "tool_logs": [],
                "updated_state": state,
            }

    @classmethod
    def stream_chat_message(
        cls, user_text: str, session_id: str, state: Dict[str, Any]
    ):
        """Streams real-time token events (tool logs and text chunks) from FastAPI SSE endpoint."""
        url = f"{BASE_API_URL}/chat/stream"
        payload = {
            "user_text": user_text,
            "session_id": session_id,
            "state": state,
        }
        try:
            with cls.get_session().post(
                url, json=payload, stream=True, timeout=60
            ) as http_response:
                if http_response.status_code == 200:
                    active_event_type = "message"
                    for line in http_response.iter_lines(decode_unicode=True):
                        if line:
                            if line.startswith("event: "):
                                active_event_type = line[7:].strip()
                            elif line.startswith("data: "):
                                raw_data = line[6:]
                                try:
                                    parsed_data = json.loads(raw_data)
                                    yield {
                                        "event": active_event_type,
                                        "data": parsed_data,
                                    }
                                except Exception:
                                    yield {
                                        "event": active_event_type,
                                        "data": {
                                            "chunk": raw_data,
                                            "content": raw_data,
                                        },
                                    }
                else:
                    yield {
                        "event": "message",
                        "data": {
                            "chunk": f"Backend Error HTTP {http_response.status_code}"
                        },
                    }
        except Exception as exception_detail:
            yield {
                "event": "message",
                "data": {
                    "chunk": f"Unable to reach FastAPI backend: {str(exception_detail)}"
                },
            }
