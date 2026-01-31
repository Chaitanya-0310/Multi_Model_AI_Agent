import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add src to python path
sys.path.append(os.path.join(os.getcwd()))

from src.tools import GoogleDocTool, GoogleCalendarTool
from src.agents import create_graph

class TestNewFeatures(unittest.TestCase):
    def test_google_doc_tool(self):
        tool = GoogleDocTool()
        with patch('src.tools.create_doc') as mock_create:
            mock_create.return_value = ("mock_id", "mock_url")
            result = tool._run("test title", "test content")
            self.assertIn("Successfully created document", result)
            self.assertIn("mock_id", result)
            self.assertIn("mock_url", result)

    def test_google_calendar_tool(self):
        tool = GoogleCalendarTool()
        with patch('src.tools.add_calendar_event') as mock_add:
            mock_add.return_value = "mock_event_id"
            result = tool._run("test event", "2023-12-25T09:00:00Z")
            self.assertIn("Successfully scheduled event", result)
            self.assertIn("mock_event_id", result)

    def test_graph_structure(self):
        graph = create_graph()
        # Verify nodes exist
        nodes = graph.nodes
        self.assertIn("publisher", nodes)
        self.assertIn("router", nodes)
        self.assertIn("planner", nodes)
        
    def test_guardrails_import(self):
        # Just check if we can import guardrails without error
        try:
            import guardrails as gd
            self.assertTrue(True)
        except ImportError:
            self.fail("guardrails-ai not installed")

if __name__ == '__main__':
    unittest.main()
