"""Provider-native LLM model discovery contracts."""

import asyncio

import httpx

import app.services.llm_model_service as model_service_module
from app.services.llm_model_service import LLMModelService


def _install_transport(monkeypatch, handler):
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(model_service_module.httpx, "AsyncClient", client_factory)


def test_ollama_models_use_local_tags_endpoint(monkeypatch):
    def handler(request):
        assert str(request.url) == "http://ollama.test:11434/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen2.5:7b"}, {"name": "llama3.2:latest"}]},
        )

    _install_transport(monkeypatch, handler)

    models = asyncio.run(
        LLMModelService().list_models("ollama", api_base="http://ollama.test:11434")
    )

    assert models == [
        ("ollama/llama3.2:latest", "llama3.2:latest"),
        ("ollama/qwen2.5:7b", "qwen2.5:7b"),
    ]


def test_gemini_models_are_filtered_to_generate_content(monkeypatch):
    def handler(request):
        assert request.url.params["key"] == "gemini-secret"
        if request.url.params.get("pageToken") == "next-page":
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-second",
                            "displayName": "Gemini Second",
                            "supportedGenerationMethods": ["generateContent"],
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-chat",
                        "displayName": "Gemini Chat",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/text-embedding",
                        "supportedGenerationMethods": ["embedContent"],
                    },
                ],
                "nextPageToken": "next-page",
            },
        )

    _install_transport(monkeypatch, handler)

    models = asyncio.run(
        LLMModelService().list_models("gemini", api_key="gemini-secret")
    )

    assert models == [
        ("gemini/gemini-chat", "Gemini Chat"),
        ("gemini/gemini-second", "Gemini Second"),
    ]


def test_anthropic_models_use_provider_headers(monkeypatch):
    def handler(request):
        assert request.headers["x-api-key"] == "anthropic-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        return httpx.Response(
            200,
            json={"data": [{"id": "claude-test", "display_name": "Claude Test"}]},
        )

    _install_transport(monkeypatch, handler)

    models = asyncio.run(
        LLMModelService().list_models("anthropic", api_key="anthropic-secret")
    )

    assert models == [("anthropic/claude-test", "Claude Test")]


def test_openai_compatible_models_get_correct_litellm_prefix(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "vendor/chat", "name": "Chat"},
                    {"id": "openrouter/auto", "name": "Auto"},
                ]
            },
        )

    _install_transport(monkeypatch, handler)
    service = LLMModelService()

    openai = asyncio.run(service.list_models("openai", api_key="openai-secret"))
    openrouter = asyncio.run(service.list_models("openrouter", api_key="router-secret"))

    assert openai == [("openrouter/auto", "Auto"), ("vendor/chat", "Chat")]
    assert openrouter == [
        ("openrouter/auto", "Auto"),
        ("openrouter/vendor/chat", "Chat"),
    ]
    assert requests[0].headers["authorization"] == "Bearer openai-secret"
    assert requests[1].headers["authorization"] == "Bearer router-secret"


def test_provider_http_error_does_not_expose_api_key(monkeypatch):
    def handler(request):
        return httpx.Response(401, json={"error": "unauthorized"})

    _install_transport(monkeypatch, handler)

    try:
        asyncio.run(LLMModelService().list_models("gemini", api_key="do-not-leak"))
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected model discovery to reject HTTP 401")

    assert "HTTP 401" in message
    assert "do-not-leak" not in message