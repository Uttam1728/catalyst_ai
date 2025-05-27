from typing import List, Optional, Union

from pydantic import BaseModel, Field


class CodeReference(BaseModel):
    content: Optional[str] = Field(None, description="Selected code content")
    fullContent: Optional[str] = Field(None, description="Full file reference content")
    language: Optional[str] = Field(None, description="Programming language")

    def extract_content(self, field_description: str) -> str:
        """Extract formatted content from CodeReference."""
        if not self.content or not self.content.strip():
            return ""

        if not self.fullContent or not self.fullContent.strip():
            return ""

        if not self.language or not self.language.strip():
            self.language = "Language: Not specified"

        return (
            f"**{field_description}**: {self.content}\n"
            "~~~\n"
            f"**File content reference ({self.language})**: {self.fullContent}\n"
            "~~~\n"
        )


class FileReference(BaseModel):
    name: Optional[str] = None
    fileContent: Optional[str] = None
    code: Optional[str] = None
    gitContent: Optional[str] = None
    content: Optional[str] = None

    def extract_content(self) -> str:
        """Extract formatted content from FileReference."""
        content = ""
        if self.name:
            content += f"**Name: {self.name}**\n"

        content_value = self.fileContent or self.code or self.gitContent or self.content
        if content_value:
            content += f"**Content:**\n{content_value}\n"

        return content


class ReferencesSchema(BaseModel):
    query: Optional[str] = Field(None, description="User's query")
    selectedCode: Optional[Union[str, CodeReference]] = Field(None, description="Selected code snippet")
    replyingToCode: Optional[Union[str, CodeReference]] = Field(None,
                                                                description="Code snippet the user is replying to")
    replyingToPara: Optional[str] = Field(None, description="Paragraph the user is replying to")
    extraContent: Optional[str] = Field(None, description="Additional contextual content")
    files: Optional[List[FileReference]] = Field(None, description="List of relevant files")
    folders: Optional[List[FileReference]] = Field(None, description="List of relevant folders")
    git: Optional[List[FileReference]] = Field(None, description="Git-related information")
    functions: Optional[List[FileReference]] = Field(None, description="List of relevant functions")
    questionDOM: Optional[str] = Field(None)
    graph_id: Optional[str] = Field(None)

    def extract_content(self) -> str:
        """
        Extract formatted content from the references data using model_fields in Pydantic v2.
        """
        content = ""

        # Skip these fields
        skip_fields = {'questionDOM', 'graph_id'}

        for field_name, field in self.model_fields.items():
            if field_name in skip_fields:
                continue

            value = getattr(self, field_name)
            if value is None:
                continue

            description = field.description

            # Handle string values
            if isinstance(value, str) and value.strip():
                content += f"**{description}**: {value}\n~~~\n"

            # Handle CodeReference and Union[str, CodeReference]
            elif isinstance(value, CodeReference):
                content += value.extract_content(description)

            # Handle list of FileReference objects
            elif isinstance(value, list) and all(isinstance(v, FileReference) for v in value):
                content += f"**Section: {description}**\n"
                for item in value:
                    content += item.extract_content()
                content += "~~~\n"

        return content
