"""Provider-neutral AI client exports.

This module keeps route imports decoupled from legacy LMStudio-specific naming
while preserving backward compatibility through the existing implementation.
"""

from backend.lmstudio_client import LMStudioClient


class LocalAIClient(LMStudioClient):
    """Provider-neutral alias for the OpenAI-compatible local AI client."""


AIClient = LocalAIClient
