# Langfuse Setup Guide

This guide will help you set up Langfuse observability for your Marketing Campaign Orchestrator.

## What is Langfuse?

Langfuse is an open-source LLM observability platform that helps you:
- **Track agent reasoning**: See how your agents think and make decisions
- **Monitor LLM calls**: View all prompts, completions, and token usage
- **Analyze performance**: Measure latency and identify bottlenecks
- **Collect user feedback**: Track approval/revision requests
- **Debug issues**: Replay entire conversation flows

## Prerequisites

- Python environment with the project requirements installed
- Google API key for the LLM

## Step 1: Install Dependencies

First, install the Langfuse packages (already added to `requirements.txt`):

```bash
pip install -r requirements.txt
```

## Step 2: Create Langfuse Account

1. Visit [https://cloud.langfuse.com](https://cloud.langfuse.com)
2. Sign up for a free account
3. Create a new project (e.g., "Marketing Campaign Orchestrator")

## Step 3: Get API Keys

1. In your Langfuse project, navigate to **Settings** → **API Keys**
2. Copy the following credentials:
   - **Public Key** (starts with `pk-lf-...`)
   - **Secret Key** (starts with `sk-lf-...`)

## Step 4: Configure Environment Variables

Create a `.env` file in your project root (or update existing one):

```bash
# Google Gemini API Key (Required)
GOOGLE_API_KEY=your_gemini_api_key_here

# Langfuse Observability
LANGFUSE_PUBLIC_KEY=pk-lf-your_public_key_here
LANGFUSE_SECRET_KEY=sk-lf-your_secret_key_here
LANGFUSE_HOST=https://cloud.langfuse.com
```

> **Note**: The project will work WITHOUT Langfuse credentials, but tracing will be disabled.

## Step 5: Verify Installation

### Option A: Using Streamlit UI

```bash
streamlit run app.py
```

Check the sidebar for:
- ✓ **Langfuse Observability: Enabled** (green) if configured correctly
- **Langfuse Observability: Disabled** (gray) if credentials are missing

### Option B: Using FastAPI Backend

```bash
python backend.py
```

Then make a test request:

```bash
curl -X POST "http://localhost:8000/run_campaign" \
  -H "Content-Type: application/json" \
  -d '{"goal": "Create a social media campaign for product launch"}'
```

Check the response for `langfuse_trace_url` field.

## Step 6: View Traces in Langfuse

1. Run a campaign (via Streamlit or API)
2. Go to [https://cloud.langfuse.com](https://cloud.langfuse.com)
3. Navigate to your project
4. Click **Traces** in the sidebar
5. You should see your campaign execution with:
   - **Trace**: Overall workflow
   - **Generations**: Individual LLM calls
   - **Scores**: User feedback and validation results

## What Gets Tracked?

### 1. Agent Nodes
Every agent node is tracked with:
- **Input**: Goal, current asset, retry count
- **Output**: Generated plans, drafts, critiques
- **Metadata**: Reasoning traces, iteration counts

### 2. LLM Calls
All language model invocations include:
- **Prompt**: Full input prompt
- **Completion**: Model response
- **Token Usage**: Input/output token counts
- **Latency**: Response time

### 3. RAG Operations
Retrieval and grading operations track:
- **Query**: Search query used
- **Document Count**: Number of documents retrieved
- **Relevance Score**: Whether retrieval was relevant

### 4. Guardrails Validations
Content validations track:
- **Status**: Passed/failed
- **Details**: What was modified (if any)
- **Asset Name**: Which content was validated

### 5. User Feedback
Draft approvals and revisions track:
- **Status**: Approved, needs revision, pending
- **Feedback Text**: User's specific feedback
- **Asset Name**: Which draft was reviewed

## Troubleshooting

### Langfuse not initializing

**Symptom**: Warning message "Langfuse is not enabled"

**Solutions**:
1. Verify `.env` file exists and contains the keys
2. Check key format (public key starts with `pk-lf-`, secret with `sk-lf-`)
3. Restart the application after adding environment variables

### No traces appearing in dashboard

**Symptom**: Application runs but no traces in Langfuse

**Solutions**:
1. Check that you're logged into the correct project
2. Verify API keys are from the same project you're viewing
3. Wait a few seconds and refresh the dashboard
4. Check application logs for Langfuse errors

### Import errors

**Symptom**: `ModuleNotFoundError: No module named 'langfuse'`

**Solutions**:
1. Run `pip install langfuse langfuse-langchain`
2. Verify you're in the correct Python environment
3. Check `requirements.txt` includes the Langfuse packages

## Self-Hosted Langfuse (Optional)

If you prefer to self-host Langfuse:

1. Follow the [Langfuse self-hosting guide](https://langfuse.com/docs/deployment/self-host)
2. Update your `.env` file with your self-hosted URL:
   ```bash
   LANGFUSE_HOST=https://your-langfuse-instance.com
   ```

## Next Steps

- **Explore Traces**: Click on individual traces to see the full execution flow
- **Analyze Patterns**: Look for common failure modes or slow operations
- **Set Up Alerts**: Configure alerts for errors or latency spikes (Langfuse Pro)
- **Export Data**: Use Langfuse API to export data for custom analysis

## Support

- **Langfuse Documentation**: [https://langfuse.com/docs](https://langfuse.com/docs)
- **Langfuse Discord**: [https://discord.gg/7NXusRtqYU](https://discord.gg/7NXusRtqYU)
- **Project Issues**: Check your project's GitHub repository
