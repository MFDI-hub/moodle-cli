"""Messaging service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class MessageRecord(MoodleModel):
    id: int
    user_id_from: Annotated[int, Field(validation_alias="useridfrom")] = 0
    user_id_to: Annotated[int, Field(validation_alias="useridto")] = 0
    text: str = ""
    time_created: Annotated[int, Field(validation_alias="timecreated")] = 0


class ConversationRecord(MoodleModel):
    id: int
    name: str | None = None
    type: int = 1
    member_count: Annotated[int, Field(validation_alias="membercount")] = 0
    # Moodle returns null (not 0) for a conversation with nothing unread.
    unread_count: Annotated[int | None, Field(validation_alias="unreadcount")] = None


class MessageService(BaseService):
    def send_message(self, to_user_id: int, text: str) -> int:
        data = self.call(
            "core_message_send_instant_messages",
            messages=[{"touserid": to_user_id, "text": text}],
        )
        return data[0]["msgid"]

    def get_messages(
        self,
        user_id: int,
        user_id_from: int = 0,
        message_type: str = "conversations",
    ) -> list[MessageRecord]:
        data = self.call(
            "core_message_get_messages",
            useridto=user_id,
            useridfrom=user_id_from,
            type=message_type,
            read=0,
            newestfirst=1,
        )
        return [MessageRecord.model_validate(m) for m in data.get("messages", [])]

    def get_conversations(self, user_id: int) -> list[ConversationRecord]:
        data = self.call(
            "core_message_get_conversations",
            userid=user_id,
        )
        return [ConversationRecord.model_validate(c) for c in data.get("conversations", [])]

    def get_conversation_messages(
        self, current_user_id: int, conversation_id: int
    ) -> list[dict[str, Any]]:
        data = self.call(
            "core_message_get_conversation_messages",
            currentuserid=current_user_id,
            convid=conversation_id,
        )
        return data.get("messages", [])

    def unread_count(self, user_id: int) -> int:
        """Number of conversations with unread messages."""
        data = self.call("core_message_get_unread_conversations_count", useridto=user_id)
        if isinstance(data, dict):
            return int(data.get("count", 0))
        return int(data)
