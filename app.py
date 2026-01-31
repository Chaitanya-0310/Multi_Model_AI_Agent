import streamlit as st
import os
import sys

# Ensure src is in python path
sys.path.append(os.path.join(os.getcwd(), "src"))

from src.rag import ingest_docs
from src.agents import create_graph

st.set_page_config(page_title="Marketing Campaign Orchestrator", layout="wide")

st.title("🤖 Marketing Campaign Orchestrator")
st.markdown("""
This agentic workflow takes a high-level campaign goal and:
1. **Plans** the necessary assets.
2. **Drafts** content using RAG (Brand Guidelines & Product Docs).
3. **Reviews** the content for brand compliance.
4. **Publishes** to Google Workspace.
""")

# --- Session State Management ---
if "graph" not in st.session_state:
    st.session_state.graph = create_graph()
    st.session_state.config = {"configurable": {"thread_id": "1"}}

if "run_stage" not in st.session_state:
    st.session_state.run_stage = "entry"  # entry, plan_approval, draft_approval, feedback_collection, review_approval, complete

if "draft_feedback" not in st.session_state:
    st.session_state.draft_feedback = {}

if "draft_statuses" not in st.session_state:
    st.session_state.draft_statuses = {}

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
    if 'critique' in state_values and state_values['critique']:
        st.subheader("3. Brand Compliance Review")
        st.info(state_values['critique'])

    # 4. Publish Results
    if 'publish_results' in state_values:
        st.subheader("4. Publishing Results")
        for asset, result in state_values['publish_results'].items():
            st.success(f"**{asset}:** {result}")

    # 5. Reasoning Trace (New)
    if 'reasoning_trace' in state_values:
        with st.expander("🕵️ Agent Thought Process (Reasoning Trace)"):
            st.markdown(state_values['reasoning_trace'])

# --- Main Application Logic ---
if st.session_state.run_stage == "entry":
    if st.button("🚀 Start Campaign"):
        if not os.environ.get("GOOGLE_API_KEY"):
            st.error("Please provide a Google API Key in the sidebar.")
        elif not goal:
            st.error("Please enter a campaign goal.")
        else:
            with st.spinner("Analyzing Goal & Planning..."):
                # Run until interruption (before retriever)
                st.session_state.graph.invoke({"goal": goal}, config=st.session_state.config)
                st.session_state.run_stage = "plan_approval"
                st.rerun()

elif st.session_state.run_stage == "plan_approval":
    st.warning("⏸️ Step 1: Approve Strategic Plan")
    current_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(current_values)
    
    if st.button("✅ Approve Plan & Start Drafting"):
        with st.spinner("Drafting content..."):
            # Resume until next interruption (before reviewer)
            st.session_state.graph.invoke(None, config=st.session_state.config)
            st.session_state.run_stage = "draft_approval"
            st.rerun()

elif st.session_state.run_stage == "draft_approval":
    st.warning("⏸️ Step 2: Review Content Drafts")
    current_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(current_values)
    
    if st.button("✅ Continue to Detailed Review"):
        st.session_state.run_stage = "feedback_collection"
        st.rerun()

elif st.session_state.run_stage == "feedback_collection":
    st.warning("⏸️ Step 3: Provide Feedback on Drafts")
    current_values = st.session_state.graph.get_state(st.session_state.config).values
    drafts = current_values.get('drafts', {})
    
    st.subheader("📝 Review Each Draft")
    st.markdown("Please review each draft and either approve it or request revisions with specific feedback.")
    
    # Display feedback interface for each draft
    for asset_name, content in drafts.items():
        with st.expander(f"📄 {asset_name}", expanded=True):
            st.markdown(content)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                feedback_key = f"feedback_{asset_name}"
                st.session_state.draft_feedback[asset_name] = st.text_area(
                    f"Feedback for {asset_name}",
                    value=st.session_state.draft_feedback.get(asset_name, ""),
                    placeholder="Provide specific feedback if requesting revisions (e.g., 'Make it more professional', 'Add statistics', etc.)",
                    height=100,
                    key=feedback_key
                )
            
            with col2:
                status_key = f"status_{asset_name}"
                current_status = st.session_state.draft_statuses.get(asset_name, "pending")
                
                st.markdown(f"**Status:** `{current_status}`")
                
                if st.button(f"✅ Approve", key=f"approve_{asset_name}"):
                    st.session_state.draft_statuses[asset_name] = "approved"
                    st.rerun()
                
                if st.button(f"🔄 Request Revision", key=f"revise_{asset_name}"):
                    if st.session_state.draft_feedback.get(asset_name, "").strip():
                        st.session_state.draft_statuses[asset_name] = "needs_revision"
                        st.rerun()
                    else:
                        st.error("Please provide feedback before requesting revision.")
    
    st.divider()
    
    # Show summary of statuses
    status_summary = {}
    for asset in drafts.keys():
        status = st.session_state.draft_statuses.get(asset, "pending")
        status_summary[status] = status_summary.get(status, 0) + 1
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ Approved", status_summary.get("approved", 0))
    with col2:
        st.metric("🔄 Needs Revision", status_summary.get("needs_revision", 0))
    with col3:
        st.metric("⏳ Pending", status_summary.get("pending", len(drafts)))
    
    # Bulk actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Approve All Drafts"):
            for asset in drafts.keys():
                st.session_state.draft_statuses[asset] = "approved"
            st.rerun()
    
    # Submit feedback button
    if st.button("🚀 Submit Feedback & Continue", type="primary"):
        # Check if all drafts have been reviewed
        all_reviewed = all(
            st.session_state.draft_statuses.get(asset, "pending") != "pending" 
            for asset in drafts.keys()
        )
        
        if not all_reviewed:
            st.error("Please review all drafts (approve or request revision) before continuing.")
        else:
            # Update graph state with feedback
            needs_revision = any(
                st.session_state.draft_statuses.get(asset) == "needs_revision" 
                for asset in drafts.keys()
            )
            
            with st.spinner("Processing feedback..."):
                # Inject feedback into graph state
                st.session_state.graph.update_state(
                    st.session_state.config,
                    {
                        "user_feedback": st.session_state.draft_feedback,
                        "draft_status": st.session_state.draft_statuses
                    }
                )
                
                # Resume graph execution (will hit feedback_processor)
                st.session_state.graph.invoke(None, config=st.session_state.config)
                
                if needs_revision:
                    # Reset for next iteration
                    st.session_state.draft_feedback = {}
                    st.session_state.draft_statuses = {}
                    st.info("Regenerating drafts based on your feedback...")
                    # Stay in feedback_collection to review regenerated drafts
                    st.session_state.run_stage = "feedback_collection"
                else:
                    # All approved, move to review
                    st.session_state.run_stage = "review_approval"
                
                st.rerun()

elif st.session_state.run_stage == "review_approval":
    st.warning("⏸️ Step 4: Final Review before Publishing")
    current_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(current_values)
    
    if st.button("🚀 Approve & Publish to Google Workspace"):
        with st.spinner("Publishing to Google Docs & Calendar..."):
            # Resume until end
            st.session_state.graph.invoke(None, config=st.session_state.config)
            st.session_state.run_stage = "complete"
            st.rerun()

elif st.session_state.run_stage == "complete":
    st.success("Campaign Generation & Publishing Complete!")
    
    final_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(final_values)
    
    if st.button("🔄 Start New Campaign"):
        st.session_state.graph = create_graph() # Reset graph and memory
        st.session_state.run_stage = "entry"
        st.session_state.draft_feedback = {}
        st.session_state.draft_statuses = {}
        st.rerun()
