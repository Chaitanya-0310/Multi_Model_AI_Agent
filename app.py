import streamlit as st
import os
import sys
import uuid
import datetime

sys.path.append(os.path.join(os.getcwd(), "src"))

from src.rag import ingest_docs
from src.agents import create_graph
from src.langfuse_integration import get_langfuse_client, is_langfuse_enabled

st.set_page_config(page_title="AI Campaign Orchestrator", layout="wide", initial_sidebar_state="expanded")

# ─── Quick Templates ──────────────────────────────────────────────────────────

TEMPLATES = {
    "💰 Wealthsimple Invest": {
        "product": "Wealthsimple Invest",
        "audience": "first-time investors and Canadians aged 25–40 who want hands-off portfolio management",
        "objective": "Brand Awareness",
        "key_message": "Start investing in a diversified portfolio in minutes — no financial expertise required, TFSA and RRSP accounts available, 0.5% annual fee",
        "channels": ["Email", "Social Media", "Blog Post", "LinkedIn"],
        "timeline": "Q1 2026",
    },
    "📈 Wealthsimple Trade": {
        "product": "Wealthsimple Trade",
        "audience": "self-directed investors and millennial Canadians switching from bank brokerages",
        "objective": "Lead Generation",
        "key_message": "Trade stocks and ETFs commission-free on TSX, NYSE, and NASDAQ — TFSA, RRSP, and FHSA accounts supported",
        "channels": ["Email", "Blog Post", "Paid Ads", "Social Media"],
        "timeline": "Q2 2026",
    },
    "🏦 Wealthsimple Cash": {
        "product": "Wealthsimple Cash",
        "audience": "everyday Canadians looking for a high-interest savings account with no monthly fees",
        "objective": "Customer Acquisition",
        "key_message": "Earn 4.5% interest on your savings with no minimum balance, no hidden fees, and instant e-Transfers",
        "channels": ["Social Media", "Email", "Paid Ads"],
        "timeline": "Q2 2026",
    },
    "🇨🇦 Tax Season Campaign": {
        "product": "Wealthsimple Tax",
        "audience": "Canadians filing personal tax returns, especially first-time filers and RRSP/TFSA contributors",
        "objective": "Seasonal Campaign",
        "key_message": "File your Canadian taxes free in under an hour — auto-fill from CRA, NETFILE certified, pay what you want",
        "channels": ["Email", "Social Media", "Blog Post", "Press Release"],
        "timeline": "February–April 2026 (Tax Season)",
    },
}

OBJECTIVES = [
    "Brand Awareness",
    "Product Launch",
    "Lead Generation",
    "Customer Retention",
    "Event Promotion",
    "Seasonal Campaign",
]

ALL_CHANNELS = [
    "Email", "Blog Post", "Social Media", "LinkedIn",
    "Video", "Press Release", "Paid Ads", "Influencer",
]


# ─── Session State ────────────────────────────────────────────────────────────

if "graph" not in st.session_state:
    st.session_state.graph = create_graph()
    st.session_state.config = {"configurable": {"thread_id": str(uuid.uuid4())}}

if "run_stage" not in st.session_state:
    st.session_state.run_stage = "entry"

if "draft_feedback" not in st.session_state:
    st.session_state.draft_feedback = {}

if "draft_statuses" not in st.session_state:
    st.session_state.draft_statuses = {}

if "langfuse_trace_id" not in st.session_state:
    st.session_state.langfuse_trace_id = None

if "langfuse_trace_url" not in st.session_state:
    st.session_state.langfuse_trace_url = None

if "audit_log" not in st.session_state:
    st.session_state.audit_log = []

if "compliance_acknowledged" not in st.session_state:
    st.session_state.compliance_acknowledged = {}

# Goal Builder state — persists across reruns so templates can pre-fill fields
if "gb" not in st.session_state:
    st.session_state.gb = {
        "product": "",
        "audience": "",
        "objective": "Brand Awareness",
        "key_message": "",
        "channels": [],
        "timeline": "",
        "mode": "builder",   # "builder" | "freetext"
        "freetext": "",
    }


def log_audit(stage: str, decision: str, details: str = ""):
    st.session_state.audit_log.append({
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "stage": stage,
        "decision": decision,
        "details": details,
    })


# ─── Progress Tracker ─────────────────────────────────────────────────────────

STAGE_ORDER = [
    ("entry",            "1. Define Goal"),
    ("plan_approval",    "2. Approve Plan"),
    ("draft_approval",   "3. Review Drafts"),
    ("feedback_collection", "3. Review Drafts"),
    ("review_approval",  "4. Authorize Publish"),
    ("complete",         "5. Complete"),
]

STAGE_INDEX = {
    "entry": 0,
    "plan_approval": 1,
    "draft_approval": 2,
    "feedback_collection": 2,
    "review_approval": 3,
    "complete": 4,
}

UNIQUE_STAGES = [
    ("entry",           "1. Define Goal"),
    ("plan_approval",   "2. Approve Plan"),
    ("draft_approval",  "3. Review Drafts"),
    ("review_approval", "4. Authorize Publish"),
    ("complete",        "5. Complete"),
]


def show_progress():
    current_idx = STAGE_INDEX.get(st.session_state.run_stage, 0)
    cols = st.columns(len(UNIQUE_STAGES))
    for i, (col, (_, label)) in enumerate(zip(cols, UNIQUE_STAGES)):
        with col:
            if i < current_idx:
                st.markdown(f"<div style='text-align:center; color:#28a745; font-size:0.85rem'>✅ {label}</div>", unsafe_allow_html=True)
            elif i == current_idx:
                st.markdown(f"<div style='text-align:center; color:#007bff; font-weight:bold; font-size:0.85rem'>🔵 {label}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center; color:#aaa; font-size:0.85rem'>⬜ {label}</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:8px 0 18px 0'>", unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🤖 AI Campaign Orchestrator")
    st.caption("Replacing a 2-week, 5-person workflow with AI-native orchestration.")
    st.divider()

    st.header("Configuration")

    _provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
    if _provider == "groq":
        _model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        st.success(f"🟢 LLM: Groq · {_model}")
        groq_key = st.text_input("Groq API Key", type="password")
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
    else:
        st.info("🔵 LLM: Google Gemini 2.5 Flash")
        api_key = st.text_input("Google API Key", type="password")
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key

    st.divider()
    if st.button("🔄 Re-ingest Knowledge Base"):
        with st.spinner("Ingesting documents..."):
            try:
                ingest_docs()
                st.success("Knowledge Base Updated!")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    if is_langfuse_enabled():
        st.success("✓ Langfuse: Enabled")
        if st.session_state.langfuse_trace_url:
            st.markdown(f"[View Trace ↗]({st.session_state.langfuse_trace_url})")
    else:
        st.info("Langfuse: Disabled")

    st.divider()
    st.markdown("**📄 Google Docs Publishing**")
    try:
        from src.google_utils import get_publish_status
        pub_status = get_publish_status()
        if pub_status["mcp_available"]:
            st.success("✓ MCP + Direct API ready")
        elif pub_status["api_available"]:
            st.warning("⚠ Direct API only (MCP not configured)")
        else:
            st.error("✗ No credentials — will use mock URLs")
            with st.expander("How to enable real publishing"):
                st.markdown("""
**Option A — OAuth (recommended):**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create an OAuth 2.0 Desktop App credential
3. Add `GDRIVE_CLIENT_ID` and `GDRIVE_CLIENT_SECRET` to your `.env` file
4. Run the app — you'll be prompted to authenticate once

**Option B — Service Account:**
- Set `GOOGLE_SERVICE_ACCOUNT_INFO` env var with your service account JSON

**Option C — credentials.json:**
- Place `credentials.json` in the project root
                """)
    except Exception:
        st.info("Publishing status unavailable")

    # ── Audit Trail ───────────────────────────────────────────────────────────
    if st.session_state.audit_log:
        st.divider()
        st.subheader("📋 Human Decision Audit Trail")
        st.caption("Every decision that must remain human-owned:")
        for entry in st.session_state.audit_log:
            icon = "✅" if "approved" in entry["decision"].lower() else "🔄" if "revision" in entry["decision"].lower() else "📤"
            st.markdown(f"**{entry['time']}** {icon} `{entry['stage']}`")
            st.markdown(f"&nbsp;&nbsp;→ {entry['decision']}")
            if entry["details"]:
                st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;{entry['details']}")


# ─── Header ───────────────────────────────────────────────────────────────────

st.title("🤖 AI Campaign Orchestrator")

with st.expander("ℹ️ How this works", expanded=False):
    st.markdown("""
**Replacing a 2-week, 5-person workflow with AI-native orchestration.**

| Before | After |
|---|---|
| Campaign manager, copywriter, brand reviewer, compliance officer | You (Campaign Director) + AI |
| 2 weeks, 5 stakeholder meetings | ~20 minutes, 3 human decisions |
| Email chains, revision loops | Automated grading + one-click feedback |

**Your 3 decisions as Campaign Director:**
1. ✅ Approve the strategic plan
2. ✅ Approve (or revise) each content draft
3. ✅ **Authorize final publishing** ← *This must stay human: legal & reputational risk cannot be delegated to AI*
    """)

show_progress()


# ─── Helpers shared across stages ────────────────────────────────────────────

def _confidence_badge(score: float) -> str:
    if score >= 0.85:
        return "🟢 High"
    elif score >= 0.5:
        return "🟡 Medium"
    return "🔴 Low"


def compose_goal(gb: dict) -> str:
    """Auto-assemble a structured goal string from builder fields."""
    product = gb.get("product", "").strip()
    audience = gb.get("audience", "").strip()
    objective = gb.get("objective", "Brand Awareness")
    key_message = gb.get("key_message", "").strip()
    channels = gb.get("channels", [])
    timeline = gb.get("timeline", "").strip()

    if not product:
        return ""

    goal = f"Launch a {objective.lower()} campaign for {product}"
    if audience:
        goal += f", targeting {audience}"
    if timeline:
        goal += f", during {timeline}"
    goal += "."
    if key_message:
        goal += f" Key message: {key_message}."
    if channels:
        goal += f" Channels: {', '.join(channels)}."
    return goal


def goal_quality(gb: dict) -> tuple[int, list[str]]:
    """Return (score 0-100, list of missing items)."""
    missing = []
    score = 0
    if gb.get("product", "").strip():
        score += 25
    else:
        missing.append("Product / Service name")
    if gb.get("audience", "").strip():
        score += 25
    else:
        missing.append("Target audience")
    if gb.get("key_message", "").strip():
        score += 25
    else:
        missing.append("Key message")
    if gb.get("channels"):
        score += 15
    else:
        missing.append("At least one channel")
    if gb.get("timeline", "").strip():
        score += 10
    return score, missing


def generate_campaign_markdown(state_values: dict) -> str:
    goal = state_values.get("goal", "Campaign")
    plan = state_values.get("plan", [])
    drafts = state_values.get("drafts", {})
    critique = state_values.get("critique", "")
    confidence_scores = state_values.get("confidence_scores") or {}
    publish_results = state_values.get("publish_results", {})

    lines = [
        "# Marketing Campaign Brief", "",
        f"**Goal:** {goal}",
        f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
        "---", "", "## Strategic Plan", "",
    ]
    for i, step in enumerate(plan, 1):
        lines.append(f"{i}. {step}")

    lines += ["", "---", "", "## Content Drafts", ""]
    for asset, content in drafts.items():
        score = confidence_scores.get(asset)
        badge = f" · Confidence: {_confidence_badge(score)} ({score*100:.0f}%)" if score is not None else ""
        lines += [f"### {asset}{badge}", "", content, "", "---", ""]

    if critique:
        lines += ["## Brand Compliance Review", "", critique, "", "---", ""]

    if publish_results:
        lines += ["## Publishing Results", ""]
        for asset, result in publish_results.items():
            lines.append(f"- **{asset}:** {result}")
        lines += ["", "---", ""]

    if st.session_state.audit_log:
        lines += ["## Human Decision Audit Trail", ""]
        for entry in st.session_state.audit_log:
            lines.append(f"- `{entry['time']}` **{entry['stage']}** — {entry['decision']}")
            if entry["details"]:
                lines.append(f"  - {entry['details']}")

    return "\n".join(lines)


def display_results(state_values: dict):
    """Render current campaign state with confidence badges and readiness score."""
    confidence_scores = state_values.get("confidence_scores") or {}

    if confidence_scores:
        avg_score = sum(confidence_scores.values()) / len(confidence_scores)
        c1, c2, _ = st.columns([1, 1, 3])
        c1.metric("Campaign Readiness Score", f"{avg_score*100:.0f}%",
                  help="Average AI confidence: retrieval relevance × hallucination grading")
        c2.metric("Assets Graded", len(confidence_scores))
        st.divider()

    if state_values.get("plan"):
        st.subheader("1. Strategic Plan")
        plan_cols = st.columns(min(len(state_values["plan"]), 3))
        for i, step in enumerate(state_values["plan"]):
            with plan_cols[i % len(plan_cols)]:
                st.info(f"**{i+1}.** {step}")
        st.divider()

    if state_values.get("drafts"):
        st.subheader("2. Content Drafts")
        drafts = state_values["drafts"]
        draft_variants = state_values.get("draft_variants") or {}
        for asset, content in drafts.items():
            score = confidence_scores.get(asset)
            badge = f"  {_confidence_badge(score)} ({score*100:.0f}%)" if score is not None else ""
            with st.expander(f"📄 {asset}{badge}", expanded=True):
                show_draft_with_variants(asset, content, draft_variants.get(asset, ""))
        st.divider()

    if state_values.get("critique"):
        st.subheader("3. Brand Compliance Review")
        st.info(state_values["critique"])

    if state_values.get("publish_results"):
        st.subheader("4. Publishing Results")
        for asset, result in state_values["publish_results"].items():
            st.success(f"**{asset}:** {result}")

    if state_values.get("reasoning_trace"):
        with st.expander("🕵️ Agent Reasoning Trace"):
            st.markdown(state_values["reasoning_trace"])


def show_kpi_table(performance_estimates: dict):
    """Render the projected performance benchmark table below the plan cards."""
    if not performance_estimates:
        return
    import pandas as pd

    st.markdown("#### 📊 Projected Performance Benchmarks")
    st.caption("Industry benchmarks for each planned asset. Individual results may vary.")

    rows = []
    for asset, metrics in performance_estimates.items():
        if not metrics:
            continue
        source = metrics.pop("Source", "Industry benchmarks")
        for metric, value in metrics.items():
            rows.append({"Asset": asset, "Metric": metric, "Benchmark": value})
        metrics["Source"] = source  # restore for later use

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Performance estimates not yet available.")


def _compliance_badge_html(summary: str) -> str:
    if summary == "PASS":
        return "✅ **PASS**"
    elif summary == "WARN":
        return "⚠️ **WARN**"
    return "🚫 **BLOCK**"


def show_compliance_gate(asset: str, flags: list, summary: str) -> bool:
    """
    Renders compliance flags for a single asset.
    Returns True if the asset is cleared for approval (no unacknowledged HIGH flags).
    """
    badge = _compliance_badge_html(summary)
    st.markdown(f"**Compliance:** {badge}", unsafe_allow_html=False)

    high_flags = [f for f in flags if f["severity"] == "HIGH"]
    medium_flags = [f for f in flags if f["severity"] == "MEDIUM"]
    low_flags = [f for f in flags if f["severity"] == "LOW"]

    if high_flags:
        for flag in high_flags:
            st.error(f"🚫 **HIGH:** {flag['issue']}\n\n💡 *Fix:* {flag['suggestion']}")

    if medium_flags:
        with st.expander(f"⚠️ {len(medium_flags)} medium-severity flag(s)"):
            for flag in medium_flags:
                st.warning(f"**{flag['issue']}**\n\n💡 *Fix:* {flag['suggestion']}")

    if low_flags:
        with st.expander(f"ℹ️ {len(low_flags)} low-severity note(s)"):
            for flag in low_flags:
                st.info(f"**{flag['issue']}**\n\n💡 *Fix:* {flag['suggestion']}")

    if not flags:
        st.success("All compliance checks passed.")
        return True

    if high_flags:
        ack_key = f"ack_{asset}"
        acknowledged = st.checkbox(
            f"I have reviewed the HIGH severity flag(s) above and acknowledge the risk for **{asset}**",
            key=ack_key,
            value=st.session_state.compliance_acknowledged.get(asset, False),
        )
        st.session_state.compliance_acknowledged[asset] = acknowledged
        return acknowledged

    return True  # WARN/LOW only — cleared


def show_draft_with_variants(asset: str, primary_content: str, variant_content: str):
    """Render a draft with Primary / Variant tabs."""
    tab_primary, tab_variant = st.tabs(["🎯 Primary Audience", "👥 Variant Segment"])
    with tab_primary:
        st.markdown(primary_content)
    with tab_variant:
        if variant_content:
            st.markdown(variant_content)
        else:
            st.info("Variant draft not yet generated for this asset.")


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: entry — Goal Builder
# ═════════════════════════════════════════════════════════════════════════════

if st.session_state.run_stage == "entry":

    st.subheader("🎯 Define Your Campaign Goal")

    # ── Quick Templates ───────────────────────────────────────────────────────
    st.markdown("**Quick Start — pick a template:**")
    tcols = st.columns(len(TEMPLATES))
    for col, (label, values) in zip(tcols, TEMPLATES.items()):
        with col:
            if st.button(label, use_container_width=True):
                for k, v in values.items():
                    st.session_state.gb[k] = v
                st.rerun()

    st.divider()

    # ── Mode Toggle ───────────────────────────────────────────────────────────
    mode = st.radio(
        "Input mode",
        ["🔧 Goal Builder (Guided)", "✏️ Free Text (Advanced)"],
        horizontal=True,
        index=0 if st.session_state.gb["mode"] == "builder" else 1,
        label_visibility="collapsed",
    )
    st.session_state.gb["mode"] = "builder" if "Builder" in mode else "freetext"

    st.markdown("")

    # ── Builder Mode ──────────────────────────────────────────────────────────
    if st.session_state.gb["mode"] == "builder":

        col_left, col_right = st.columns(2, gap="large")

        with col_left:
            st.markdown("##### Core Details")
            st.session_state.gb["product"] = st.text_input(
                "🏷️ Product / Service",
                value=st.session_state.gb["product"],
                placeholder="e.g., Geotab GO9, Acme SaaS Platform",
                help="The product or brand you are promoting.",
            )
            st.session_state.gb["audience"] = st.text_input(
                "👥 Target Audience",
                value=st.session_state.gb["audience"],
                placeholder="e.g., logistics fleet managers, B2B procurement leads",
                help="Who this campaign is aimed at.",
            )
            st.session_state.gb["objective"] = st.selectbox(
                "🎯 Campaign Objective",
                OBJECTIVES,
                index=OBJECTIVES.index(st.session_state.gb["objective"])
                if st.session_state.gb["objective"] in OBJECTIVES else 0,
                help="The primary business goal of this campaign.",
            )
            st.session_state.gb["timeline"] = st.text_input(
                "📅 Timeline",
                value=st.session_state.gb["timeline"],
                placeholder="e.g., Q3 2025, Holiday Season, October launch",
                help="When this campaign should run.",
            )

        with col_right:
            st.markdown("##### Message & Channels")
            st.session_state.gb["key_message"] = st.text_area(
                "💬 Key Message / USP",
                value=st.session_state.gb["key_message"],
                placeholder="e.g., Cut fuel costs by 15% with real-time vehicle tracking",
                height=108,
                help="The core value proposition or single most important message.",
            )
            st.session_state.gb["channels"] = st.multiselect(
                "📡 Marketing Channels",
                ALL_CHANNELS,
                default=st.session_state.gb["channels"],
                help="Select all channels this campaign will use.",
            )

        # ── Goal Quality Meter ────────────────────────────────────────────────
        score, missing = goal_quality(st.session_state.gb)
        st.markdown("")
        q_col1, q_col2 = st.columns([3, 2])
        with q_col1:
            if score == 100:
                st.success(f"✅ Goal Quality: **{score}% — Excellent!** Ready to launch.")
            elif score >= 75:
                st.warning(f"🟡 Goal Quality: **{score}% — Good.** Optional: add {', '.join(missing)}")
            elif score >= 50:
                st.warning(f"🟠 Goal Quality: **{score}% — Fair.** Add: {', '.join(missing)}")
            else:
                st.error(f"🔴 Goal Quality: **{score}% — Incomplete.** Required: {', '.join(missing)}")
            st.progress(score / 100)

        # ── Assembled Goal Preview ────────────────────────────────────────────
        composed = compose_goal(st.session_state.gb)
        with q_col2:
            if composed:
                st.markdown("**📋 Composed Goal Preview:**")
                st.info(composed)

        final_goal = composed

    # ── Free-Text Mode ────────────────────────────────────────────────────────
    else:
        st.session_state.gb["freetext"] = st.text_area(
            "Campaign Goal",
            value=st.session_state.gb["freetext"],
            height=140,
            placeholder=(
                "Be specific. Include: product name, target audience, campaign objective, "
                "key message, channels, and timeline.\n\n"
                "Example: Launch a Q3 brand awareness campaign for the Geotab GO9, "
                "targeting logistics fleet managers, focusing on fuel savings and safety. "
                "Channels: email, LinkedIn, blog. Timeline: September 2025."
            ),
            help="A detailed description produces better, more tailored content.",
        )

        # Live character count and completeness hint
        text = st.session_state.gb["freetext"]
        char_count = len(text)
        word_count = len(text.split()) if text.strip() else 0
        hints = []
        for kw, label in [
            ("target", "target audience"), ("email|social|blog|linkedin|video", "channel"),
            ("Q1|Q2|Q3|Q4|season|launch", "timeline"), ("messag|value|benefit|focus", "key message")
        ]:
            import re
            if not re.search(kw, text, re.IGNORECASE):
                hints.append(label)

        col_info, col_hint = st.columns([1, 2])
        with col_info:
            color = "green" if word_count >= 25 else "orange" if word_count >= 10 else "red"
            st.markdown(f"<span style='color:{color}'>{word_count} words · {char_count} characters</span>", unsafe_allow_html=True)
        with col_hint:
            if hints:
                st.caption(f"Consider adding: {', '.join(hints)}")
            elif word_count >= 25:
                st.caption("✅ Goal looks comprehensive.")

        final_goal = st.session_state.gb["freetext"]

    # ── Launch Button ─────────────────────────────────────────────────────────
    st.divider()
    can_launch = bool(final_goal and final_goal.strip())

    launch_col, _ = st.columns([2, 3])
    with launch_col:
        if st.button("🚀 Start Campaign", type="primary", disabled=not can_launch, use_container_width=True):
            _active_provider = os.environ.get("LLM_PROVIDER", "gemini").lower()
            _missing_key = (
                (_active_provider == "groq" and not os.environ.get("GROQ_API_KEY")) or
                (_active_provider != "groq" and not os.environ.get("GOOGLE_API_KEY"))
            )
            if _missing_key:
                st.error("Please provide an API Key in the sidebar.")
            else:
                with st.spinner("Analysing goal & generating strategic plan..."):
                    langfuse_client = get_langfuse_client()
                    if langfuse_client and is_langfuse_enabled():
                        try:
                            trace = langfuse_client.trace(
                                name="streamlit_campaign_workflow",
                                metadata={"goal": final_goal, "interface": "streamlit"},
                                input={"goal": final_goal},
                            )
                            st.session_state.langfuse_trace_id = trace.id
                            st.session_state.langfuse_trace_url = trace.get_trace_url()
                        except Exception as e:
                            st.warning(f"Langfuse trace failed: {e}")

                    initial_input = {"goal": final_goal, "confidence_scores": {}}
                    if st.session_state.langfuse_trace_id:
                        initial_input["langfuse_trace_id"] = st.session_state.langfuse_trace_id

                    st.session_state.graph.invoke(initial_input, config=st.session_state.config)
                    st.session_state.run_stage = "plan_approval"
                    st.rerun()

    if not can_launch:
        st.caption("Fill in at least the Product / Service field to enable launch.")


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: plan_approval
# ═════════════════════════════════════════════════════════════════════════════

elif st.session_state.run_stage == "plan_approval":

    st.warning("⏸️ **HUMAN DECISION REQUIRED — Step 2 of 4:** Review & Approve Strategic Plan")
    st.caption("Review the AI-generated asset plan before content creation begins. You can start a new campaign to change the goal.")

    current_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(current_values)

    # ── KPI Benchmark Table ────────────────────────────────────────────────
    show_kpi_table(current_values.get("performance_estimates") or {})

    col_approve, col_reset = st.columns([2, 1])
    with col_approve:
        if st.button("✅ Approve Plan & Start Drafting", type="primary", use_container_width=True):
            log_audit("Plan Approval", "Approved strategic plan",
                      f"{len(current_values.get('plan', []))} assets approved")
            with st.spinner("Drafting all assets — this may take a minute..."):
                st.session_state.graph.invoke(None, config=st.session_state.config)
                st.session_state.run_stage = "draft_approval"
                st.rerun()
    with col_reset:
        if st.button("↩️ Redefine Goal", use_container_width=True):
            st.session_state.run_stage = "entry"
            st.session_state.compliance_acknowledged = {}
            st.session_state.graph = create_graph()
            st.session_state.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: draft_approval
# ═════════════════════════════════════════════════════════════════════════════

elif st.session_state.run_stage == "draft_approval":

    st.warning("⏸️ **Step 3 of 4:** Initial Draft Review")
    current_values = st.session_state.graph.get_state(st.session_state.config).values
    drafts = current_values.get("drafts", {})
    draft_variants = current_values.get("draft_variants") or {}
    compliance_flags = current_values.get("compliance_flags") or {}
    compliance_summary = current_values.get("compliance_summary") or {}
    confidence_scores = current_values.get("confidence_scores") or {}

    if confidence_scores:
        avg_score = sum(confidence_scores.values()) / len(confidence_scores)
        c1, c2, _ = st.columns([1, 1, 3])
        c1.metric("Campaign Readiness Score", f"{avg_score*100:.0f}%")
        c2.metric("Assets Drafted", len(drafts))
        st.divider()

    if current_values.get("plan"):
        st.subheader("1. Strategic Plan")
        plan_cols = st.columns(min(len(current_values["plan"]), 3))
        for i, step in enumerate(current_values["plan"]):
            with plan_cols[i % len(plan_cols)]:
                st.info(f"**{i+1}.** {step}")
        st.divider()

    if drafts:
        st.subheader("2. Content Drafts")
        for asset, content in drafts.items():
            score = confidence_scores.get(asset)
            badge = f"  ·  {_confidence_badge(score)} ({score*100:.0f}%)" if score is not None else ""
            summary = compliance_summary.get(asset, "PASS")
            compliance_icon = {"PASS": "✅", "WARN": "⚠️", "BLOCK": "🚫"}.get(summary, "✅")

            with st.expander(f"📄 {asset}{badge}   {compliance_icon} Compliance: {summary}", expanded=True):
                # Tabbed draft display
                show_draft_with_variants(asset, content, draft_variants.get(asset, ""))
                st.divider()
                # Compliance gate
                flags = compliance_flags.get(asset, [])
                show_compliance_gate(asset, flags, summary)

        st.divider()

    # Approve button is disabled until all HIGH-flag assets are acknowledged
    all_cleared = all(
        compliance_summary.get(asset, "PASS") != "BLOCK"
        or st.session_state.compliance_acknowledged.get(asset, False)
        for asset in drafts
    )

    if not all_cleared:
        st.error("🚫 One or more drafts have unacknowledged HIGH compliance flags. "
                 "Check the acknowledgement boxes above before continuing.")

    st.divider()
    col_pub, col_cont = st.columns([1, 2])
    with col_pub:
        if st.button("📤 Quick Publish to Google Docs", use_container_width=True, disabled=not all_cleared):
            from src.google_utils import publish_draft_to_gdoc
            goal_text = current_values.get("goal", "")
            with st.spinner("Publishing..."):
                for asset, content in drafts.items():
                    doc_id, doc_url = publish_draft_to_gdoc(f"{asset} — {goal_text[:40]}", content)
                    if doc_id.startswith("mock_"):
                        st.warning(f"**{asset}:** Mock published. [View]({doc_url})")
                    else:
                        st.success(f"**{asset}:** [Open in Google Docs ↗]({doc_url})")
    with col_cont:
        if st.button("✅ Continue to Detailed Review & Feedback", type="primary",
                     use_container_width=True, disabled=not all_cleared):
            st.session_state.run_stage = "feedback_collection"
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: feedback_collection
# ═════════════════════════════════════════════════════════════════════════════

elif st.session_state.run_stage == "feedback_collection":

    st.warning("⏸️ **HUMAN DECISION REQUIRED — Step 3 of 4:** Review & Approve Each Draft")
    st.caption("Your editorial judgment drives final quality. Approve drafts or request targeted revisions.")

    current_values = st.session_state.graph.get_state(st.session_state.config).values
    drafts = current_values.get("drafts", {})
    confidence_scores = current_values.get("confidence_scores") or {}

    # Campaign readiness summary bar
    if confidence_scores:
        avg_score = sum(confidence_scores.values()) / len(confidence_scores)
        c1, c2, c3 = st.columns([1, 1, 3])
        c1.metric("Campaign Readiness", f"{avg_score*100:.0f}%")
        approved_count = sum(1 for a in drafts if st.session_state.draft_statuses.get(a) == "approved")
        c2.metric("Approved", f"{approved_count} / {len(drafts)}")
        st.divider()

    draft_variants = current_values.get("draft_variants") or {}
    compliance_flags = current_values.get("compliance_flags") or {}
    compliance_summary = current_values.get("compliance_summary") or {}

    for asset_name, content in drafts.items():
        score = confidence_scores.get(asset_name)
        badge = f"  ·  {_confidence_badge(score)} Confidence ({score*100:.0f}%)" if score is not None else ""
        current_status = st.session_state.draft_statuses.get(asset_name, "pending")
        c_summary = compliance_summary.get(asset_name, "PASS")
        compliance_icon = {"PASS": "✅", "WARN": "⚠️", "BLOCK": "🚫"}.get(c_summary, "✅")

        status_color = {"approved": "✅", "needs_revision": "🔄", "pending": "⏳"}
        header = (
            f"📄 {asset_name}{badge}   "
            f"{status_color.get(current_status, '⏳')} {current_status.replace('_', ' ').title()}   "
            f"{compliance_icon} {c_summary}"
        )

        with st.expander(header, expanded=(current_status == "pending")):
            # Tabbed content preview
            show_draft_with_variants(asset_name, content, draft_variants.get(asset_name, ""))
            st.divider()
            # Compact compliance summary
            flags = compliance_flags.get(asset_name, [])
            if flags:
                high_count = sum(1 for f in flags if f["severity"] == "HIGH")
                med_count = sum(1 for f in flags if f["severity"] == "MEDIUM")
                st.caption(f"Compliance: {high_count} HIGH · {med_count} MEDIUM flag(s)")
            st.divider()

            # Action row
            a_col, b_col, c_col = st.columns([3, 1, 1])

            with a_col:
                st.session_state.draft_feedback[asset_name] = st.text_area(
                    "Revision notes",
                    value=st.session_state.draft_feedback.get(asset_name, ""),
                    placeholder="Describe changes (e.g., 'More formal tone', 'Add 2025 stats', 'Shorten to 150 words')",
                    height=80,
                    key=f"fb_{asset_name}",
                    label_visibility="collapsed",
                )

            with b_col:
                st.markdown("&nbsp;")
                if st.button("✅ Approve", key=f"app_{asset_name}", use_container_width=True):
                    st.session_state.draft_statuses[asset_name] = "approved"
                    log_audit("Draft Review", f"Approved: {asset_name}")
                    st.rerun()

            with c_col:
                st.markdown("&nbsp;")
                if st.button("🔄 Revise", key=f"rev_{asset_name}", use_container_width=True):
                    fb = st.session_state.draft_feedback.get(asset_name, "").strip()
                    if fb:
                        st.session_state.draft_statuses[asset_name] = "needs_revision"
                        log_audit("Draft Review", f"Revision requested: {asset_name}", fb)
                        st.rerun()
                    else:
                        st.error("Add revision notes before requesting a revision.")

    st.divider()

    # Bulk action + status summary
    total = len(drafts)
    approved = sum(1 for a in drafts if st.session_state.draft_statuses.get(a) == "approved")
    revise = sum(1 for a in drafts if st.session_state.draft_statuses.get(a) == "needs_revision")
    pending = total - approved - revise

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Assets", total)
    m2.metric("✅ Approved", approved)
    m3.metric("🔄 Needs Revision", revise)
    m4.metric("⏳ Pending", pending)

    bulk_col, submit_col = st.columns([1, 2])
    with bulk_col:
        if st.button("✅ Approve All", use_container_width=True):
            for asset in drafts:
                st.session_state.draft_statuses[asset] = "approved"
            log_audit("Draft Review", "Bulk approved all drafts", f"{len(drafts)} assets")
            st.rerun()

    with submit_col:
        if st.button("🚀 Submit & Continue", type="primary", use_container_width=True):
            all_reviewed = all(
                st.session_state.draft_statuses.get(a, "pending") != "pending"
                for a in drafts
            )
            if not all_reviewed:
                st.error(f"Please review all {pending} remaining draft(s) before continuing.")
            else:
                needs_revision = any(
                    st.session_state.draft_statuses.get(a) == "needs_revision"
                    for a in drafts
                )
                with st.spinner("Processing feedback..." if needs_revision else "Preparing final review..."):
                    st.session_state.graph.update_state(
                        st.session_state.config,
                        {
                            "user_feedback": st.session_state.draft_feedback,
                            "draft_status": st.session_state.draft_statuses,
                        },
                    )
                    st.session_state.graph.invoke(None, config=st.session_state.config)

                    if needs_revision:
                        st.session_state.draft_feedback = {}
                        st.session_state.draft_statuses = {}
                        st.session_state.run_stage = "feedback_collection"
                    else:
                        st.session_state.run_stage = "review_approval"
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: review_approval — Final publish gate
# ═════════════════════════════════════════════════════════════════════════════

elif st.session_state.run_stage == "review_approval":

    st.warning("⏸️ **HUMAN DECISION REQUIRED — Step 4 of 4:** Final Publish Authorization")
    st.info(
        "**Why this decision must stay human:** Publishing commits your brand to these materials. "
        "Legal liability and reputational risk cannot be delegated to an automated system. "
        "You are the authorizing Campaign Director."
    )

    current_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(current_values)

    # Export before committing to publish
    campaign_md = generate_campaign_markdown(current_values)
    dl_col, pub_col = st.columns([1, 2])
    with dl_col:
        st.download_button(
            label="⬇️ Export Campaign Brief",
            data=campaign_md,
            file_name=f"campaign_brief_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with pub_col:
        if st.button("🚀 Authorize & Publish to Google Workspace", type="primary", use_container_width=True):
            log_audit(
                "Publish Authorization",
                "Authorized final publish to Google Workspace",
                f"{len(current_values.get('drafts', {}))} assets",
            )
            with st.spinner("Publishing to Google Docs & scheduling in Calendar..."):
                st.session_state.graph.invoke(None, config=st.session_state.config)
                st.session_state.run_stage = "complete"
                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# STAGE: complete
# ═════════════════════════════════════════════════════════════════════════════

elif st.session_state.run_stage == "complete":

    st.success("🎉 Campaign Generation & Publishing Complete!")

    final_values = st.session_state.graph.get_state(st.session_state.config).values
    display_results(final_values)

    campaign_md = generate_campaign_markdown(final_values)
    dl_col, new_col = st.columns([1, 2])
    with dl_col:
        st.download_button(
            label="⬇️ Export Full Campaign Brief",
            data=campaign_md,
            file_name=f"campaign_brief_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with new_col:
        if st.button("🔄 Start New Campaign", use_container_width=True):
            st.session_state.graph = create_graph()
            st.session_state.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
            st.session_state.run_stage = "entry"
            st.session_state.draft_feedback = {}
            st.session_state.draft_statuses = {}
            st.session_state.compliance_acknowledged = {}
            st.session_state.langfuse_trace_id = None
            st.session_state.langfuse_trace_url = None
            st.session_state.audit_log = []
            st.session_state.gb = {
                "product": "", "audience": "", "objective": "Brand Awareness",
                "key_message": "", "channels": [], "timeline": "",
                "mode": "builder", "freetext": "",
            }
            st.rerun()
