from enum import Enum


class SurfaceType(Enum):
    INTELLIJ = "intellij"
    VSCODE = "vscode"
    DEFAULT = "vscode"


class Thresholds:
    DEFAULT_MIN = 5
    DEFAULT_MAX = 10
    INTELLIJ_MIN = 1
    INTELLIJ_MAX = 1


class MessageType:
    ERROR = "error"
    DATA = "data"
    PROGRESS = "progress"
    THREAD_UUID = "thread_uuid"
    LAST_USER_MESSAGE_ID = "last_user_message_id"
    LAST_USER_MESSAGE = "last_user_message"
    LAST_AI_MESSAGE = "last_ai_message"
    CONVERSATION_TITLE = "conversation_title"
    STREAM_START = "stream_start"
    STREAM_END = "stream_end"
    LAST_AI_MESSAGE_ID = "last_ai_message_id"
