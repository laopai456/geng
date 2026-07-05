# tests/test_explain.py
import json
from geng.explain import explain_meme, build_explain_prompt, parse_explain_response
from geng.models import ClassifiedMeme, FinalMeme

def _meme():
    return ClassifiedMeme(
        title="YYDS", date="2026-07-05", platforms=["weibo", "bilibili"],
        hot_scores={"weibo": 100}, is_meme=True, confidence=0.9,
        verified=True, bili_video_count=234,
    )

def test_build_explain_prompt_includes_title():
    p = build_explain_prompt(_meme())
    assert "YYDS" in p
    assert "释义" in p
    assert "JSON" in p

def test_parse_explain_response_valid():
    raw = '{"definition":"永远的神","origin":"电竞圈","usage":"赞美","examples":["科比YYDS"]}'
    d = parse_explain_response(raw)
    assert d["definition"] == "永远的神"
    assert d["examples"] == ["科比YYDS"]

def test_parse_explain_response_partial():
    raw = '{"definition":"某梗"}'
    d = parse_explain_response(raw)
    assert d["definition"] == "某梗"
    assert d["examples"] == []

def test_parse_explain_response_garbage():
    d = parse_explain_response("nope")
    assert d == {}

def test_explain_meme_with_mock():
    class MockLLM:
        def chat(self, model, messages):
            return '{"definition":"永远的神","origin":"电竞圈","usage":"赞美某人/某物","examples":["科比YYDS","这游戏YYDS"]}'
    out = explain_meme([_meme()], client=MockLLM())
    assert len(out) == 1
    f = out[0]
    assert isinstance(f, FinalMeme)
    assert f.definition == "永远的神"
    assert f.origin == "电竞圈"
    assert f.examples == ["科比YYDS", "这游戏YYDS"]
    assert f.verified is True

def test_explain_meme_failure_keeps_record():
    class MockLLM:
        def chat(self, model, messages): raise RuntimeError("500")
    out = explain_meme([_meme()], client=MockLLM())
    assert len(out) == 1
    assert out[0].definition is None   # 释义留空但记录仍在
