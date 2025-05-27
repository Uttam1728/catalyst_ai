from config.settings import loaded_config
from llm_agent.base_agent import BaseAgent
from utils.common import MessageTransformer
from utils.exceptions import InvalidInputException
from utils.prompts import conversation_base_prompt, generate_user_persona_tags_without_input_prompt, \
    generate_conversation_summary_prompt, user_persona_tags_response_prompt, message_summary_prompt
from wrapper.ai_models import UnifiedModel


class ConversationalAgent(BaseAgent):
    def __init__(self, tools, llm: UnifiedModel, stream=False, rag=None, **kwargs):
        super(ConversationalAgent, self).__init__(tools, llm)
        self.llm = llm
        self.input_messages = []
        self.stream = stream
        self.user_tags = []
        self.summaries = []
        self.messages = []

    async def process_input(self, input_data, user_tags=None, **kwargs):
        self.validate_input(input_data)
        self.user_tags = user_tags

        # Build conversation messages
        self.input_messages = self.build_conversation_messages(input_data)

        MessageTransformer.additional_rule_addition_system_messages(self.input_messages,
                                                                    kwargs.get("additional_rules", ""))

    def validate_input(self, input_data):
        if not isinstance(input_data, dict) or "messages" not in input_data:
            raise InvalidInputException()

    def build_conversation_messages(self, conversation):
        summaries_and_messages = conversation.get(
            'summary_and_messages', {"summaries": [], "messages": conversation["messages"]}
        )
        self.messages = conversation["messages"]
        summary_prompt = ""
        if loaded_config.use_thread_summaries:
            self.messages = summaries_and_messages['messages']
            self.summaries = summaries_and_messages['summaries']
            summary_prompt = message_summary_prompt.substitute(summaries=self.summaries)
        return ([
                    {
                        "role": "system",
                        "content": [{
                            "type": "text",
                            "text": conversation_base_prompt
                        }]
                    },
                ] + conversation["messages"] + [
                    {
                        "role": "system",
                        "content": [
                            {
                                'type': 'text',
                                'text': user_persona_tags_response_prompt.substitute(
                                    user_tags=f"#{' #'.join(self.user_tags or [])}")
                            }
                        ]
                    },
                    {
                        "role": "system",
                        "content": [{
                            "type": "text",
                            "text": generate_user_persona_tags_without_input_prompt
                        }]
                    }
                ]
                + [
                    {
                        "role": "system",
                        "content": [{
                            "type": "text",
                            "text": generate_conversation_summary_prompt

                        }]}
                ]
                + [
                    {
                        "role": "system",
                        "content": [{
                            "type": "text",
                            "text": summary_prompt

                        }]}
                ])

    async def process_output(self):
        return

    async def execute(self, **kwargs):
        # Check if this is a devas product request
        product = kwargs.get('product', '')

        # Set use_mcp to True for devas product
        if product == 'devas':
            kwargs['use_mcp'] = True
        else:
            kwargs['use_mcp'] = False

        response = await self.llm.predict(messages=self.input_messages, stream=self.stream, **kwargs)
        return response

    async def handle(self, data, **kwargs):
        await self.process_input(data, **kwargs)
        output = await self.execute(**kwargs)
        return output
