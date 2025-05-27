from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator

from surface.constants import MessageType
from utils.common import ModelResponseHandler
from .base_view import BaseView
from .stream_strategy import StreamStrategyFactory, StreamStrategyType


@dataclass
class StreamConfig:
    rand_min: int
    rand_max: int
    checksum: str = "#userPersonaTags="


class StreamHandler(ABC):
    def __init__(self, config: StreamConfig, strategy_type: StreamStrategyType = StreamStrategyType.STRING):
        self.config = config
        self.strategy = StreamStrategyFactory.create_strategy(strategy_type)

    @abstractmethod
    async def handle_stream(self, response, **kwargs) -> AsyncGenerator[str, None]:
        pass

    def format_output(self, content: str, msg_type: str = MessageType.DATA) -> str:
        """Format the output using the selected strategy"""
        return self.strategy.format_output(content, msg_type)


class DefaultStreamHandler(StreamHandler):
    def __init__(self, config: StreamConfig, strategy_type: StreamStrategyType = StreamStrategyType.STRING):
        super().__init__(config, strategy_type)

    async def handle_stream(self, response, **kwargs) -> AsyncGenerator[str, None]:
        try:
            formatted_response = self.format_output(response, msg_type=MessageType.DATA)
            yield formatted_response
        except Exception as e:
            error_msg = f"Error in default stream handler: {str(e)}"
            yield self.format_output(error_msg, msg_type=MessageType.ERROR)


class StreamHandlerFactory:
    @staticmethod
    def create_handler(handler_type: str, config: StreamConfig,
                       strategy_type: StreamStrategyType = StreamStrategyType.STRING, **kwargs) -> StreamHandler:
        handlers = {
            'default': DefaultStreamHandler,
            'combined': CombinedStreamHandler  # New combined handler for multiple markers
        }
        handler_class = handlers.get(handler_type, DefaultStreamHandler)
        return handler_class(config, strategy_type, **kwargs)


# Optional: Create a combined handler that can handle both tags and summaries
class CombinedStreamHandler(StreamHandler):
    def __init__(self, config: StreamConfig, strategy_type: StreamStrategyType = StreamStrategyType.STRING, **kwargs):
        super().__init__(config, strategy_type)
        self.markers = {
            'tags': '#userPersonaTags=',
            'summary': '#messageSummary='
        }
        self.result = {
            'response_text': '',
            'tags': [],
            'summary': ''
        }

    async def handle_stream(self, response, **kwargs):
        model = kwargs['model']
        output_text = ""
        response_text = ""
        hold_text = ""
        full_response = ""

        # Track both types of tags
        tags_found = False
        summary_found = False

        checking = False
        # Use the markers from self.markers
        tag_checksum = self.markers['tags']
        summary_checksum = self.markers['summary']
        checksums = [tag_checksum, summary_checksum]
        current_checksum = None
        yield_substr = ""

        # Handle string response
        if isinstance(response, str):
            self.result['response_text'] = response
            yield self.format_output(response, msg_type=MessageType.DATA)
            return

        try:
            async for output in ModelResponseHandler.stream_model_response(model, response):
                # Keep track of full response for later processing
                if output is None:
                    continue
                if type(output) is dict:
                    msg_type = output.get("type", "")
                    msg_content = output.get("content", "")
                    yield self.format_output(msg_content, msg_type)
                    continue
                full_response += output
                hold_text += output

                # If we've found either tag, just accumulate the text without yielding
                if tags_found or summary_found:
                    continue

                if checking:
                    # Check if the current checksum is complete
                    if current_checksum and hold_text in current_checksum:
                        checking = True
                    elif any(checksum in hold_text for checksum in checksums):
                        # Determine which checksum was found
                        if tag_checksum in hold_text:
                            tags_found = True
                        if summary_checksum in hold_text:
                            summary_found = True
                        checking = False
                    else:
                        checking = False
                        current_checksum = None

                if not checking and "#" in hold_text:
                    index = hold_text.rindex("#")
                    substr = hold_text[index:]

                    # Check if substring matches start of any checksum
                    is_potential_checksum = False
                    for checksum in checksums:
                        if substr in checksum:
                            yield_substr = hold_text[:index]
                            hold_text = hold_text[index:]
                            checking = True
                            current_checksum = checksum
                            is_potential_checksum = True
                            break
                        elif checksum in substr:
                            checking = True
                            # Determine which checksum was found
                            if tag_checksum in substr:
                                tags_found = True
                            if summary_checksum in substr:
                                summary_found = True
                            is_potential_checksum = True
                            break

                    if not is_potential_checksum:
                        checking = False
                        current_checksum = None

                if not (tags_found or summary_found) and not checking:
                    output_text += hold_text
                    hold_text = ""
                elif yield_substr:
                    output_text += yield_substr
                    yield_substr = ""

                # Only yield if we haven't found any tags yet
                if not (tags_found or summary_found) and output_text:
                    yield self.format_output(output_text, msg_type=MessageType.DATA)
                    output_text = ""

            # Final yield only if we haven't found any tags
            if output_text and not (tags_found or summary_found):
                yield self.format_output(output_text, msg_type=MessageType.DATA)

            # Store the complete response
            self.result['response_text'] = full_response

            # Extract tags if present
            if self.markers['tags'] in full_response:
                tags_section = full_response.split(self.markers['tags'])[1]
                # Take everything up to the next marker if it exists
                if self.markers['summary'] in tags_section:
                    tags_section = tags_section.split(self.markers['summary'])[0]
                self.result['tags'] = [tag.strip() for tag in tags_section.strip().split(',')]

            # Extract summary if present
            if self.markers['summary'] in full_response:
                summary_section = full_response.split(self.markers['summary'])[1]
                # Take everything up to the next marker if it exists
                if self.markers['tags'] in summary_section:
                    summary_section = summary_section.split(self.markers['tags'])[0]
                self.result['summary'] = summary_section.strip()


        except Exception as e:
            error_msg = f"Error processing stream: {str(e)}"
            BaseView.construct_error_response(e)
            yield self.format_output(error_msg, msg_type=MessageType.ERROR)

    def get_result(self):
        return self.result
