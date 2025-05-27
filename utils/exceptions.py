from structlog.contextvars import bind_contextvars


class ApplicationException(Exception):
    """Base exception class for all application-specific exceptions."""
    DEFAULT_MESSAGE = "An unexpected error occurred"
    ERROR_CODE = 1000  # Generic client error

    def __init__(self, message: str = None, error_code: int = None):
        self.message = message or self.DEFAULT_MESSAGE
        self.error_code = error_code or self.ERROR_CODE
        super().__init__(self.message)
        bind_contextvars(exception={"error_message": self.message})


class CustomException(Exception):
    DEFAULT_ERROR_MESSAGE = "Exception occurred"

    def __init__(self, error_message: str = None):
        error_message = error_message or self.DEFAULT_ERROR_MESSAGE
        self.error_message = error_message
        super().__init__(self.error_message)
        bind_contextvars(exception={"error_message": self.error_message})


class ApiException(CustomException):
    DEFAULT_ERROR_MESSAGE = "API Exception"


### 1XXX - CLIENT ERRORS (User Input, Config Issues)
class InvalidInputException(ApplicationException):
    DEFAULT_MESSAGE = "The input data provided is invalid."
    ERROR_CODE = 1001


class AgentConfigNotFoundException(ApplicationException):
    DEFAULT_MESSAGE = "Agent configuration missing! Please configure the agent."
    ERROR_CODE = 1002


class CommandNotFoundException(ApplicationException):
    DEFAULT_MESSAGE = "The specified command was not found."
    ERROR_CODE = 1003


### 2XXX - RESOURCE & DATA ISSUES (Documents, Models, Search, APIs)
class DuplicateDocumentException(ApplicationException):
    DEFAULT_MESSAGE = "A document with the same title or URL already exists."
    ERROR_CODE = 2001


class DocumentProcessingException(ApplicationException):
    DEFAULT_MESSAGE = "An error occurred while processing the document."
    ERROR_CODE = 2002


class JiraProcessingException(ApplicationException):
    DEFAULT_MESSAGE = "An error occurred while processing the Jira ticket."
    ERROR_CODE = 2003


class SearchQueryException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to generate a valid search query."
    ERROR_CODE = 2004


class SearchQueryGenerationException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to generate a search query."
    ERROR_CODE = 2005


class SurfaceRequestException(ApplicationException):
    DEFAULT_MESSAGE = "An error occurred while processing the surface request."
    ERROR_CODE = 2006


class LLMNotFoundException(ApplicationException):
    DEFAULT_MESSAGE = "Requested AI model not found in registry!"
    ERROR_CODE = 2007


class ModelFetchException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to fetch models from the registry."
    ERROR_CODE = 2008


class SemanticSearchAPIException(ApplicationException):
    DEFAULT_MESSAGE = "Error calling the semantic search API."
    ERROR_CODE = 2009


class ExecutionException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to execute the plan."
    ERROR_CODE = 3003


class PlanCreationException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to create a plan due to an unexpected error."
    ERROR_CODE = 3004


### 4XXX - SYSTEM & INFRASTRUCTURE ISSUES (Code Gen, Deployment, File Ops)
class FolderStructureException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to create folder structure due to an unexpected error."
    ERROR_CODE = 4001


class CodeGenerationException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to generate code due to an unexpected error."
    ERROR_CODE = 4002


class InputProcessingException(ApplicationException):
    DEFAULT_MESSAGE = "Error processing input data."
    ERROR_CODE = 4003


### 5XXX - EXTERNAL SERVICE FAILURES (API Calls, 3rd Party Integrations)
class BugReportException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to report bug."
    ERROR_CODE = 5001


class URLFetchException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to fetch content from URL"
    ERROR_CODE = 5002


class URLConnectionException(ApplicationException):
    DEFAULT_MESSAGE = "Failed to establish connection to URL"
    ERROR_CODE = 5003


class SessionExpiredException(ApplicationException):
    DEFAULT_MESSAGE = "Session Expired for catalyst"
    ERROR_CODE = 6001
