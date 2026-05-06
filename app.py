#!/usr/bin/env python3
"""AI Content System — Flask Dashboard with SSE real-time streaming."""

import sys, os, io, json, queue, threading, time
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
# ── Global state ──────────────────────────────────────────────
_clients: list = []
_clients_lock = threading.Lock()
_pipeline_lock = threading.Lock()

pipeline_state = {
    "running": False,
    "agents": {
        "scraper":        {"status": "idle", "logs": [], "output": None, "duration": None},
        "validator":      {"status": "idle", "logs": [], "output": None, "duration": None},
        "voice_writer":   {"status": "idle", "logs": [], "output": None, "duration": None},
        "hook_generator": {"status": "idle", "logs": [], "output": None, "duration": None},
    },
    "topic": "", "start_time": None, "end_time": None, "error": None,
}

def broadcast(event: str, data: dict):
    msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
    with _clients_lock:
        dead = []
        for q in _clients:
            try:   q.put_nowait(msg)
            except: dead.append(q)
        for q in dead: _clients.remove(q)


class AgentLogger(io.TextIOBase):
    def __init__(self, agent_id, original):
        self.agent_id, self.original, self._buf = agent_id, original, ""

    def write(self, text):
        try: self.original.write(text); self.original.flush()
        except: pass
        self._buf += text
        lines = self._buf.split("\n"); self._buf = lines[-1]
        for line in lines[:-1]:
            s = line.strip()
            if s:
                pipeline_state["agents"][self.agent_id]["logs"].append(s)
                broadcast("agent_log", {"agent": self.agent_id, "message": s,
                                         "ts": datetime.now().strftime("%H:%M:%S")})
        return len(text)

    def flush(self):
        try: self.original.flush()
        except: pass


def _set_status(aid, status):
    pipeline_state["agents"][aid]["status"] = status
    broadcast("agent_status", {"agent": aid, "status": status})


def _run_agent(aid, fn, *args, **kwargs):
    orig = sys.stdout
    sys.stdout = AgentLogger(aid, orig)
    t0 = time.time()
    result = None
    try:
        _set_status(aid, "running")
        result = fn(*args, **kwargs)
        pipeline_state["agents"][aid]["duration"] = round(time.time() - t0, 1)
        _set_status(aid, "done")
    except Exception as e:
        pipeline_state["agents"][aid]["duration"] = round(time.time() - t0, 1)
        _set_status(aid, "error")
        broadcast("agent_log", {"agent": aid, "message": f"ERROR: {e}",
                                  "ts": datetime.now().strftime("%H:%M:%S")})
    finally:
        sys.stdout = orig
    return result


def _load_json(path):
    p = BASE_DIR / path
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def _update_history(topic, s_data, h_data, v_data):
    history_file = BASE_DIR / ".tmp/runs_history.json"
    history = _load_json(".tmp/runs_history.json") if history_file.exists() else []
    
    # Calculate generated contents (e.g. number of hooks)
    content_count = len(h_data.get("hooks", [])) if h_data else 0
    # Calculate avg views from validator
    views = 0
    if v_data and v_data.get("top_topics"):
        views = v_data["top_topics"][0].get("avg_views", 0)
        
    run_record = {
        "id": f"run-{int(time.time())}",
        "topic": topic or "Auto Viral Scan Run",
        "timestamp": datetime.now().isoformat(),
        "status": "Completed",
        "agents": ["01", "02", "03", "04"],
        "contents_generated": content_count,
        "avg_views": views,
        "success_rate": 100,
        "validation": v_data
    }
    history.insert(0, run_record)
    history_file.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history


def run_pipeline(topic: str, skip_scrape: bool):
    with _pipeline_lock:
        for aid in pipeline_state["agents"]:
            pipeline_state["agents"][aid] = {"status": "idle", "logs": [], "output": None, "duration": None}
        pipeline_state.update(running=True, topic=topic,
                              start_time=datetime.now().isoformat(), end_time=None, error=None)

    broadcast("pipeline_start", {"topic": topic, "skip_scrape": skip_scrape})

    try:
        from tools.content_validator import run as validate
        from tools.voice_writer import run as write_script
        from tools.hook_generator import run as gen_hooks

        # Agent 01
        scraper_out = None
        if not skip_scrape:
            from tools.content_scraper import run as scrape
            scraper_out = _run_agent("scraper", scrape, topic)
        else:
            latest = BASE_DIR / ".tmp/scraped_content_latest.json"
            if latest.exists():
                scraper_out = str(latest)
                pipeline_state["agents"]["scraper"]["status"] = "skipped"
                broadcast("agent_status", {"agent": "scraper", "status": "skipped"})
                broadcast("agent_log", {"agent": "scraper",
                                         "message": "⚡ Using cached sample data — scrape skipped",
                                         "ts": datetime.now().strftime("%H:%M:%S")})
            else:
                broadcast("agent_log", {"agent": "scraper",
                                         "message": "❌ No cached data found. Disable skip-scrape.",
                                         "ts": datetime.now().strftime("%H:%M:%S")})
                _set_status("scraper", "error"); return

        # Agent 02
        validator_out = _run_agent("validator", validate, input_path=scraper_out)
        if not validator_out: pipeline_state["error"] = "Validator failed"; return
        v_data = _load_json(".tmp/validated_content_latest.json")
        pipeline_state["agents"]["validator"]["output"] = v_data
        broadcast("agent_output", {"agent": "validator", "data": v_data})

        # Agent 03
        script_out = _run_agent("voice_writer", write_script,
                                 topic=topic or None, validator_path=validator_out)
        if not script_out: pipeline_state["error"] = "Voice writer failed"; return
        s_data = _load_json(".tmp/script_latest.json")
        pipeline_state["agents"]["voice_writer"]["output"] = s_data
        broadcast("agent_output", {"agent": "voice_writer", "data": s_data})

        # Agent 04
        hooks_out = _run_agent("hook_generator", gen_hooks,
                                topic=topic or None, script_path=script_out)
        h_data = _load_json(".tmp/hooks_latest.json") if hooks_out else {}
        pipeline_state["agents"]["hook_generator"]["output"] = h_data
        broadcast("agent_output", {"agent": "hook_generator", "data": h_data})

        pipeline_state["end_time"] = datetime.now().isoformat()
        
        # Save history
        _update_history(topic, s_data, h_data, v_data)
        
        broadcast("pipeline_done", {"topic": topic, "script": s_data,
                                     "hooks": h_data, "validation": v_data})
    except Exception as e:
        pipeline_state["error"] = str(e)
        broadcast("pipeline_error", {"message": str(e)})
    finally:
        pipeline_state["running"] = False


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def index(): return render_template("index.html")

@app.route("/api/run", methods=["POST"])
def api_run():
    if pipeline_state["running"]:
        return jsonify({"error": "Pipeline already running"}), 409
    d = request.json or {}
    threading.Thread(target=run_pipeline,
                     args=(d.get("topic", "").strip(), d.get("skip_scrape", True)),
                     daemon=True).start()
    return jsonify({"status": "started"})

@app.route("/api/events")
def api_events():
    q = queue.Queue(maxsize=300)
    with _clients_lock: _clients.append(q)
    def stream():
        yield f"event: state\ndata: {json.dumps(pipeline_state, ensure_ascii=False, default=str)}\n\n"
        try:
            while True:
                try:    yield q.get(timeout=25)
                except queue.Empty: yield ": ping\n\n"
        finally:
            with _clients_lock:
                if q in _clients: _clients.remove(q)
    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/api/output/<kind>")
def api_output(kind):
    files = {"scrape": ".tmp/scraped_content_latest.json",
             "validate": ".tmp/validated_content_latest.json",
             "script": ".tmp/script_latest.json",
             "hooks": ".tmp/hooks_latest.json"}
    f = BASE_DIR / files.get(kind, "nonexistent")
    if not f.exists(): return jsonify({"error": "Not found"}), 404
    return jsonify(json.loads(f.read_text(encoding="utf-8")))

@app.route("/api/status")
def api_status(): return jsonify(pipeline_state)

@app.route("/api/stats")
def api_stats():
    history = _load_json(".tmp/runs_history.json") if (BASE_DIR / ".tmp/runs_history.json").exists() else []
    runs_this_week = len(history)
    contents_generated = sum(r.get("contents_generated", 0) for r in history)
    avg_success = 100.0 if history else 0.0
    avg_views = history[0].get("avg_views", 0) if history else 0
    
    # Extract topics
    topics = []
    if history and history[0].get("validation"):
        topics = history[0]["validation"].get("top_topics", [])
        
    # Extract insights
    insights = {}
    if history and history[0].get("validation"):
        val = history[0]["validation"]
        insights = {
            "topic": val.get("recommendation", "").split("**")[1] if "**" in val.get("recommendation", "") else "Auto Selected Topic",
            "format": val.get("top_formats", [{"format": "Reels"}])[0]["format"]
        }
        
    return jsonify({
        "runs_this_week": runs_this_week,
        "contents_generated": contents_generated,
        "avg_success_rate": avg_success,
        "avg_views": avg_views,
        "recent_runs": history[:5],
        "top_topics": topics,
        "insights": insights
    })

if __name__ == "__main__":
    print("🚀  AI Content Dashboard → http://127.0.0.1:5000")
    app.run(debug=False, threaded=True, port=5000)
