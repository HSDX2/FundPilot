"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Each AI model backend implements this interface."""

    @property
    @abstractmethod
    def provider_type(self) -> str:
        """Return AIProviderType value (e.g. 'deepseek', 'openai')."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> str:
        """Send a chat completion request and return the response text."""
        ...

    @abstractmethod
    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        tools: list[dict] | None = None,
    ) -> dict:
        """Run analysis and return structured JSON result.

        The implementation should request JSON output from the model
        and parse it into a dict.
        """
        ...
