import json
import os
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

BASE_API_URL = os.getenv("BASE_API_URL", "http://localhost:8000/api/v1")


class APIClient:
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
    def _get_headers(cls) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = st.session_state.get("jwt_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @classmethod
    def _request(
        cls,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 10,
    ) -> requests.Response:
        url = f"{BASE_API_URL}{endpoint}"
        return cls.get_session().request(
            method=method,
            url=url,
            json=json_data,
            headers=cls._get_headers(),
            timeout=timeout,
        )

    @classmethod
    def register(cls, name: str, email: str, password: str) -> Dict[str, Any]:
        try:
            res = cls._request(
                "POST",
                "/auth/register",
                {"name": name, "email": email, "password": password},
            )
            return res.json()
        except Exception as e:
            return {"success": False, "error": f"Backend connection failed: {e}"}

    @classmethod
    def login(cls, email: str, password: str) -> Dict[str, Any]:
        try:
            res = cls._request(
                "POST", "/auth/login", {"email": email, "password": password}
            )
            return res.json()
        except Exception as e:
            return {"success": False, "error": f"Backend connection failed: {e}"}

    @classmethod
    def list_sessions(cls, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            res = cls._request("GET", "/sessions")
            return res.json() if res.status_code == 200 else []
        except Exception:
            return []

    @classmethod
    def create_session(
        cls, user_id: Optional[str] = None, title: str = "New Chat Session"
    ) -> Optional[Dict[str, Any]]:
        payload = {"title": title}
        if user_id:
            payload["user_id"] = user_id
        try:
            res = cls._request("POST", "/sessions", payload)
            return res.json() if res.status_code == 200 else None
        except Exception:
            return None

    @classmethod
    def load_session(
        cls, session_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            res = cls._request("GET", f"/sessions/{session_id}")
            return res.json() if res.status_code == 200 else None
        except Exception:
            return None

    @classmethod
    def delete_session(cls, session_id: str, user_id: Optional[str] = None) -> bool:
        try:
            res = cls._request("DELETE", f"/sessions/{session_id}")
            return res.status_code == 200
        except Exception:
            return False

    @classmethod
    def send_chat_message(
        cls, user_text: str, session_id: str, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = {"user_text": user_text, "session_id": session_id, "state": state}
        try:
            res = cls._request("POST", "/chat/message", payload, timeout=60)
            if res.status_code == 200:
                return res.json()
            return {
                "reply": f"Backend Error: HTTP {res.status_code} - {res.text}",
                "tool_logs": [],
                "updated_state": state,
            }
        except Exception as e:
            return {
                "reply": f"Unable to reach FastAPI backend: {e}.",
                "tool_logs": [],
                "updated_state": state,
            }

    @classmethod
    def _parse_sse_line(
        cls, line: str, active_event: str
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        if isinstance(line, bytes):
            line = line.decode("utf-8")

        if line.startswith("event: "):
            return None, line[7:].strip()

        if line.startswith("data: "):
            raw = line[6:]
            try:
                data = json.loads(raw)
            except Exception:
                data = {"chunk": raw, "content": raw}
            return {"event": active_event, "data": data}, active_event

        return None, active_event

    @classmethod
    def stream_chat_message(
        cls, user_text: str, session_id: str, state: Dict[str, Any]
    ):
        url = f"{BASE_API_URL}/chat/stream"
        payload = {"user_text": user_text, "session_id": session_id, "state": state}
        try:
            with cls.get_session().post(
                url, json=payload, headers=cls._get_headers(), stream=True, timeout=60
            ) as http_response:
                if http_response.status_code != 200:
                    yield {
                        "event": "error",
                        "data": {
                            "error": f"Backend Error HTTP {http_response.status_code}"
                        },
                    }
                    return

                active_event = "message"
                for line in http_response.iter_lines(decode_unicode=True):
                    if line:
                        str_line = (
                            line.decode("utf-8") if isinstance(line, bytes) else line
                        )
                        evt_obj, active_event = cls._parse_sse_line(
                            str_line, active_event
                        )
                        if evt_obj:
                            yield evt_obj

        except Exception as e:
            yield {
                "event": "error",
                "data": {"error": f"Unable to reach FastAPI backend: {e}"},
            }
