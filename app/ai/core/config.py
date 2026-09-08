"""
AI Configuration and Feature Flags.
"""

import os

# AI Subsystem Feature Flags
AI_FEATURE_ENABLED = os.getenv("AI_FEATURE_ENABLED", "true").lower() == "true"
AI_VLM_ENABLED = os.getenv("AI_VLM_ENABLED", "false").lower() == "true"
AI_AGENT_ORCHESTRATOR_ENABLED = os.getenv("AI_AGENT_ORCHESTRATOR_ENABLED", "false").lower() == "true"

# Model Routing
DEFAULT_LLM_PROVIDER = os.getenv("AI_DEFAULT_LLM", "litellm")
DEFAULT_VISION_PROVIDER = os.getenv("AI_DEFAULT_VISION", "openai")
DEFAULT_PREDICTIVE_BACKEND = os.getenv("AI_PREDICTIVE_BACKEND", "scikit")
