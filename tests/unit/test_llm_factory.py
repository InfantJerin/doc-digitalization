from src.core.settings import Settings
from src.integrations.claude_client import ClaudeClient
from src.integrations.litellm_client import LiteLLMClient
from src.integrations.llm_factory import get_llm_client
from src.integrations.openai_client import OpenAIClient


def test_llm_factory_returns_openai_compatible_client_when_configured():
    settings = Settings(
        llm_provider="openai_compatible",
        llm_api_key="test",
        llm_api_base="https://example.local/v1",
        agent_model="gpt-4.1-mini",
    )
    client = get_llm_client(settings)
    assert isinstance(client, OpenAIClient)


def test_llm_factory_returns_litellm_client_when_configured():
    settings = Settings(llm_provider="litellm", llm_api_key="test", agent_model="gpt-4.1-mini")
    client = get_llm_client(settings)
    assert isinstance(client, LiteLLMClient)


def test_llm_factory_defaults_to_claude_client():
    settings = Settings(llm_provider="anthropic", anthropic_api_key="test")
    client = get_llm_client(settings)
    assert isinstance(client, ClaudeClient)
