"""
FastAPI bridge — streams the LangGraph trace as Server-Sent Events so the web
console can render a live run.

The frontend's *Replay* mode needs none of this (it plays a baked stream with zero
cost). This backend powers *Live* mode: it runs the real 6-agent graph on Gemini and
streams each trace event as it happens, pausing at the human-approval interrupt.

Run (from webapp/backend, with GOOGLE_API_KEY in the repo-root .env):
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000
"""
import json
import os
import sys
import threading
from pathlib import Path

# Windows guard: uvicorn's stdout is often ASCII/cp1252, so prints/logs containing
# em-dashes (—) inside the agent prompts crash the worker with a UnicodeEncodeError
# ("'ascii' codec can't encode '—'"). Force UTF-8 like the terminal runners do.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import hashlib
import hmac
import time as _time
import urllib.parse

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# Make the repo root importable (graph.py, llm.py, agents/, tools/ live there).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

app = FastAPI(title="Titan Operations Sentinel API")

# Single-user demo: one pending approval at a time, keyed by run_id.
_decision_value: dict[str, str] = {}
_decision_ready: dict[str, threading.Event] = {}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@app.get("/api/health")
def health():
    """Liveness plus what is actually wired up, so a demo can show the integrations are
    real rather than described."""
    out = {"ok": True, "pending_approvals": list(_decision_ready)}
    try:
        import observability
        import policy
        from integrations.approval import approval_channels
        out["observability"] = observability.status()
        out["approval"] = approval_channels()
        out["policy"] = policy.summary()
    except Exception as exc:  # noqa: BLE001 — health must never 500
        out["detail_error"] = str(exc)[:200]
    try:
        from rag.index import corpus_stats
        from rag.retrieve import default_mode
        out["retrieval"] = {**corpus_stats(), "mode": default_mode()}
    except Exception:  # noqa: BLE001
        pass
    return out


def _resolve(run_id: str | None, choice: str) -> dict:
    """The single place a paused run is resumed. The console, a Slack button and an email
    link all land here, so a decision is recorded identically however it arrived."""
    rid = run_id or (next(iter(_decision_ready)) if _decision_ready else None)
    if rid and rid in _decision_ready:
        _decision_value[rid] = "approve" if choice.lower().startswith("a") else "reject"
        _decision_ready[rid].set()
        return {"ok": True, "run_id": rid, "decision": _decision_value[rid]}
    return {"ok": False, "error": "no pending approval", "run_id": run_id}


class Decision(BaseModel):
    decision: str            # "approve" | "reject"
    run_id: str | None = None


@app.post("/api/decision")
def decision(d: Decision):
    """Resolve the human-in-the-loop approval gate for a paused run."""
    return _resolve(d.run_id, d.decision)


@app.get("/api/decision/link", response_class=HTMLResponse)
def decision_link(run_id: str, decision: str):
    """Resolve the gate from a link in an approval email.

    A GET that changes state is not something to do casually, so this is scoped as
    narrowly as it can be: it resolves one named run that is already paused and waiting,
    it cannot start anything, and a second click on the same link is a no-op because the
    run is no longer pending. The security boundary is the mailbox, which is the same
    boundary the plant already uses for a purchase approval by email. For anything
    stronger, use the Slack channel, which is signed."""
    result = _resolve(run_id, decision)
    if result["ok"]:
        body = (f"<h2>Recorded: {result['decision']}</h2>"
                f"<p>Run <code>{result['run_id']}</code> has been resumed and your "
                f"decision is in the audit log.</p>")
    else:
        body = ("<h2>Nothing to decide</h2><p>This run is not waiting for an approval. "
                "It may already have been decided, or it may have timed out.</p>")
    return HTMLResponse(
        "<html><head><meta charset='utf-8'><title>Titan Operations Sentinel</title>"
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:34rem;margin:4rem auto;"
        "padding:0 1rem;color:#111}code{background:#f4f4f5;padding:.1rem .3rem;"
        "border-radius:4px}</style></head><body>" + body + "</body></html>"
    )


def _slack_signature_valid(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack's request signature.

    Without this, anyone who learns the URL can approve a spend. The timestamp check is
    what stops a captured request being replayed later."""
    secret = os.getenv("SLACK_SIGNING_SECRET")
    if not secret:
        return False
    try:
        if abs(_time.time() - int(timestamp)) > 60 * 5:
            return False
    except (TypeError, ValueError):
        return False
    basestring = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


@app.post("/api/slack/interactions")
async def slack_interactions(request: Request):
    """Handle the Approve / Reject buttons from the Slack approval message.

    The button value carries the run id, so a click on an older message resolves the run
    it belongs to rather than whatever happens to be pending now."""
    raw = await request.body()
    ts = request.headers.get("X-Slack-Request-Timestamp", "")
    sig = request.headers.get("X-Slack-Signature", "")
    if not _slack_signature_valid(raw, ts, sig):
        return {"text": "Signature verification failed. The decision was not recorded."}

    # Slack posts application/x-www-form-urlencoded with a single `payload` field. We
    # parse the raw body we already read rather than using fastapi.Form, which would pull
    # in python-multipart purely to read one field we have in hand.
    try:
        form = urllib.parse.parse_qs(raw.decode("utf-8"))
        payload = (form.get("payload") or [""])[0]
        data = json.loads(payload)
        action = (data.get("actions") or [{}])[0]
        choice, _, run_id = str(action.get("value", "")).partition("::")
        user = (data.get("user") or {}).get("username", "unknown")
    except (ValueError, TypeError, IndexError):
        return {"text": "Could not read that action."}

    result = _resolve(run_id or None, choice or "reject")
    if not result["ok"]:
        return {"replace_original": False,
                "text": "That run is no longer waiting for a decision."}
    return {
        "replace_original": True,
        "text": (f"*{result['decision'].upper()}* by @{user} for run "
                 f"`{result['run_id']}`. The decision is in the audit log."),
    }


@app.get("/api/providers")
def providers():
    """Catalog of model providers + which are ready, and the active one."""
    import llm
    return {"active": llm.active_provider(), "model": llm.resolve_model(), "providers": llm.supported()}


_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _upsert_env(pairs: dict[str, str]) -> None:
    """Insert/update KEY=value lines in the repo-root .env (created if missing)."""
    lines = _ENV_PATH.read_text(encoding="utf-8").splitlines() if _ENV_PATH.exists() else []
    for key, value in pairs.items():
        row = f"{key}={value}"
        for i, ln in enumerate(lines):
            if ln.strip().startswith(f"{key}="):
                lines[i] = row
                break
        else:
            lines.append(row)
    _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Config(BaseModel):
    provider: str
    model: str
    apiKey: str | None = None
    persist: bool = False           # also write the key + model to repo-root .env
    azureEndpoint: str | None = None  # azure_openai only
    apiVersion: str | None = None     # azure_openai only


@app.post("/api/config")
def configure(c: Config):
    """Switch provider/model live. Key is held in memory; with persist=true it's also
    written to the gitignored repo-root .env so it survives a restart."""
    import llm
    p = llm.PROVIDER_BY_ID.get(c.provider)
    if not p:
        return {"ok": False, "error": f"unknown provider '{c.provider}'"}
    if c.apiKey:
        # strip stray whitespace/newlines/quotes a paste often carries — a common
        # cause of a valid key being rejected as API_KEY_INVALID.
        c.apiKey = c.apiKey.strip().strip('"').strip("'").strip()
        os.environ[p["keys"][0]] = c.apiKey            # live, in-memory for this process
    # Azure needs endpoint + api-version alongside the key (model = deployment name)
    if c.provider == "azure_openai":
        if c.azureEndpoint:
            os.environ["AZURE_OPENAI_ENDPOINT"] = c.azureEndpoint.strip().rstrip("/") + "/"
        if c.apiVersion:
            os.environ["OPENAI_API_VERSION"] = c.apiVersion.strip()
    os.environ["TOS_MODEL"] = f"{c.provider}:{c.model}"
    llm.get_chat_model.cache_clear()
    llm.get_llm.cache_clear()
    # the ReAct agents are @lru_cache'd bound to the model they were first built with —
    # clear them too, or a provider switch keeps calling the old provider.
    try:
        import agents
        agents.build_agents.cache_clear()
    except Exception:
        pass
    try:
        llm.get_chat_model()                            # validate it builds with the given key
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)[:200]}
    persisted = False
    if c.persist:
        try:
            pairs = {"TOS_MODEL": f"{c.provider}:{c.model}"}
            if c.apiKey:
                pairs[p["keys"][0]] = c.apiKey
            if c.provider == "azure_openai":
                if os.getenv("AZURE_OPENAI_ENDPOINT"):
                    pairs["AZURE_OPENAI_ENDPOINT"] = os.environ["AZURE_OPENAI_ENDPOINT"]
                if os.getenv("OPENAI_API_VERSION"):
                    pairs["OPENAI_API_VERSION"] = os.environ["OPENAI_API_VERSION"]
            _upsert_env(pairs)
            persisted = True
        except Exception as exc:  # noqa: BLE001
            return {"ok": True, "active": llm.active_provider(), "model": llm.resolve_model(),
                    "persisted": False, "persistError": str(exc)[:160]}
    return {"ok": True, "active": llm.active_provider(), "model": llm.resolve_model(), "persisted": persisted}


@app.get("/api/run")
def run(scenario: str = "happy"):
    def gen():
        from langgraph.types import Command

        from graph import build_graph, make_initial_state

        graph = build_graph()
        state = make_initial_state(scenario)
        rid = state["run_id"]
        cfg = {"configurable": {"thread_id": rid}, "recursion_limit": 50}
        ready = threading.Event()
        _decision_ready[rid] = ready

        def drain(stream):
            """Yield ('event', e) for each trace event; end with ('interrupt', value|None)."""
            interrupted = None
            for chunk in stream:
                if "__interrupt__" in chunk:
                    interrupted = chunk["__interrupt__"][0].value
                    continue
                for _node, upd in chunk.items():
                    for e in ((upd or {}).get("trace") or []):
                        if e.get("type") != "plan":   # the plan is emitted, enriched, at the end
                            yield ("event", e)
            yield ("interrupt", interrupted)

        try:
            interrupted = None
            for kind, payload in drain(graph.stream(state, cfg)):
                if kind == "event":
                    yield _sse(payload)
                else:
                    interrupted = payload

            if interrupted is not None:
                req = dict(interrupted)
                req["type"] = "approval_request"
                yield _sse(req)
                ready.wait(timeout=300)
                choice = _decision_value.get(rid, "reject")
                for kind, payload in drain(graph.stream(Command(resume={"decision": choice}), cfg)):
                    if kind == "event":
                        yield _sse(payload)

            final = graph.get_state(cfg).values
            yield _sse({
                "type": "plan",
                "status": final.get("status", "complete"),
                "text": final.get("final_plan", ""),
            })
        finally:
            _decision_ready.pop(rid, None)
            _decision_value.pop(rid, None)

    return StreamingResponse(gen(), media_type="text/event-stream")
