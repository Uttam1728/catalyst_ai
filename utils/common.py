import json
import os
import traceback
from datetime import datetime
from enum import Enum
from urllib.parse import urlparse
from uuid import UUID

import sentry_sdk
from clerk_integration.exceptions import UserDataException
from clerk_integration.utils import UserData
from fastapi import HTTPException, status
from fastapi_prometheus_middleware import get_metrics
from fastapi_prometheus_middleware.context import token_usage_context
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sqlalchemy import inspect
from starlette.requests import Request
from tiktoken import encoding_for_model

from config.settings import loaded_config
from utils.base_view import BaseView
from utils.exceptions import SessionExpiredException
from utils.references_schema import ReferencesSchema
from wrapper.ai_models import ModelRegistry

additional_rules_prompt = "\nAdditional Rules: {additional_rules}\n"


class URLExtractor:
    @staticmethod
    def extract_urls_with_symbol(text, symbol):
        words = text.split()
        urls = []
        for word in words:
            if word.startswith(symbol):
                url = word[1:]
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:
                    urls.append(url)
        return urls


class ModelResponseHandler:
    @staticmethod
    async def stream_model_response(model_name, stream):
        metrics = get_metrics('api_metrics')
        try:
            if any(model_type in model_name for model_type in ["openai", "gpt", "o1", "deepseek"]):
                async for message in stream:
                    if getattr(message, "usage", None) is not None:
                        token_data = token_usage_context.get()
                        input_tokens = message.usage.prompt_tokens
                        output_tokens = message.usage.completion_tokens
                        total_tokens = message.usage.total_tokens
                        token_data["total_tokens"] += total_tokens
                        token_data["input_tokens"] += input_tokens
                        token_data["output_tokens"] += output_tokens
                        token_usage_context.set(token_data)

                        # Track token usage with Prometheus
                        metrics.track_token_usage(
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total_tokens
                        )
                    elif hasattr(message, 'choices') and message.choices and message.choices[0].delta:
                        yield message.choices[0].delta.content

            elif "claude" in model_name:
                async for event in stream:
                    if event.type == "progress":
                        yield event.payload
                    elif event.type == "text":
                        yield event.text
                    elif event.type == "message_start":
                        usage = event.message.usage
                        input_tokens = usage.input_tokens
                        output_tokens = usage.output_tokens
                        total_tokens = input_tokens + output_tokens + usage.cache_creation_input_tokens + \
                                       usage.cache_read_input_tokens
                        token_data = token_usage_context.get()
                        token_data["total_tokens"] += total_tokens
                        token_data["input_tokens"] += input_tokens
                        token_data["output_tokens"] += output_tokens
                        token_usage_context.set(token_data)

                    elif event.type == "message_delta":
                        usage = event.usage
                        output_tokens = usage.output_tokens
                        token_data = token_usage_context.get()
                        token_data["total_tokens"] += output_tokens
                        token_data["output_tokens"] += output_tokens
                        token_usage_context.set(token_data)

                        # Track token usage with Prometheus
                        metrics.track_token_usage(
                            input_tokens=token_data["input_tokens"],
                            output_tokens=token_data["output_tokens"],
                            total_tokens=token_data["total_tokens"]
                        )
            else:
                raise Exception(f"Unsupported model or no output available. {model_name} {stream}")
        except Exception as e:
            with sentry_sdk.push_scope() as scope:
                stack_trace = traceback.format_exc()
                scope.set_extra("stack_trace", stack_trace)
                sentry_sdk.capture_exception(e)
            BaseView.construct_error_response(e)
            yield ""

    @staticmethod
    def get_simple_model_response(model_name: str, response: dict | str | object) -> str:
        metrics = get_metrics('api_metrics')
        try:
            if any(model_type in model_name for model_type in ["openai", "gpt", "o1", "deepseek"]):
                token_data = token_usage_context.get()
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                total_tokens = response.usage.total_tokens
                token_data["total_tokens"] += total_tokens
                token_data["input_tokens"] += input_tokens
                token_data["output_tokens"] += output_tokens
                token_usage_context.set(token_data)

                # Track token usage with Prometheus
                metrics.track_token_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens
                )
                return response.choices[0].message.content
            elif "claude" in model_name:
                token_data = token_usage_context.get()
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens + response.usage.cache_creation_input_tokens + \
                               response.usage.cache_read_input_tokens
                token_data["total_tokens"] += total_tokens
                token_data["input_tokens"] += input_tokens
                token_data["output_tokens"] += output_tokens
                token_usage_context.set(token_data)

                # Track token usage with Prometheus
                metrics.track_token_usage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens
                )
                return response.content[0].text if response.content and len(response.content) > 0 and hasattr(
                    response.content[0], 'text') else ""
            else:
                raise ValueError(f"Unsupported model: {model_name}")
        except Exception as e:
            BaseView.construct_error_response(e)
            return ""


class MessageTransformer:
    @staticmethod
    async def transform_messages(data, model_name):
        for message in data:
            role = message.get('role')
            content = message.get('content')

            if 'question_meta:' in content:
                content_parts = content.split('question_meta:')

                try:
                    question_meta = json.loads(content_parts[1].strip())
                except json.JSONDecodeError:
                    question_meta = {}

                if 'references' in question_meta:
                    reference_content = MessageTransformer.create_content_from_reference(question_meta['references'])
                    if 'enhancedFileContext' in question_meta:
                        reference_content += "Enhanced File Context For More Reference\n"
                        reference_content += question_meta['enhancedFileContext']
                    new_content = [{"type": "text", "text": reference_content}]
                else:
                    new_content = [{"type": "text", "text": content.strip()}]

                model_llm = ModelRegistry.get_model(model_name)
                if model_llm.config.accept_image and 'image' in question_meta or 'images' in question_meta:
                    new_content = await MessageTransformer.transform_image_messages(question_meta, model_name,
                                                                                    new_content)
            else:
                new_content = [{
                    "type": "text",
                    "text": content.strip()
                }]

            message.clear()
            message['role'] = role
            message['content'] = new_content

        return data

    @staticmethod
    def create_content_from_reference(references):
        try:
            ref_data = ReferencesSchema(**references)
            content = ref_data.extract_content()
            return content
        except Exception:
            return references.get("query")

    @staticmethod
    async def transform_image_messages(question_meta, model_name, new_content):
        images = question_meta.get('images', [question_meta.get('image')] if 'image' in question_meta else [])[:5]

        for image_url in images:
            if not image_url:
                continue

            if "openai" in model_name or "gpt" in model_name or "o1" in model_name:
                new_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": image_url,
                    },
                })
            elif "claude" in model_name:
                parts = image_url.split(',', 1)
                media_type = "image/" + parts[0].split(';')[0].split('/')[1] if len(parts) > 1 else 'unknown'
                base64_data = parts[1] if len(parts) > 1 else ''

                new_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64_data,
                    }
                })

        return new_content

    @staticmethod
    def additional_rule_addition_system_messages(messages, additional_rules):
        if not additional_rules:
            return
        for message in messages:
            if message.get('role') == 'system':
                if type(message['content']) == list:
                    message["content"][0]["text"] += additional_rules_prompt.format(additional_rules=additional_rules)
                else:
                    message['content'] += additional_rules_prompt.format(additional_rules=additional_rules)
                break

    @staticmethod
    def langchain_splitter(text):
        splitter = RecursiveCharacterTextSplitter(chunk_size=1600, chunk_overlap=20)
        return splitter.split_text(text)


class TokenCalculator:
    @staticmethod
    def calculate_tokens(message, model_name):
        """Calculate tokens for a single message."""
        if any(model_type in model_name for model_type in ["openai", "gpt", "o1", "deepseek", "claude", "anthropic"]):
            try:
                ENCODING = encoding_for_model(model_name)
            except KeyError:
                # Fallback to cl100k_base encoding which is used by most recent models
                ENCODING = encoding_for_model("gpt-4")

            if isinstance(message["content"], str):
                return len(ENCODING.encode(message["content"]))
            elif isinstance(message["content"], list):
                tokens = 0
                for item in message["content"]:
                    if item["type"] == "text":
                        tokens += len(ENCODING.encode(item["text"]))
                return tokens

        return 0

    @staticmethod
    async def trim_messages(messages, model_name):
        system_messages = [msg for msg in messages if msg.get("role") == "system"]
        user_and_assistant_messages = [msg for msg in messages if msg.get("role") != "system"]

        system_tokens = sum(TokenCalculator.calculate_tokens(msg, model_name) for msg in system_messages)

        def calculate_total_tokens(subset):
            return system_tokens + sum(TokenCalculator.calculate_tokens(msg, model_name) for msg in subset)

        total_tokens = calculate_total_tokens(user_and_assistant_messages)
        if total_tokens <= loaded_config.max_tokens:
            return messages

        left = 0
        right = len(user_and_assistant_messages)

        while left < right:
            mid = (left + right) // 2
            retained_messages = user_and_assistant_messages[mid:]

            total_tokens = calculate_total_tokens(retained_messages)

            if total_tokens <= loaded_config.max_tokens:
                return system_messages + retained_messages
            else:
                right = mid

        final_messages = system_messages

        final_trimmed_messages = TokenCalculator.trim_last_message_if_still_exceeds(final_messages,
                                                                                    user_and_assistant_messages[right:],
                                                                                    right, model_name)

        return final_trimmed_messages

    @staticmethod
    def trim_last_message_if_still_exceeds(final_messages, user_assistant_msgs, right, model_name):
        final_single_msg = user_assistant_msgs[right]

        if TokenCalculator.calculate_tokens(final_single_msg, model_name) <= loaded_config.max_tokens:
            final_messages.append(final_single_msg)
            return final_messages

        original_content = final_single_msg.get("content", "")

        if isinstance(original_content, str):
            length = len(original_content)
            remove_length = length // 5
            truncated_content = original_content[:length - remove_length]
            trimmed_msg = {**final_single_msg, "content": truncated_content}
            final_messages.append(trimmed_msg)

        elif isinstance(original_content, list):
            all_text = "".join(item["text"] for item in original_content if item["type"] == "text")
            length = len(all_text)
            remove_length = length // 5
            truncated_text = all_text[:length - remove_length]

            truncated_list = []
            remaining = len(truncated_text)
            for item in original_content:
                if item["type"] == "text":
                    text = item["text"]
                    if len(text) <= remaining:
                        truncated_list.append({"type": "text", "text": text})
                        remaining -= len(text)
                    else:
                        if remaining > 0:
                            truncated_list.append({"type": "text", "text": text[:remaining]})
                        break

            trimmed_msg = {**final_single_msg, "content": truncated_list}
            final_messages.append(trimmed_msg)

        else:
            trimmed_msg = {**final_single_msg, "content": ""}
            final_messages.append(trimmed_msg)

        return final_messages


class UserDataHandler:
    @staticmethod
    async def get_user_data_from_request(request: Request):
        try:
            # Check if we should use dummy user based on config

            if loaded_config.use_dummy_user:
                current_time = datetime.now()
                dummy_user = UserData(
                    _id=1,
                    orgId=str(1),
                    firstName="Test",
                    lastName="User",
                    email="ushankradadiya@gofynd.com",
                    username="test_user",
                    phoneNumber=None,  # Optional field
                    profilePicUrl=None,  # Optional field
                    active=True,
                    roleIds=[1],
                    meta={},  # Required but can be empty
                    createdAt=current_time,  # Required
                    updatedAt=current_time,  # Required
                    workspace=[{}]
                )
                return dummy_user
            else:
                return await loaded_config.clerk_auth_helper.get_user_data_from_clerk(request)
        except UserDataException as e:
            try:
                user_data: UserData = request.state.user_data
                return user_data
            except Exception as e:
                BaseView.construct_error_response(e)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": SessionExpiredException.DEFAULT_MESSAGE,
                        "message": str(e),
                        "code": SessionExpiredException.ERROR_CODE
                    }
                ) from e

    @staticmethod
    def validate_email_match(user_email: str, requested_by: str):
        if user_email != requested_by:
            raise HTTPException(status_code=403, detail="Unauthorized access to this resource.")


class SQLAlchemySerializer:
    @staticmethod
    def to_serializable_dict(obj):
        """Convert SQLAlchemy object to a JSON-serializable dictionary."""
        result = {}
        for column in inspect(obj).mapper.column_attrs:
            value = getattr(obj, column.key)

            # Convert UUID to string
            if isinstance(value, UUID):
                value = str(value)

            # Convert Enum to string
            elif isinstance(value, Enum):
                value = value.name

            # Convert datetime to ISO format string
            elif isinstance(value, datetime):
                value = value.isoformat()

            result[column.key] = value
        return result
