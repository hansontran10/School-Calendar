import json
from types import SimpleNamespace

import pytest

from app.extraction import providers as P
from app.extraction.prompt import ExtractionContext
from tests.fakes import SAMPLE_RESULT, FakeProvider

CTX = ExtractionContext()


def test_first_provider_success():
    a = FakeProvider("a", [SAMPLE_RESULT])
    result, used = P.extract("text", CTX, providers=[a])
    assert used == "a" and len(result.items) == 4
    assert "text" in a.calls[0][1]


def test_retries_once_on_invalid_json():
    a = FakeProvider("a", ["{not json", SAMPLE_RESULT])
    _, used = P.extract("text", CTX, providers=[a])
    assert used == "a" and len(a.calls) == 2


def test_falls_back_after_two_invalid_replies():
    bad = {"course": {"code": None, "name": None}, "items": [{"title": "x"}]}
    a = FakeProvider("a", [bad, bad])
    b = FakeProvider("b", [SAMPLE_RESULT])
    _, used = P.extract("text", CTX, providers=[a, b])
    assert used == "b"


def test_falls_back_on_exception():
    a = FakeProvider("a", [RuntimeError("network down")])
    b = FakeProvider("b", [SAMPLE_RESULT])
    assert P.extract("text", CTX, providers=[a, b])[1] == "b"


def test_all_fail_raises():
    a = FakeProvider("a", [RuntimeError("boom")])
    with pytest.raises(P.ProviderError, match="a: boom"):
        P.extract("text", CTX, providers=[a])


def test_missing_keys_are_reported(monkeypatch):
    for var in ["CLAUDE_MODEL", "OPENAI_MODEL", "GEMINI_MODEL"]:
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(P.ProviderError, match="CLAUDE_MODEL is not set"):
        P.extract("text", CTX)


def test_provider_order(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDERS", "openai, gemini,claude")
    assert P.provider_order() == ["openai", "gemini", "claude"]
    assert P.provider_order("claude") == ["claude", "openai", "gemini"]


def test_claude_adapter_uses_forced_tool_call():
    sent = {}

    def create(**kw):
        sent.update(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="hi"),
                                        SimpleNamespace(type="tool_use", input=SAMPLE_RESULT)])

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    out = P.ClaudeProvider(client=client, model="m").complete_json("sys", "user", {"type": "object"})
    assert json.loads(out) == SAMPLE_RESULT
    assert sent["tool_choice"] == {"type": "tool", "name": "record_deadlines"}
    assert sent["tools"][0]["input_schema"] == {"type": "object"}
    assert sent["system"] == "sys"


def test_openai_adapter_uses_strict_schema():
    sent = {}

    def create(**kw):
        sent.update(kw)
        msg = SimpleNamespace(content=json.dumps(SAMPLE_RESULT), refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    out = P.OpenAIProvider(client=client, model="m").complete_json("sys", "user", {"type": "object"})
    assert json.loads(out) == SAMPLE_RESULT
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert sent["messages"][0] == {"role": "system", "content": "sys"}


def test_openai_refusal_raises():
    msg = SimpleNamespace(content=None, refusal="no")
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(message=msg)]))))
    with pytest.raises(P.ProviderError, match="refused"):
        P.OpenAIProvider(client=client, model="m").complete_json("s", "u", {})


def test_gemini_adapter_sends_json_schema():
    sent = {}

    def generate_content(**kw):
        sent.update(kw)
        return SimpleNamespace(text=json.dumps(SAMPLE_RESULT))

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    out = P.GeminiProvider(client=client, model="m").complete_json("sys", "user", {"type": "object"})
    assert json.loads(out) == SAMPLE_RESULT
    assert sent["config"].response_mime_type == "application/json"
    assert sent["config"].response_json_schema == {"type": "object"}
    assert sent["config"].system_instruction == "sys"
