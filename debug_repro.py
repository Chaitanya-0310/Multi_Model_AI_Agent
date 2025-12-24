
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    from src.agents import create_graph, AgentState
    print("Successfully imported create_graph")
except Exception as e:
    print(f"Failed to import create_graph: {e}")
    sys.exit(1)

print("Attempting to create graph...")
try:
    graph = create_graph()
    print("Graph created successfully")
    
    # Try to invoke planner to see if model name triggers error
    print("Attempting to invoke planner...")
    config = {"configurable": {"thread_id": "1"}}
    
    # We can invoke the planner directly or via graph.
    res = graph.invoke({"goal": "Test Goal"}, config=config)
    print("Graph invoked successfully")
    print(res)

except Exception as e:
    print(f"Error during execution: {e}")
    import traceback
    traceback.print_exc()
