from loguru import logger
from typing import Any, Optional
from datetime import datetime

from core.utils.json_serializable import JSONSerializable


class BaseMessage(JSONSerializable):
    """
    The base abstract message class.

    Messages are the inputs and outputs of Models.
    """

    # The string content of the message.
    content: str

    # The created_by of the message. AI, Human, Bot etc.
    created_by: str

    # Any additional info.
    metadata: dict[str, Any]

    def __init__(self, content: str, created_by: str, metadata: Optional[dict[str, Any]] = None) -> None:
        super().__init__()
        self.content = content
        self.created_by = created_by
        self.metadata = metadata

    @property
    def type(self) -> str:
        """Type of the Message, used for serialization."""

    @classmethod
    def is_lc_serializable(cls) -> bool:
        """Return whether this class is serializable."""
        return True

    def __str__(self) -> str:
        return f"{self.created_by}: {self.content}"


class ChatMessage(JSONSerializable):
    """
    The base abstract chat message class.

    Chat messages are the pair of (question, answer) conversation
    between human and model.
    """

    human_message: Optional[BaseMessage] = None
    ai_message: Optional[BaseMessage] = None
    timestamp: datetime

    def add_user_message(self, message: str, metadata: Optional[dict] = None):
        if self.human_message:
            logger.debug(
                "Human message already exists in the chat message,\
                overwriting it with new message."
            )

        self.human_message = BaseMessage(content=message, created_by="human", metadata=metadata)

    def add_ai_message(self, message: str, metadata: Optional[dict] = None):
        if self.ai_message:
            logger.debug(
                "AI message already exists in the chat message,\
                overwriting it with new message."
            )

        self.ai_message = BaseMessage(content=message, created_by="ai", metadata=metadata)

    def __str__(self) -> str:
        return f"{self.human_message}\n{self.ai_message} at {self.timestamp}"