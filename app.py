import streamlit as st
import os
import sys

# Ensure src is in python path
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.rag import ingest_docs
from src.agents import create_graph

st.set_page_config(page_title="Geotab Marketing Campaign Orchestrator", layout="wide")

st.title("🤖 Geotab Marketing Campaign Orchestrator")
st.markdown("""
This agentic workflow takes a high-level campaign goal and:
1. **Plans** the necessary assets.
2. **Drafts** content using RAG (Brand Guidelines & Product Docs).
3. **Reviews** the content for brand compliance.
""")

# --- Session State Management ---
if "graph" not in st.session_state:
    st.session_state.graph = create_graph()
    st.session_state.config = {"configurable": {"thread_id": "1"}}

if "run_stage" not in st.session_state:
    st.session_state.run_stage = "entry"  # entry, review, complete

# --- Sidebar ---
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Google API Key", type="password")
    
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
    
    st.divider()
    if st.button("Re-ingest Knowledge Base"):
        with st.spinner("Ingesting documents..."):
            try:
                ingest_docs()
                st.success("Knowledge Base Updated!")
            except Exception as e:
                st.error(f"Error: {e}")

# --- Main Interface ---
goal = st.text_area("Campaign Goal", height=100, 
                    placeholder="Example: Launch a Q3 awareness campaign for the Geotab GO9 targeting logistics fleet managers focusing on safety.")

def display_results(state_values):
    """Helper to display the current state of the campaign."""
    # 1. Plan
    if 'plan' in state_values:
        st.subheader("1. Strategic Plan")
        for i, step in enumerate(state_values['plan'], 1):
            st.write(f"**{i}. {step}**")
        st.divider()

    # 2. Drafts
    if 'drafts' in state_values:
        st.subheader("2. Content Drafts")
        drafts = state_values['drafts']
        cols = st.columns(len(drafts) if drafts else 1)
        for i, (asset, content) in enumerate(drafts.items()):
            with cols[i]:
                with st.expander(f"📄 {asset}", expanded=True):
                    st.markdown(content)
        st.divider()

    # 3. Critique
    if 'critique' in state_values:
        st.subheader("3. Brand Compliance Review")
        st.info(state_values['critique'])

# --- Main Application Logic ---
if st.session_state.run_stage == "entry":
    if st.button("🚀 Run Campaign"):
        if not os.environ.get("GOOGLE_API_KEY"):
            st.error("Please provide an OpenAI API Key in the sidebar.")
        elif not goal:
            st.error("Please enter a campaign goal.")
        else:
            with st.spinner("Planning & Drafting..."):
                # Run until interruption (before reviewer)
                st.session_state.graph.invoke({"goal": goal}, config=st.session_state.config)
                st.session_state.run_stage = "review"
                st.rerun()

elif st.session_state.run_stage == "review":
    st.warning("⏸️ Approval Required: Review drafts before compliance check.")
    
    # Fetch current state from memory
    current_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(current_values)
    
    if st.button("✅ Approve & Run Compliance Check"):
        with st.spinner("Reviewing for compliance..."):
            # Resume execution (pass None to proceed)
            st.session_state.graph.invoke(None, config=st.session_state.config)
            st.session_state.run_stage = "complete"
            st.rerun()

elif st.session_state.run_stage == "complete":
    st.success("Campaign Generation Complete!")
    
    final_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(final_values)
    
    if st.button("🔄 Start New Campaign"):
        st.session_state.graph = create_graph() # Reset graph and memory
        st.session_state.run_stage = "entry"
        st.rerun()
