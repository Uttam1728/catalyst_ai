import time
import uuid
from typing import Dict, Any


class ChunkDelta:
    """Represents the delta content in a streaming chunk response."""

    def __init__(self, content_type: str, content_text: str):
        self.content = {"type": content_type, "content": content_text}

    def model_dump(self) -> Dict[str, Any]:
        return {"content": self.content}


class ChunkChoice:
    """Represents a choice in a streaming chunk response."""

    def __init__(self, index: int, delta: ChunkDelta):
        self.index = index
        self.delta = delta
        self.finish_reason = None

    def model_dump(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "delta": self.delta.model_dump(),
            "finish_reason": self.finish_reason
        }


class OpenAICompatibleChunk:
    """Custom chunk response that mimics OpenAI's format but allows custom content types."""

    def __init__(self, chunk_type: str, content: str):
        self.id = f"custom-chatcmpl-{uuid.uuid4()}"
        self.object = "chat.completion.chunk"
        self.created = int(time.time())
        self.model = "custom"

        delta = ChunkDelta(chunk_type, content)
        self.choices = [ChunkChoice(0, delta)]

    def model_dump(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization."""
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [choice.model_dump() for choice in self.choices]
        }


class AnthropicCompatibleChunk:
    """Custom chunk response that mimics Anthropic's format with type and payload."""

    def __init__(self, chunk_type: str, content: Any):
        self.type = chunk_type
        self.payload = content if isinstance(content, dict) else {
            "type": self.type, "content": content
        }

    def model_dump(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization."""
        return {
            "type": self.type,
            "payload": self.payload
        }


def create_llm_chunk(chunk_type: str, content: str, provider: str = "openai") -> Any:
    """Create a custom progress chunk that mimics the format of the specified provider.
    
    Args:
        chunk_type: The type of content being sent
        content: The content text or data
        provider: The provider format to use ('openai' or 'anthropic')
        
    Returns:
        A formatted chunk compatible with the specified provider
    """
    if provider.lower() == "anthropic":
        return AnthropicCompatibleChunk(chunk_type, content)
    elif provider.lower() == "openai":
        return OpenAICompatibleChunk(chunk_type, content)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
