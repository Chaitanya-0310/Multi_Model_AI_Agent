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

# --- Sidebar ---
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("OpenAI API Key", type="password")
    
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key
    
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

if st.button("🚀 Run Campaign"):
    if not os.environ.get("OPENAI_API_KEY"):
        st.error("Please provide an OpenAI API Key in the sidebar.")
    elif not goal:
        st.error("Please enter a campaign goal.")
    else:
        with st.spinner("Agents are working... (Planning -> Writing -> Reviewing)"):
            try:
                # Initialize Graph
                app = create_graph()
                inputs = {"goal": goal}
                
                # Run Graph
                result = app.invoke(inputs)
                
                # Display Results
                st.success("Campaign Generation Complete!")
                
                # 1. Plan
                st.subheader("1. Strategic Plan")
                plan_steps = result.get('plan', [])
                for i, step in enumerate(plan_steps, 1):
                    st.write(f"**{i}. {step}**")
                
                st.divider()
                
                # 2. Drafts
                st.subheader("2. Content Drafts")
                drafts = result.get('drafts', {})
                
                cols = st.columns(len(drafts) if drafts else 1)
                
                # Handle cases where we have more items than columns gracefully if needed, 
                # but for simplicity iterating normally.
                for asset, content in drafts.items():
                    with st.expander(f"📄 {asset}", expanded=True):
                        st.markdown(content)
                
                st.divider()
                
                # 3. Critique
                st.subheader("3. Brand Compliance Review")
                critique = result.get('critique', "")
                st.info(critique)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
