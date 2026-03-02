"""
Langfuse Integration Module

This module provides centralized Langfuse observability integration for the marketing agent workflow.
It handles initialization, callback management, and custom tracking utilities.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from functools import wraps

from src.config import is_langfuse_enabled, get_langfuse_config

logger = logging.getLogger(__name__)

# Global Langfuse client and handler instances
_langfuse_client = None
_langfuse_handler = None


def initialize_langfuse():
    """Initialize Langfuse client and callback handler."""
    global _langfuse_client, _langfuse_handler
    
    if not is_langfuse_enabled():
        logger.warning("Langfuse is not enabled. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable tracking.")
        return None, None
    
    try:
        from langfuse import Langfuse
        from langfuse.callback import CallbackHandler
        
        config = get_langfuse_config()
        
        _langfuse_client = Langfuse(
            public_key=config["public_key"],
            secret_key=config["secret_key"],
            host=config["host"]
        )
        
        _langfuse_handler = CallbackHandler(
            public_key=config["public_key"],
            secret_key=config["secret_key"],
            host=config["host"]
        )
        
        logger.info(f"✓ Langfuse initialized successfully (Host: {config['host']})")
        return _langfuse_client, _langfuse_handler
        
    except ImportError:
        logger.error("Langfuse packages not installed. Run: pip install langfuse langfuse-langchain")
        return None, None
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        return None, None


def get_langfuse_client():
    """Get or initialize the Langfuse client."""
    global _langfuse_client
    if _langfuse_client is None:
        initialize_langfuse()
    return _langfuse_client


def get_langfuse_handler():
    """Get or initialize the Langfuse callback handler for LangChain."""
    global _langfuse_handler
    if _langfuse_handler is None:
        initialize_langfuse()
    return _langfuse_handler


@contextmanager
def langfuse_trace(name: str, metadata: Optional[Dict[str, Any]] = None, user_id: Optional[str] = None):
    """
    Context manager for creating a Langfuse trace.
    
    Usage:
        with langfuse_trace("campaign_workflow", metadata={"goal": "..."}) as trace:
            # Your code here
            trace.update(output={"result": "..."})
    """
    client = get_langfuse_client()
    
    if client is None:
        # Langfuse not enabled, yield a no-op object
        class NoOpTrace:
            def update(self, **kwargs):
                pass
            def score(self, **kwargs):
                pass
            @property
            def get_trace_url(self):
                return None
        
        yield NoOpTrace()
        return
    
    try:
        trace = client.trace(name=name, metadata=metadata or {}, user_id=user_id)
        yield trace
        
    except Exception as e:
        logger.error(f"Error in langfuse_trace: {e}")
        yield None


@contextmanager
def langfuse_span(trace_id: str, name: str, metadata: Optional[Dict[str, Any]] = None, input_data: Optional[Any] = None):
    """
    Context manager for creating a Langfuse span within a trace.
    
    Usage:
        with langfuse_span(trace_id, "planner_node", input_data={"goal": "..."}) as span:
            # Your code here
            span.end(output={"plan": [...]})
    """
    client = get_langfuse_client()
    
    if client is None:
        # Langfuse not enabled, yield a no-op object
        class NoOpSpan:
            def end(self, **kwargs):
                pass
            def update(self, **kwargs):
                pass
        
        yield NoOpSpan()
        return
    
    try:
        span = client.span(
            trace_id=trace_id,
            name=name,
            metadata=metadata or {},
            input=input_data
        )
        yield span
        
    except Exception as e:
        logger.error(f"Error in langfuse_span: {e}")
        yield None


def track_agent_node(node_name: str):
    """
    Decorator to automatically track agent node execution with Langfuse.
    
    Usage:
        @track_agent_node("planner")
        def planner_node(state: AgentState) -> Dict:
            # Your node logic
            return {"plan": ...}
    """
    def decorator(func):
        @wraps(func)
        def wrapper(state, *args, **kwargs):
            # Skip tracking if Langfuse is not enabled
            if not is_langfuse_enabled():
                return func(state, *args, **kwargs)
            
            try:
                trace_id = state.get("langfuse_trace_id")
                
                if not trace_id:
                    # No trace ID in state, execute without tracking
                    return func(state, *args, **kwargs)
                
                client = get_langfuse_client()
                if not client:
                    return func(state, *args, **kwargs)
                
                # Create span for this node
                span = client.span(
                    trace_id=trace_id,
                    name=node_name,
                    input={
                        "goal": state.get("goal"),
                        "current_asset": state.get("current_asset"),
                        "retry_count": state.get("retry_count", 0),
                        "feedback_iteration": state.get("feedback_iteration", 0)
                    }
                )
                
                # Execute the node
                result = func(state, *args, **kwargs)
                
                # End span with output
                span.end(output=result)
                
                return result
                
            except Exception as e:
                logger.error(f"Error tracking node {node_name}: {e}")
                # Continue execution even if tracking fails
                return func(state, *args, **kwargs)
        
        return wrapper
    return decorator


def track_user_feedback(trace_id: str, asset_name: str, feedback: str, status: str):
    """
    Track user feedback as a Langfuse score.
    
    Args:
        trace_id: The Langfuse trace ID
        asset_name: Name of the asset being reviewed
        feedback: User's feedback text
        status: Approval status ("approved", "needs_revision", "pending")
    """
    client = get_langfuse_client()
    
    if not client:
        return
    
    try:
        # Map status to numeric score
        score_mapping = {
            "approved": 1.0,
            "needs_revision": 0.0,
            "pending": 0.5
        }
        
        client.score(
            trace_id=trace_id,
            name=f"user_feedback_{asset_name}",
            value=score_mapping.get(status, 0.5),
            comment=feedback
        )
        
        logger.info(f"Tracked user feedback for {asset_name}: {status}")
        
    except Exception as e:
        logger.error(f"Error tracking user feedback: {e}")


def track_guardrails_validation(trace_id: str, asset_name: str, passed: bool, details: str):
    """
    Track guardrails validation results.
    
    Args:
        trace_id: The Langfuse trace ID
        asset_name: Name of the asset being validated
        passed: Whether validation passed
        details: Validation details or error message
    """
    client = get_langfuse_client()
    
    if not client:
        return
    
    try:
        client.score(
            trace_id=trace_id,
            name=f"guardrails_{asset_name}",
            value=1.0 if passed else 0.0,
            comment=details
        )
        
        logger.info(f"Tracked guardrails validation for {asset_name}: {'passed' if passed else 'failed'}")
        
    except Exception as e:
        logger.error(f"Error tracking guardrails validation: {e}")


def track_retrieval_metrics(trace_id: str, query: str, doc_count: int, relevance_score: Optional[str] = None):
    """
    Track RAG retrieval metrics.
    
    Args:
        trace_id: The Langfuse trace ID
        query: The retrieval query
        doc_count: Number of documents retrieved
        relevance_score: Graded relevance ("yes" or "no")
    """
    client = get_langfuse_client()
    
    if not client:
        return
    
    try:
        metadata = {
            "query": query,
            "doc_count": doc_count
        }
        
        if relevance_score:
            score_value = 1.0 if relevance_score == "yes" else 0.0
            client.score(
                trace_id=trace_id,
                name="retrieval_relevance",
                value=score_value,
                comment=f"Query: {query[:100]}"
            )
        
        logger.info(f"Tracked retrieval metrics: {doc_count} docs, relevance={relevance_score}")
        
    except Exception as e:
        logger.error(f"Error tracking retrieval metrics: {e}")


def flush_langfuse():
    """Flush any pending Langfuse events. Call this before application shutdown."""
    client = get_langfuse_client()
    
    if client:
        try:
            client.flush()
            logger.info("Langfuse events flushed successfully")
        except Exception as e:
            logger.error(f"Error flushing Langfuse: {e}")
