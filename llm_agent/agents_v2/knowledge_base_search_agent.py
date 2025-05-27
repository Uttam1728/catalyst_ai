import re
from typing import List

from config.settings import loaded_config
from integrations.ingestion import SemanticSearch
from llm_agent.base_agent import BaseAgent
from utils.common import ModelResponseHandler
from utils.prompts import workspace_query_generator_prompt, workspace_search_prompt
from wrapper.ai_models import UnifiedModel


class KnowledgeBaseSearchAgent(BaseAgent):
    """Agent to handle workspace search operations."""

    # Define constants for string literals
    CRAFTING_QUERY_MESSAGE = "Crafting a smart search query"
    GATHERING_INSIGHTS_MESSAGE = "Gathering valuable insights"
    REFINING_DETAILS_MESSAGE = "Almost there, refining the details"
    DONE_MESSAGE = "Done! Here's your well-crafted response"

    def __init__(self, tools, llm: UnifiedModel, stream=False, **kwargs):
        super(KnowledgeBaseSearchAgent, self).__init__(tools, llm)
        self.input_prompt = None
        self.llm = llm
        self.add_tools(tools)
        self.input_messages = []
        self.stream = True
        self.api_client = SemanticSearch(loaded_config.ingestion_url)
        self.kb_ids = kwargs.get('kb_ids', [])

    async def process_input(self, input_data: dict, **kwargs):
        """Process the input data and generate search queries."""
        last_message = input_data["messages"][-1]
        team_id = last_message.get("team_id")
        yield self.CRAFTING_QUERY_MESSAGE
        references = kwargs.get("references", {})
        query = self._clean_query(references.get("query", ""))
        tasks = await self._create_search_tasks(query, self.kb_ids, team_id, kwargs.get("user_id", ""),
                                                kwargs.get("org_id", ""))

        yield self.GATHERING_INSIGHTS_MESSAGE
        yield self.REFINING_DETAILS_MESSAGE

        self.input_messages = self._construct_input_messages(tasks, query)
        yield self.DONE_MESSAGE

    @staticmethod
    def _clean_query(query: str) -> str:
        """Remove unnecessary characters from the query."""
        return re.sub(r"@\S+", "", query)

    async def _generate_query(self, input_data, **kwargs) -> str:
        role_content_messages = [{"role": msg['role'], "content": msg['content']} for msg in input_data['messages']]
        prompt = workspace_query_generator_prompt.substitute(messages=role_content_messages)

        search_query_result = await self.llm.predict(messages=[{"role": "user", "content": prompt}], stream=False,
                                                     **kwargs)
        search_query = ModelResponseHandler.get_simple_model_response(self.llm.config.engine, search_query_result)

        return self._clean_query(search_query)

    async def _create_search_tasks(self, query: str, knowledge_base_ids: List[int], team_id: str, user_id: str,
                                   org_id: str):
        # Return a single-element list containing the API call coroutine
        return await self.api_client.call_knowledge_base_search(
            query=query,
            knowledge_base_id=knowledge_base_ids,
            team_id=team_id,
            user_id=user_id,
            org_id=org_id
        )

    @staticmethod
    def _construct_input_messages(results: list, query: str) -> list:
        """Construct input messages for the LLM."""
        return [
            {"role": "system", "content": workspace_search_prompt.template},
            {"role": "user", "content": workspace_search_prompt.substitute(files=results, query=query)}
        ]

    async def execute(self, **kwargs):
        """Execute the LLM prediction."""
        response = await self.llm.predict(messages=self.input_messages, stream=self.stream, **kwargs)
        return response
