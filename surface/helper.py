import re
from typing import Optional
from uuid import UUID

import anthropic
import openai
from bs4 import BeautifulSoup
from chat_threads.threads.dao import ThreadDao

from config.settings import loaded_config
from llm_agent.mappers import AgentMapper
from surface.constants import SurfaceType, Thresholds
from surface.serializers import SurfaceRequest
from threads.utils import append_thread_data, get_current_thread_messages
from utils.common import URLExtractor, ModelResponseHandler
from utils.connection_handler import ConnectionHandler, execute_db_operation
from wrapper.ai_models import ModelRegistry


class SurfaceHelper:
    @staticmethod
    async def _determine_thresholds(surface_request):
        surface_type = surface_request.metadata.get("surface", SurfaceType.DEFAULT.value).lower()
        if surface_type == SurfaceType.INTELLIJ.value:
            return {"surface_type": surface_type, "rand_min": Thresholds.INTELLIJ_MIN,
                    "rand_max": Thresholds.INTELLIJ_MAX}
        elif surface_type == SurfaceType.VSCODE.value:
            return {"surface_type": surface_type, "rand_min": Thresholds.DEFAULT_MIN,
                    "rand_max": Thresholds.DEFAULT_MAX}
        return {"surface_type": surface_type, "rand_min": Thresholds.DEFAULT_MIN, "rand_max": Thresholds.DEFAULT_MAX}

    @staticmethod
    async def get_agent(surface_request: SurfaceRequest, **kwargs):
        model = surface_request.model
        stream = surface_request.stream
        api_key = surface_request.metadata.get("api_key", "")
        last_message = surface_request.data['messages'][-1]
        references = last_message.get('prompt_details', {}).get("references", dict()) or \
                     surface_request.metadata.get("references", dict())
        rag = surface_request.rag
        if references.get('thread', []):
            thread_meta = references.get('thread', [])
            surface_request.data = await append_thread_data(thread_meta,
                                                            surface_request.data)

        last_content = references.get("query", '')
        command = references.get('commands', [])
        if not command:
            urls = URLExtractor.extract_urls_with_symbol(last_content, '@')
            if urls:
                command = [{"command": "@web"}]

        html_query = references.get("questionDOM", '').replace("&nbsp;", " ")
        soup = BeautifulSoup(html_query, 'html.parser')
        highlighted_words = [span.text.strip() for span in soup.find_all('span', class_='selected-command')]

        for word in highlighted_words:
            last_content = last_content.replace(word, ' ')
        last_content = re.sub(r'\s+', ' ', last_content)
        last_content = last_content.strip()
        references["query"] = last_content

        if references.get("kb_ids", []) and loaded_config.kb_agent_enabled == True:
            return AgentMapper.get_agent("KnowledgeBaseSearchAgent", stream=stream,
                                         model=model, api_key=api_key, kb_ids=references.get("kb_ids", []))

        return AgentMapper.get_agent("ConversationalAgent", model=model,
                                     api_key=api_key,
                                     stream=stream,
                                     rag=rag)

    @staticmethod
    async def update_thread_operation(connection_handler: ConnectionHandler, thread_uuid: int,
                                      update_values_dict: dict) -> None:
        """
        Operation to update a thread in the database.

        Args:
            connection_handler: The connection handler for database access.
            thread_uuid (int): The ID of the thread to update.
            update_values_dict (dict): A dictionary of values to update in the thread.
        """
        thread_dao = ThreadDao(session=connection_handler.session)
        await thread_dao.update_thread(thread_uuid=thread_uuid, update_values_dict=update_values_dict)

    @staticmethod
    async def _handle_first_message(message, response_text, **kwargs):
        thread_id = kwargs.get("thread_id", 0)
        content = message.get("content", "")
        last_content = content[0]['text'] if type(content) == list else content

        messages = (
                [
                    {
                        "role": "system",
                        "content": [{
                            "type": "text",
                            "text": """Analyze the conversation between the user and the AI assistant provided below. 
                                    Generate a concise and impactful title (maximum 4 words) that captures the essence of the discussion, 
                                    focusing on the main topic or recurring themes. 
                                    The title should be both relevant and appealing to the user."""
                        }
                        ]
                    }
                ]
                + [
                    {
                        "role": "user",
                        "content": last_content
                    }
                ]
                + [
                    {
                        "role": "assistant",
                        "content": str(response_text) if type(response_text) != str else response_text
                    }
                ]
        )
        llm = ModelRegistry.get_model("gpt-4o")

        response = await llm.predict(messages, stream=False, **kwargs)
        chat_title = response.choices[0].message.content.strip('\"')

        # Update the thread with the generated title
        await execute_db_operation(SurfaceHelper.update_thread_operation, thread_id, {"title": chat_title})

        return chat_title

    @staticmethod
    async def process_messages(thread_uuid: UUID, current_message: list, last_question_id: Optional[int] = None):
        last_message_id = current_message[0].get("parentId", None)
        if thread_uuid:
            thread_messages = await get_current_thread_messages(thread_id=thread_uuid, last_message_id=last_message_id,
                                                                last_question_id=last_question_id)
            # for resend
            if not current_message[0].get('parentId', None):
                current_message[0]['parentId'] = thread_messages[-1].get('id')
            # for regenerate
            if current_message[0].get('regenerate', False):
                thread_messages[-1]['regenerate'] = True
            else:
                thread_messages.extend(current_message)
            return thread_messages
        else:
            return current_message

    @staticmethod
    def _construct_response_data(response, surface_request):
        data = dict()
        if isinstance(response, dict):
            if 'model' in response:
                data["content"] = ModelResponseHandler.get_simple_model_response(surface_request.model, response)
            else:
                data["content"] = response['choices'][0]["message"][
                    "content"] if 'choices' in response \
                    else response
        elif isinstance(response, anthropic.types.message.Message) or isinstance(response,
                                                                                 openai.types.chat.chat_completion.ChatCompletion):
            data["content"] = ModelResponseHandler.get_simple_model_response(surface_request.model, response)
        else:
            data["content"] = response
        return data
