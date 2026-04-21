from backend.llm_adapter import normalize_completion
from backend.llm_client import LLMResult


def test_normalize_string():
    res = normalize_completion("hello world")
    assert isinstance(res, LLMResult)
    assert res.content == "hello world"
    assert res.used_llm is False


def test_normalize_dict():
    src = {"content": "ok", "used_llm": True, "provider": "test"}
    res = normalize_completion(src)
    assert res.content == "ok"
    assert res.used_llm is True
    assert res.provider == "test"


def test_normalize_llmresult():
    src = LLMResult(content="c", used_llm=True, provider="p")
    res = normalize_completion(src)
    assert res is src
