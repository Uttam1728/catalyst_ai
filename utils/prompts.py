from string import Template

from config.settings import loaded_config

conversation_base_prompt = f"""You are an AI assistant Named {loaded_config.app_name} that helps people find information."""

generate_conversation_summary_prompt = """
Your another task is to analyze the current user conversation and generate a summary of the interaction.
 - give summary at the end of previous task's response like - #messageSummary=<summary of the current interaction>
"""

generate_user_persona_tags_without_input_prompt = """
Your another task is to analyzing the **last user prompt** to identify relevant tags based on a predefined set of 
categories. Your output must be highly accurate and include tags directly supported by the user input. 
Tags should not be inferred beyond what is explicitly stated.

1. **Output Format**:
   - At the end of your response, append the tags in this format:
     `#userPersonaTags=<comma-separated list of tags>`

"""

user_persona_tags_response_prompt = Template("""
Below tags are sorted in User Preference Manner
User Preference Tags
~~~
$user_tags
~~~

Use above tags to answer the user query.
""")

message_summary_prompt = Template("""
Following are the available summaries of previous interactions in order. There may or may not be any summaries.
Use the summaries to respond to the user.

Summaries:
~~~~~~~~~~~~~~~~~
$summaries
~~~~~~~~~~~~~~~~~
""")

workspace_search_prompt = Template("""
You are a coding assistant integrated with VSCode, . 
**Question:** $query

**Context:** $files
""")

workspace_query_generator_prompt = Template("""
You are a search query generating agent. Your task is to analyze the conversation between User and Assistant and come up with
search query for each reference provided.
Conversation:
${messages}

Response format:
1. @wide_search:function
2. ThreadService Class

Rules:
- Always respond in the given Response Format. Do not add any other details or notes etc. Do not give any extra information.
- Always stick to the information provided.
- Do not add double or single quotes or any quotes around the response.
- Specific search is always preferred more than wide search, so, whenever possible, opt for specific search and return response.
- Wide search should always start with '@wide_search'.
- Only possible combinations in @wide_search could be of 'file', 'function', 'module', 'class'. There cant be any other.
- Only give one search query as a string. Do not give numbrered output. 
- ** Consider the last message with the context of the entire message to understand what the user wants to search about. **
- ** Ignore previous messages if they are not relevant to last message from user"

""")
