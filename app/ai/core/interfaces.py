"""
Core AI Interfaces for BIM-Guard.
Adheres to the Dependency Inversion Principle (DIP).
"""

from typing import Any, Dict, Protocol


class IVisionModel(Protocol):
    """Protocol for Vision-Language Models (VLMs)."""
    
    async def analyze_image(self, image_bytes: bytes, prompt: str) -> Dict[str, Any]:
        """Process visual data (e.g. BCF snapshot, P&ID) and return structured JSON."""
        ...

class IPredictiveModel(Protocol):
    """Protocol for Machine Learning inference (e.g. XGBoost, Scikit-Learn)."""
    
    def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Run ML inference on a normalized feature dictionary."""
        ...

class ITextModel(Protocol):
    """Protocol for pure LLM text tasks (e.g. Text-to-SQL, bSDD mapping)."""
    
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a text response given a prompt."""
        ...

class IAgentOrchestrator(Protocol):
    """Protocol for multi-agent workflows (e.g. LangGraph)."""
    
    async def execute_workflow(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the multi-agent workflow on the provided context."""
        ...
