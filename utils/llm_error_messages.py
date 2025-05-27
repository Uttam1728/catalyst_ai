import json

import openai
from anthropic import (
    BadRequestError, RateLimitError, InternalServerError, AuthenticationError, APIConnectionError, APITimeoutError,
    PermissionDeniedError, NotFoundError, ConflictError, UnprocessableEntityError
)

from config.settings import loaded_config


class LLMErrorMessages:
    """Class to handle error messages for OpenAI and Anthropic APIs."""

    # Define constants for error messages and codes
    OPENAI_ERROR_MESSAGES = {
        openai.APIConnectionError: (
            f"{loaded_config.app_name} Agent is Unable to Establish Connection to API, please try again after Some time",
            2001),
        openai.RateLimitError: (
            f"{loaded_config.app_name} Agent API request has exceeded the rate limit. please try again after Some time",
            2002),
        openai.Timeout: (f"{loaded_config.app_name} Agent API Timeout Error. please try again after Some time", 2006)
    }

    DEFAULT_OPENAI_ERROR_MESSAGE = (f"{loaded_config.app_name} Agent Couldn't Complete Request", 2007)
    INVALID_REQUEST_DEFAULT_MESSAGE = (
        f"{loaded_config.app_name} Agent API cannot process the input due to invalid request details", 2005)

    ANTHROPIC_ERROR_MESSAGES = {
        APIConnectionError: (
            f"{loaded_config.app_name} Agent is unable to establish a connection to the Anthropic API. Please try again after some time or try with another model.",
            1001),
        APITimeoutError: (
            f"{loaded_config.app_name} Agent request to the Anthropic API timed out. Please try again after some time or try with another model.",
            1002),
        RateLimitError: (
            f"{loaded_config.app_name} Agent API request to Anthropic has exceeded the rate limit. Please try again after some time or try with another model.",
            1003),
        BadRequestError: (
            f"{loaded_config.app_name} Agent encountered a bad request error with the Anthropic API. Please try with a different model.",
            1004),
        AuthenticationError: (
            f"{loaded_config.app_name} Agent is unauthorized to access the Anthropic API. Please check your API key.",
            1005),
        PermissionDeniedError: (
            f"{loaded_config.app_name} Agent does not have permission to access the requested resource in the Anthropic API.",
            1006),
        NotFoundError: (f"{loaded_config.app_name} Agent couldn't find the requested resource in the Anthropic API.",
                        1007),
        ConflictError: (
            f"{loaded_config.app_name} Agent encountered a conflict error with the Anthropic API. This may be due to conflicting data.",
            1008),
        InternalServerError: (
            f"{loaded_config.app_name} Agent encountered an internal server error with the Anthropic API. Please try again later.",
            1010)
    }

    # Error types that are not directly mapped to exception classes
    ANTHROPIC_ERROR_TYPES = {
        "invalid_request_error": {
            "low_credit_balance": (
                f"{loaded_config.app_name} Agent cannot access the Claude API due to insufficient credit balance. Please upgrade or purchase credits.",
                1012)
        }
    }

    DEFAULT_ANTHROPIC_ERROR_MESSAGE = (
        f"{loaded_config.app_name} Agent encountered an unexpected error with the Anthropic API", 1011)

    @staticmethod
    def get_openai_invalid_request_message(error):
        """Retrieve message for specific OpenAI InvalidRequestError codes."""
        error_code_messages = {
            'string_above_max_length': (
                f"{loaded_config.app_name} Agent is unable to process strings that exceed the maximum length limit.",
                2003),
            'context_length_exceeded': (f"{loaded_config.app_name} Agent Can't Process Input : {str(error)}", 2004)
        }
        return error_code_messages.get(error.code,
                                       (f"{LLMErrorMessages.INVALID_REQUEST_DEFAULT_MESSAGE[0]}: {str(error)}",
                                        LLMErrorMessages.INVALID_REQUEST_DEFAULT_MESSAGE[1]))

    @classmethod
    def get_openai_error_message(cls, error):
        """Return a user-friendly message and code for OpenAI API errors."""
        if isinstance(error, openai.BadRequestError):
            return cls.get_openai_invalid_request_message(error)

        return cls.OPENAI_ERROR_MESSAGES.get(type(error), (f"{cls.DEFAULT_OPENAI_ERROR_MESSAGE[0]}: {str(error)}",
                                                           cls.DEFAULT_OPENAI_ERROR_MESSAGE[1]))

    @classmethod
    def get_anthropic_error_message(cls, error):
        """Return a user-friendly message and code for Anthropic API errors."""
        if isinstance(error, UnprocessableEntityError):
            return f"{loaded_config.app_name} Agent couldn't process the entity in the Anthropic API: {str(error)}", 1009

        # Handle JSON error responses
        if hasattr(error, 'error') and isinstance(error.error, dict):
            error_type = error.error.get('type')
            error_message = error.error.get('message', '')

            # Check for credit balance error
            if error_type == 'invalid_request_error' and 'credit balance is too low' in error_message:
                return cls.ANTHROPIC_ERROR_TYPES['invalid_request_error']['low_credit_balance']

        # Handle dictionary error directly
        elif isinstance(error, dict) and 'error' in error and isinstance(error['error'], dict):
            error_type = error['error'].get('type')
            error_message = error['error'].get('message', '')

            # Check for credit balance error
            if error_type == 'invalid_request_error' and 'credit balance is too low' in error_message:
                return cls.ANTHROPIC_ERROR_TYPES['invalid_request_error']['low_credit_balance']

        # Handle string representation of JSON
        elif isinstance(error, str):
            try:
                error_dict = json.loads(error)
                if isinstance(error_dict, dict) and 'error' in error_dict and isinstance(error_dict['error'], dict):
                    error_type = error_dict['error'].get('type')
                    error_message = error_dict['error'].get('message', '')

                    # Check for credit balance error
                    if error_type == 'invalid_request_error' and 'credit balance is too low' in error_message:
                        return cls.ANTHROPIC_ERROR_TYPES['invalid_request_error']['low_credit_balance']
            except (json.JSONDecodeError, ValueError):
                # Not a valid JSON string, continue with normal error handling
                pass

        return cls.ANTHROPIC_ERROR_MESSAGES.get(type(error), (f"{cls.DEFAULT_ANTHROPIC_ERROR_MESSAGE[0]}: {str(error)}",
                                                              cls.DEFAULT_ANTHROPIC_ERROR_MESSAGE[1]))
