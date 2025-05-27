import os
import sys

import configargparse

root_dir = os.path.dirname(os.path.abspath(__file__))
env = os.getenv('ENVIRONMENT', 'local')
default_config_files = "{0}/{1}".format(root_dir, f"default.{env}.yaml")
print(default_config_files)

parser = configargparse.ArgParser(config_file_parser_class=configargparse.YAMLConfigFileParser,
                                  default_config_files=[default_config_files],
                                  auto_env_var_prefix="")
parser.add('--app_name', help='app_name')
parser.add('--use_dummy_user', help='use_dummy_user')
parser.add('--env', help='env')
parser.add('--port', help='port')
parser.add('--host', help='host')
# debug flag
parser.add('--debug', help='debug', action="store_true")
parser.add('--db_url', help='db_url')
parser.add('--read_db_url', help='read_db_url')

parser.add('--ingestion_url', help="ingestion_url")
parser.add('--groq_key', help="groq_key")
parser.add('--redis_payments_url', help="redis_payments_url")
parser.add('--skip_paths_for_restriction', help="skip_paths_for_restriction")

parser.add('--openai_key', help='openai_key')
parser.add('--claude_key', help='claude_key')

parser.add('--K8S_POD_NAME', help='K8S_POD_NAME')

parser.add('--sentry_dsn', help='SENTRY_DSN')
parser.add('--sentry_environment', help='SENTRY_ENVIRONMENT')

# external API keys
parser.add('--stream_token', help='stream_token')

parser.add('--deepseek_api_key', help='DeepSeek model API Key')


parser.add('--thread_summary_count', help='Chat message to be summarised in the entire thread to be processed')
parser.add('--full_message_count', help='Chat messages to be sent as is.')
parser.add('--thread_summary_context_limit',
           help='Max token length for each message beyond which it will be converted to summary')
parser.add('--use_thread_summaries', help='Enable or disable thread summary use in conversational agent.')
parser.add('--clerk_secret_key', help='clerk_secret_key')
parser.add('--kb_agent_enabled', help='kb_agent_enabled')

arguments = sys.argv
print(arguments)
argument_options = parser.parse_known_args(arguments)
# print("argument values")
print(parser.format_values())
docker_args = argument_options[0]
