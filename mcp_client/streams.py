from typing import AsyncIterator, TypeVar, Generic

T = TypeVar('T')


class CustomAsyncStream(Generic[T]):
    """A custom implementation of AsyncStream that wraps an async generator."""

    def __init__(self, generator_func):
        self._generator = generator_func()

    def __aiter__(self) -> AsyncIterator[T]:
        return self

    async def __anext__(self) -> T:
        try:
            return await self._generator.__anext__()
        except StopAsyncIteration:
            raise
        except IndexError as e:
            # Convert IndexError to a proper exception instead of trying to call send() on it
            raise RuntimeError(f"Index error in async stream: {str(e)}")
