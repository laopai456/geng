# tests/test_classify.py
import json
from geng.classify import classify_memes, build_classify_prompt, parse_classify_response
from geng.models import Candidate

def _candidate(title):
    return Candidate(title=title, date="2026-07-05", platforms=["weibo", "bilibili"], hot_scores={"weibo": 100})

def test_build_classify_prompt_contains_all_titles():
    prompt = build_classify_prompt([_candidate("YYDS"), _candidate("某明星离婚")])
    assert "YYDS" in prompt
    assert "某明星离婚" in prompt
    assert "JSON" in prompt

def test_parse_classify_response_valid():
    raw = '{"items": [{"title": "YYDS", "is_meme": true, "confidence": 0.95, "reason": "网络缩写"}]}'
    parsed = parse_classify_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["is_meme"] is True
    assert parsed[0]["confidence"] == 0.95

def test_parse_classify_response_handles_garbage():
    parsed = parse_classify_response("这不是JSON")
    assert parsed == []

def test_classify_memes_with_mock_client():
    class MockLLM:
        def chat(self, model, messages):
            return '{"items": [{"title": "YYDS", "is_meme": true, "confidence": 0.9, "reason": "缩写梗"}]}'
    out = classify_memes([_candidate("YYDS")], client=MockLLM())
    assert len(out) == 1
    assert out[0].is_meme is True
    assert out[0].confidence == 0.9

def test_classify_memes_filters_non_meme():
    class MockLLM:
        def chat(self, model, messages):
            return '{"items": [{"title": "YYDS", "is_meme": true, "confidence": 0.9, "reason": ""}, {"title": "新闻", "is_meme": false, "confidence": 0.1, "reason": "新闻"}]}'
    out = classify_memes([_candidate("YYDS"), _candidate("新闻")], client=MockLLM())
    assert len(out) == 1
    assert out[0].title == "YYDS"
