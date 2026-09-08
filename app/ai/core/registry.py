"""
AI Registry (Factory Pattern).
Resolves dependencies and routes requests to the correct implementations.
"""

import logging
from typing import Optional

from .config import AI_FEATURE_ENABLED, AI_VLM_ENABLED
from .interfaces import IAgentOrchestrator, IPredictiveModel, ITextModel, IVisionModel

logger = logging.getLogger("bimguard.ai.registry")

class AIFactory:
    """Central registry to instantiate AI clients safely."""

    @staticmethod
    def get_vision_model() -> Optional[IVisionModel]:
        if not AI_FEATURE_ENABLED or not AI_VLM_ENABLED:
            logger.info("Vision AI features are disabled via config.")
            return None
            
        # TODO: Return concrete IVisionModel instance
        return None

    @staticmethod
    def get_cost_predictor() -> Optional[IPredictiveModel]:
        if not AI_FEATURE_ENABLED:
            return None
            
        # TODO: Return loaded IPredictiveModel instance
        return None
        
    @staticmethod
    def get_text_model() -> Optional[ITextModel]:
        if not AI_FEATURE_ENABLED:
            return None
            
        # TODO: Return LiteLLM text model wrapper
        return None

    @staticmethod
    def get_orchestrator() -> Optional[IAgentOrchestrator]:
        from .config import AI_AGENT_ORCHESTRATOR_ENABLED
        if not AI_FEATURE_ENABLED or not AI_AGENT_ORCHESTRATOR_ENABLED:
            return None
            
        # TODO: Return concrete LangGraph orchestrator
        return None
