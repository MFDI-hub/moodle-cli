"""Chat sessions and messages."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class ChatService(BaseService):
    def sessions(self, chat_id: int) -> Any:
        return self.call("mod_chat_get_sessions", chatid=chat_id)

    def messages(self, chat_id: int, session_start: int = 0, session_end: int = 0) -> Any:
        params: dict[str, Any] = {"chatid": chat_id}
        if session_start:
            params["sessionstart"] = session_start
        if session_end:
            params["sessionend"] = session_end
        return self.call("mod_chat_get_session_messages", **params)

    def send(self, chat_id: int, message: str) -> Any:
        return self.call("mod_chat_send_chat_message", chatid=chat_id, messagetext=message)
