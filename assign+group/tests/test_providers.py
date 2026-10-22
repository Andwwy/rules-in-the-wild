"""The provider switch: what each route sends, how it authenticates, and how it fails — against a local recorder, no
network, no keys."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from rule_pipeline import llm

SCHEMA = {"type": "object", "properties": {"echo": {"type": "string"}}, "required": ["echo"]}
ANSWER = json.dumps({"echo": "hi"})

CHAT = {"id": "c1", "object": "chat.completion", "created": 0, "model": "gpt-5.6-terra",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": ANSWER}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
                  "completion_tokens_details": {"reasoning_tokens": 2}}}
RESPONSES = {"id": "r1", "object": "response", "created_at": 0, "status": "completed", "model": "gpt-5.6-terra",
             "output": [{"type": "message", "id": "m1", "status": "completed", "role": "assistant",
                         "content": [{"type": "output_text", "text": ANSWER, "annotations": []}]}],
             "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                       "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 2}},
             "parallel_tool_calls": True, "tool_choice": "auto", "tools": []}
AGENT = {"output": [{"type": "message", "content": [{"type": "output_text", "text": ANSWER}]}],
         "usage": {"input_tokens": 10, "output_tokens": 5, "cost": {"total_cost": 0.0001}}}


@pytest.fixture
def recorder():
    """A local HTTP server. `replies` is a list of (status, headers, body) served in order (the last one repeats);
    `seen` collects (path, headers, body) of every request."""
    state = {"replies": [], "seen": []}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("content-length", 0)))
            state["seen"].append((self.path, dict(self.headers), json.loads(body) if body else None))
            status, headers, reply = state["replies"].pop(0) if len(state["replies"]) > 1 else state["replies"][0]
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(reply).encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    state["url"] = f"http://127.0.0.1:{server.server_port}"
    yield state
    server.shutdown()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(llm.time, "sleep", slept.append)
    return slept


@pytest.fixture
def keys(monkeypatch):
    for k in ("AWS_BEARER_TOKEN_BEDROCK", "AWS_PROFILE", "AWS_REGION", "BEDROCK_MANTLE_REGION"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATEST")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("AWS_REGION_NAME", "us-east-1")


def settings(provider, **kw):
    return llm.Settings(provider=provider, **kw)


# ── model names ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_one_model_name_spelled_per_route():
    m = "openai/gpt-5.6-terra"
    assert llm.ROUTES["perplexity"].model(m) == "openai/gpt-5.6-terra"
    assert llm.ROUTES["openai"].model(m) == "openai/gpt-5.6-terra"
    assert llm.ROUTES["bedrock"].model(m) == "bedrock_mantle/openai.gpt-5.6-terra"
    assert llm.ROUTES["bedrock"].model("anthropic/claude-sonnet-4-6") == "bedrock/converse/anthropic.claude-sonnet-4-6"
    assert llm.ROUTES["bedrock"].model("us.anthropic.claude-opus-5") == "bedrock/converse/us.anthropic.claude-opus-5"


def test_openai_route_refuses_other_vendors(keys):
    with pytest.raises(llm.FatalLLMError, match="only serves OpenAI"):
        llm.call("p", "u", SCHEMA, settings("openai", model="anthropic/claude-sonnet-4-6"))


def test_aliases_and_unknown_provider(keys):
    assert llm.route_of(settings("pplx")) is llm.ROUTES["perplexity"]
    with pytest.raises(llm.FatalLLMError, match="unknown provider"):
        llm.route_of(settings("azure"))


def test_missing_key_stops_before_any_request(monkeypatch):
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    with pytest.raises(llm.FatalLLMError, match="PERPLEXITY_API_KEY is not set"):
        llm.call("p", "u", SCHEMA, settings("perplexity"))


def test_strict_schema_closes_objects_and_gives_up_on_optional_properties():
    assert llm.strict_schema(SCHEMA)["additionalProperties"] is False
    optional = {"type": "object", "properties": {"a": {"type": "string"}}, "required": []}
    assert llm.strict_schema(optional) is None


# ── what each route sends ──────────────────────────────────────────────────────────────────────────────────────────

def test_perplexity_agent_api(keys, recorder, monkeypatch):
    monkeypatch.setattr(llm, "PERPLEXITY_URL", recorder["url"] + "/v1/agent")
    recorder["replies"] = [(200, {}, AGENT)]
    answer, usage = llm.call("prompt", "rule", SCHEMA, settings("perplexity", effort="medium"))
    path, headers, body = recorder["seen"][0]
    assert answer == {"echo": "hi"} and usage["cost"] == 0.0001
    assert path == "/v1/agent" and headers["Authorization"] == "Bearer pplx-test"
    assert body["model"] == "openai/gpt-5.6-terra" and body["instructions"] == "prompt"
    assert body["reasoning"] == {"effort": "medium"} and body["service_tier"] == "flex"
    fmt = body["response_format"]["json_schema"]
    assert fmt["strict"] is True and fmt["schema"]["additionalProperties"] is False


def test_openai_chat_completions(keys, recorder, monkeypatch):
    pytest.importorskip("litellm")
    monkeypatch.setenv("OPENAI_BASE_URL", recorder["url"] + "/v1")
    recorder["replies"] = [(200, {}, CHAT)]
    answer, usage = llm.call("prompt", "rule", SCHEMA, settings("openai"))
    path, headers, body = recorder["seen"][0]
    assert answer == {"echo": "hi"} and usage["input"] == 10 and usage["reasoning"] == 2
    assert path == "/v1/chat/completions" and headers["Authorization"] == "Bearer sk-test"
    assert body["model"] == "gpt-5.6-terra" and body["reasoning_effort"] == "high" and body["service_tier"] == "flex"
    assert body["messages"][0] == {"role": "system", "content": "prompt"}
    fmt = body["response_format"]["json_schema"]
    assert fmt["strict"] is True and fmt["schema"]["additionalProperties"] is False


def test_bedrock_mantle_with_aws_credentials(keys, recorder, monkeypatch):
    pytest.importorskip("litellm")
    monkeypatch.setenv("BEDROCK_MANTLE_API_BASE", recorder["url"])
    recorder["replies"] = [(200, {}, RESPONSES)]
    answer, _ = llm.call("prompt", "rule", SCHEMA, settings("bedrock"))
    path, headers, body = recorder["seen"][0]
    assert answer == {"echo": "hi"}
    assert path.endswith("/openai/v1/responses") and headers["Authorization"].startswith("AWS4-HMAC-SHA256")
    assert body["model"] == "openai.gpt-5.6-terra" and body["reasoning"] == {"effort": "high"}
    assert "service_tier" not in body
    assert body["text"]["format"]["strict"] is True


def test_bedrock_api_key_is_a_bearer_token(keys, recorder, monkeypatch):
    pytest.importorskip("litellm")
    monkeypatch.setenv("BEDROCK_MANTLE_API_BASE", recorder["url"])
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "bedrock-key")
    recorder["replies"] = [(200, {}, RESPONSES)]
    llm.call("prompt", "rule", SCHEMA, settings("bedrock"))
    assert recorder["seen"][0][1]["Authorization"] == "Bearer bedrock-key"


def test_a_setting_the_route_cannot_take_stops_the_run(keys, recorder, monkeypatch):
    """Bedrock's Mantle endpoint has no flex tier: the run stops instead of the tier being dropped silently."""
    pytest.importorskip("litellm")
    monkeypatch.setenv("BEDROCK_MANTLE_API_BASE", recorder["url"])
    recorder["replies"] = [(200, {}, RESPONSES)]
    with pytest.raises(llm.FatalLLMError, match="flex"):
        llm.call("prompt", "rule", SCHEMA, settings("bedrock", tier="flex"))
    assert not recorder["seen"]


# ── failures ───────────────────────────────────────────────────────────────────────────────────────────────────────

def test_rejected_key_is_fatal(keys, recorder, monkeypatch):
    monkeypatch.setattr(llm, "PERPLEXITY_URL", recorder["url"] + "/v1/agent")
    recorder["replies"] = [(401, {}, {"error": "bad key"})]
    with pytest.raises(llm.FatalLLMError, match="401"):
        llm.call("p", "u", SCHEMA, settings("perplexity"))
    assert len(recorder["seen"]) == 1


def test_quota_429_is_fatal_other_429_waits_retry_after(keys, recorder, monkeypatch, no_sleep):
    monkeypatch.setattr(llm, "PERPLEXITY_URL", recorder["url"] + "/v1/agent")
    recorder["replies"] = [(429, {}, {"error": {"code": "insufficient_quota"}})]
    with pytest.raises(llm.FatalLLMError, match="quota"):
        llm.call("p", "u", SCHEMA, settings("perplexity"))
    recorder["replies"] = [(429, {"Retry-After": "7"}, {"error": "slow down"}), (200, {}, AGENT)]
    assert llm.call("p", "u", SCHEMA, settings("perplexity"))[0] == {"echo": "hi"}
    assert no_sleep == [7.0]


def test_openai_429_is_retried(keys, recorder, monkeypatch, no_sleep):
    pytest.importorskip("litellm")
    monkeypatch.setenv("OPENAI_BASE_URL", recorder["url"] + "/v1")
    recorder["replies"] = [(429, {"Retry-After": "3"}, {"error": {"message": "rate limit", "type": "requests"}}),
                           (200, {}, CHAT)]
    assert llm.call("p", "u", SCHEMA, settings("openai"))[0] == {"echo": "hi"}
    assert len(recorder["seen"]) == 2 and no_sleep and no_sleep[0] <= 10


def test_a_persistent_429_ends_as_an_item_error_not_a_crash(keys, recorder, monkeypatch, no_sleep):
    monkeypatch.setattr(llm, "PERPLEXITY_URL", recorder["url"] + "/v1/agent")
    recorder["replies"] = [(429, {}, {"error": "slow down"})]
    with pytest.raises(llm.LLMError, match="rate limited") as e:
        llm.call("p", "u", SCHEMA, settings("perplexity"))
    assert not isinstance(e.value, llm.FatalLLMError)
    assert len(recorder["seen"]) == llm.RATE_LIMIT_ATTEMPTS and max(no_sleep) <= 300


# ── keys from .env files ───────────────────────────────────────────────────────────────────────────────────────────

def test_nearest_env_wins_and_parents_fill_in(tmp_path, monkeypatch):
    for k in ("PIPE_TEST_A", "PIPE_TEST_B"):
        monkeypatch.delenv(k, raising=False)
    lab, run = tmp_path / "DAPlab", tmp_path / "DAPlab" / "rules" / "run"
    run.mkdir(parents=True)
    (lab / ".env").write_text("PIPE_TEST_A=lab\nPIPE_TEST_B=lab\n")
    (run / ".env").write_text("PIPE_TEST_A=run\n")
    llm.load_env(run)
    import os
    assert os.environ["PIPE_TEST_A"] == "run" and os.environ["PIPE_TEST_B"] == "lab"


def test_an_empty_bedrock_key_slot_falls_back_to_aws_credentials(keys, recorder, monkeypatch):
    """DAPlab/.env ships `AWS_BEARER_TOKEN_BEDROCK=` empty: that must mean "use ~/.aws", not "send an empty token"."""
    pytest.importorskip("litellm")
    monkeypatch.setenv("BEDROCK_MANTLE_API_BASE", recorder["url"])
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "")
    recorder["replies"] = [(200, {}, RESPONSES)]
    llm.call("prompt", "rule", SCHEMA, settings("bedrock"))
    assert recorder["seen"][0][1]["Authorization"].startswith("AWS4-HMAC-SHA256")


# ── the project's spend ledger ─────────────────────────────────────────────────────────────────────────────────────

def test_each_answered_call_is_logged(keys, recorder, monkeypatch, private_ledger):
    monkeypatch.setattr(llm, "PERPLEXITY_URL", recorder["url"] + "/v1/agent")
    recorder["replies"] = [(200, {}, AGENT)]
    llm.call("p", "u", SCHEMA, settings("perplexity"))
    rows = [json.loads(l) for l in private_ledger.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["source"] == "rule pipeline / perplexity" and rows[0]["cost"] == 0.0001


def test_a_spent_budget_stops_the_run_before_any_request(keys, recorder, monkeypatch, private_ledger):
    from rule_pipeline import spend
    monkeypatch.setattr(llm, "PERPLEXITY_URL", recorder["url"] + "/v1/agent")
    recorder["replies"] = [(200, {}, AGENT)]
    spend.record("experiment gateway", "claude-sonnet-5-5", 50.0)
    with pytest.raises(llm.FatalLLMError, match="budget spent"):
        llm.call("p", "u", SCHEMA, settings("perplexity"))
    assert not recorder["seen"]
