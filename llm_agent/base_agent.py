class BaseAgent:
    tools: list = []
    tool_chains: list = []
    base_prompt: str = ""
    actions: list = []
    tool_model_prompt_template: str = ""

    def __init__(self, *args, **kwargs):
        pass

    def add_tools(self, tools):
        agent_tools = []
        for tool_class in tools:
            tool = tool_class(llm=self.llm, memory=self.memory)
            # agent_tools.append(
            #     Tool(name=tool.name, func=tool.tool_function, description=tool.description)
            # )
        self.tools = agent_tools

    async def process_input(self, input_data: {}):
        raise NotImplementedError

    async def execute(self, **kwargs):
        raise NotImplementedError

    async def process_output(self):
        # This method is intentionally left empty because the current implementation
        # does not require any specific processing of the output. The output is directly
        # handled by the `execute` method. This method can be extended in the future if
        # additional output processing is needed.
        pass

    async def handle(self, data, **kwargs):
        await self.process_input(data)
        await self.execute()
        response = await self.process_output()
        return response
