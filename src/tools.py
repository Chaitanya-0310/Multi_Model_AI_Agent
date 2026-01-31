# src/tools.py
from typing import Type, List
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from src.rag import retrieve_context
from src.config import RETRIEVER_TOOL_DESCRIPTION
from src.google_utils import create_doc, add_calendar_event

class RetrieverInput(BaseModel):
    """Input for the retriever tool."""
    query: str = Field(description="The search query to look up in the knowledge base.")

class RetrieverTool(BaseTool):
    name: str = "knowledge_base_retriever"
    description: str = RETRIEVER_TOOL_DESCRIPTION
    args_schema: Type[BaseModel] = RetrieverInput

    def _run(self, query: str) -> str:
        """Use the tool."""
        try:
            context = retrieve_context(query)
            if not context or context.strip() == "No knowledge base found. Please run ingestion.":
                return "Error: The knowledge base is empty or not found. Please ensure documents are ingested before searching."
            return context
        except Exception as e:
            return f"Error: An unexpected error occurred while retrieving context: {str(e)}. Please try a different query or check the system status."

    async def _arun(self, query: str) -> str:
        """Use the tool asynchronously."""
        # For simplicity, we'll just call the synchronous version
        return self._run(query)

class GoogleDocInput(BaseModel):
    """Input for Google Doc creation."""
    title: str = Field(description="The title of the document.")
    content: str = Field(description="The content to be written in the document.")

class GoogleDocTool(BaseTool):
    name: str = "google_doc_creator"
    description: str = "Use this tool to create a Google Doc with the specified title and content."
    args_schema: Type[BaseModel] = GoogleDocInput

    def _run(self, title: str, content: str) -> str:
        try:
            doc_id, url = create_doc(title, content)
            return f"Successfully created document. ID: {doc_id}, URL: {url}"
        except Exception as e:
            return f"Error creating Google Doc: {str(e)}"

class GoogleCalendarInput(BaseModel):
    """Input for Google Calendar event creation."""
    summary: str = Field(description="The summary/title of the event.")
    start_time: str = Field(description="The start time of the event in ISO format (e.g., 2023-12-25T09:00:00Z).")
    description: str = Field(default="", description="The description of the event.")

class GoogleCalendarTool(BaseTool):
    name: str = "google_calendar_scheduler"
    description: str = "Use this tool to schedule a publishing date in Google Calendar."
    args_schema: Type[BaseModel] = GoogleCalendarInput

    def _run(self, summary: str, start_time: str, description: str = "") -> str:
        try:
            event_id = add_calendar_event(summary, start_time, description)
            return f"Successfully scheduled event. ID: {event_id}"
        except Exception as e:
            return f"Error scheduling event: {str(e)}"

def get_tools() -> List[BaseTool]:
    """Returns a list of available tools."""
    return [RetrieverTool(), GoogleDocTool(), GoogleCalendarTool()]
