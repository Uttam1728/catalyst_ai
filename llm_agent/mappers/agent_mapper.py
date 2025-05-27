from llm_agent.agents_v2.conversational_agent import ConversationalAgent

from utils.exceptions import AgentConfigNotFoundException, LLMNotFoundException
from wrapper.ai_models import ModelRegistry


class AgentMapper:
    config = {
        "ConversationalAgent": {"tools": [], "llm": ModelRegistry, "class": ConversationalAgent},
    }

    @classmethod
    def get_agent(cls, agent_slug, model=None, stream=False, session=None, rag=None, **kwargs):
        agent_config = cls.get_agent_config(agent_slug)
        if agent_config is None:
            raise AgentConfigNotFoundException()
        agent_class = agent_config["class"]

        # Get model instance from registry using slug
        llm = agent_config["llm"].get_model(model) if model else agent_config["llm"].get_model(
            "gpt-4o")  # default model

        if llm is None:
            raise LLMNotFoundException(f"Model {model} not found in registry!")

        agent_object = agent_class(
            tools=agent_config["tools"],
            llm=llm,
            stream=stream,
            session=session,
            rag=rag,
            **kwargs
        )

        return agent_object

    @classmethod
    def get_agent_config(cls, agent_slug):
        return cls.config.get(agent_slug)
