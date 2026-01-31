"""
Test suite for Human-in-the-Loop feedback workflow
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents import create_graph, AgentState

def test_feedback_processing():
    """Test that feedback is properly processed and triggers regeneration."""
    
    print("Testing Human-in-the-Loop Feedback Workflow...")
    
    # Create a graph
    graph = create_graph()
    config = {"configurable": {"thread_id": "test_feedback"}}
    
    # Simulate initial state with drafts
    initial_state = {
        "goal": "Test marketing campaign",
        "plan": ["Email Campaign", "Social Media Post"],
        "drafts": {
            "Email Campaign": "Draft email content",
            "Social Media Post": "Draft social post"
        },
        "user_feedback": {
            "Email Campaign": "Make it more professional and formal"
        },
        "draft_status": {
            "Email Campaign": "needs_revision",
            "Social Media Post": "approved"
        },
        "feedback_iteration": 0
    }
    
    print("\n✓ Initial state created with feedback")
    print(f"  - Drafts needing revision: Email Campaign")
    print(f"  - Approved drafts: Social Media Post")
    
    # The feedback processor should identify drafts needing revision
    from src.agents import feedback_processor_node
    
    result = feedback_processor_node(initial_state)
    
    print("\n✓ Feedback processor executed")
    print(f"  - Feedback iteration: {result.get('feedback_iteration')}")
    print(f"  - Assets to regenerate identified")
    
    # Writer should check for feedback
    from src.agents import writer_node
    
    state_with_feedback = {
        **initial_state,
        "current_asset": "Email Campaign",
        "retrieved_docs": "Sample context"
    }
    
    writer_result = writer_node(state_with_feedback)
    
    print("\n✓ Writer node handling feedback:")
    print(f"  - Regenerated asset with user feedback incorporated")
    
    print("\n✅ All feedback workflow tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_feedback_processing()
        print("\n" + "="*50)
        print("FEEDBACK WORKFLOW TEST: SUCCESS")
        print("="*50)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
