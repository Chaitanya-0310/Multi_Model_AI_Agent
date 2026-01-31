from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import sys

# Add src to python path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.agents import create_graph

app = FastAPI(title="Geotab Marketing Campaign Orchestrator API")

class CampaignRequest(BaseModel):
    goal: str
    api_key: Optional[str] = None

class CampaignResponse(BaseModel):
    plan: Optional[List[str]] = None
    drafts: Optional[Dict[str, str]] = None
    critique: Optional[str] = None
    reasoning_trace: Optional[str] = None

@app.get("/")
def read_root():
    return {"message": "Welcome to the Geotab Marketing Campaign Orchestrator API"}

@app.post("/run_campaign", response_model=CampaignResponse)
async def run_campaign(request: CampaignRequest, x_api_key: Optional[str] = Header(None)):
    
    # 1. Authentication
    api_key = request.api_key or x_api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=401, detail="Google API Key is required. Provide it in the request body, header (X-API-Key), or environment variable.")
    
    # Set the environment variable for the agent to use
    os.environ["GOOGLE_API_KEY"] = api_key

    # 2. Run the Graph
    try:
        graph = create_graph()
        config = {"configurable": {"thread_id": "api_request"}}
        
        # We invoke the graph. 
        # Note: The graph is designed to stop at 'reviewer'. 
        # For a one-shot API, we might want to run it all the way or handle the interruption.
        # For this v1, we will run it and if it stops, we resume it immediately or just return the state.
        
        # Initial run (Planner -> Writer -> Reviewer(stop))
        # The create_graph() in agents.py sends interrupt_before=["reviewer"]
        
        # First invocation
        initial_state = graph.invoke({"goal": request.goal}, config=config)
        
        # To make it fully autonomous for the API, we can resume execution to run the reviewer
        # If the state has 'critique', it means it finished. 
        # If it paused at reviewer, we should resume.
        
        # Let's inspect the graph state to see if we need to resume.
        # However, simplicity: The current graph stops BEFORE reviewer.
        # If we want the critique, we need to invoke it again with None.
        
        final_state = graph.invoke(None, config=config) # Resume to run Reviewer
        
        return CampaignResponse(
            plan=final_state.get("plan"),
            drafts=final_state.get("drafts"),
            critique=final_state.get("critique"),
            reasoning_trace=final_state.get("reasoning_trace")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
