#!/usr/bin/env python3
"""
server.py — mnemo local server
Serves room.html and bridges browser to Claude API.
Run: python3 server.py
Then open: http://localhost:8765/room.html
"""

import os
import sys
import json
import uuid
import signal
import datetime
import threading
import anthropic
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8765
MODEL = "claude-sonnet-4-20250514"

BASE = os.path.dirname(os.path.abspath(__file__))
GRAPH_PATH = os.path.join(BASE, "graph.json")
SESSIONS_PATH = os.path.join(BASE, "sessions")
REFLECTIONS_PATH = os.path.join(BASE, "reflections")

# ── Active session tracking ──
# The server accumulates transcript messages so it can auto-save on shutdown
active_transcript = []
transcript_lock = threading.Lock()

def load_graph():
    with open(GRAPH_PATH) as f:
        return json.load(f)

def save_graph(graph):
    graph["meta"]["last_reflection"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(GRAPH_PATH, "w") as f:
        json.dump(graph, f, indent=2)

def build_reflection_prompt(graph, transcript):
    existing_nodes = []
    for n in graph["human"]["nodes"] + graph["models"]["claude"]["nodes"]:
        existing_nodes.append(f"{n['id']}: {n['label']} — {n['description']}")

    existing_tensions = []
    for t in graph.get("tensions", []):
        if not t.get("resolved"):
            existing_tensions.append(f"{t['id']}: {t['label']} — {t['description']}")

    transcript_text = ""
    for msg in transcript:
        role = graph["meta"].get("owner", "human") if msg["role"] == "user" else "Claude"
        transcript_text += f"\n{role}: {msg['content']}\n"

    return f"""You are the reflection agent for mnemo — a memory system that maintains a living graph of concepts for a human-AI relationship.

A conversation session has just ended. Process it and suggest graph updates.

=== EXISTING GRAPH NODES ===
{chr(10).join(existing_nodes)}

=== EXISTING UNRESOLVED TENSIONS ===
{chr(10).join(existing_tensions) if existing_tensions else "None"}

=== SESSION TRANSCRIPT ===
{transcript_text}

=== YOUR TASK ===

Analyse this conversation and respond with ONLY valid JSON:

{{
  "nodes_activated": ["list of existing node IDs meaningfully engaged"],
  "edges_to_strengthen": [
    {{"from": "node_id", "to": "node_id", "delta": 0.1}}
  ],
  "new_nodes_proposed": [
    {{
      "id": "snake_case_id",
      "label": "short label",
      "description": "one precise sentence",
      "owner": "claude",
      "weight": 1.5,
      "coordinates": {{"x": 0.0, "y": 0.0, "z": 0.0}},
      "tags": [],
      "proposed": true
    }}
  ],
  "new_tensions_proposed": [
    {{
      "id": "tension_snake_case",
      "label": "short label",
      "description": "what is unresolved and why it matters",
      "nodes_involved": ["node_id"],
      "weight": 2.0,
      "resolved": false
    }}
  ],
  "tensions_resolved": [],
  "reflection_note": "One or two sentences capturing the essential quality of this conversation."
}}

Rules:
- Only propose genuinely new nodes — do not duplicate existing ones
- Node weights for new proposals: 1.0–2.5
- Edge weight deltas: 0.05–0.3
- Be conservative — three real nodes beat ten shallow ones
- The reflection_note will shown at the start of the next session"""

def apply_reflection_to_graph(graph, reflection, feedback=None):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    all_nodes = {n["id"]: n for n in graph["human"]["nodes"] + graph["models"]["claude"]["nodes"]}

    # Activate nodes
    for node_id in reflection.get("nodes_activated", []):
        if node_id in all_nodes:
            n = all_nodes[node_id]
            n["weight"] = min(10.0, n["weight"] + 0.3)
            n["activation_count"] = n.get("activation_count", 0) + 1
            n["last_activated"] = now

    # Strengthen edges
    all_edges = graph["human"]["edges"] + graph["models"]["claude"]["edges"]
    for delta_spec in reflection.get("edges_to_strengthen", []):
        matched = False
        for edge in all_edges:
            if edge["from"] == delta_spec["from"] and edge["to"] == delta_spec["to"]:
                edge["weight"] = min(5.0, edge["weight"] + delta_spec.get("delta", 0.1))
                matched = True
                break
        if not matched:
            graph["models"]["claude"]["edges"].append({
                "from": delta_spec["from"], "to": delta_spec["to"],
                "weight": delta_spec.get("delta", 0.1),
                "type": "resonance", "directed": False, "created": now
            })

    # Add proposed nodes
    for node in reflection.get("new_nodes_proposed", []):
        node["created"] = now
        node["last_activated"] = now
        node["activation_count"] = 1
        graph["models"]["claude"]["nodes"].append(node)

    # Add tensions
    for tension in reflection.get("new_tensions_proposed", []):
        tension["created"] = now
        graph["tensions"].append(tension)

    # Resolve tensions
    for tension_id in reflection.get("tensions_resolved", []):
        for t in graph["tensions"]:
            if t["id"] == tension_id:
                t["resolved"] = True
                t["resolved_at"] = now

    # Update model stats
    graph["models"]["claude"]["session_count"] += 1
    graph["models"]["claude"]["total_weight"] = graph["models"]["claude"].get("total_weight", 0) + len(reflection.get("nodes_activated", []))

    # Store feedback in graph for future learning
    if feedback:
        if "feedback_log" not in graph:
            graph["feedback_log"] = []
        graph["feedback_log"].append({
            "timestamp": now,
            "feedback": feedback,
            "session_note": reflection.get("reflection_note", "")
        })

    # Record session
    graph["sessions"].append({
        "id": str(uuid.uuid4()),
        "model": "claude",
        "started": now, "ended": now,
        "reflection_completed": True,
        "nodes_activated": reflection.get("nodes_activated", []),
        "nodes_proposed": [n["id"] for n in reflection.get("new_nodes_proposed", [])],
        "note": reflection.get("reflection_note", ""),
        "human_feedback": feedback or []
    })

    return graph

def auto_save_on_shutdown():
    """Run reflection and save graph if there's an unsaved conversation."""
    with transcript_lock:
        transcript = list(active_transcript)

    if len(transcript) < 2:
        return False

    print("\n\033[93m⟳  unsaved session detected — running auto-reflection...\033[0m")

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("\033[91m✗  ANTHROPIC_API_KEY not set — saving raw transcript only\033[0m")
            session_id = str(uuid.uuid4())
            session_file = os.path.join(SESSIONS_PATH, f"{session_id}.json")
            with open(session_file, "w") as f:
                json.dump({"id": session_id, "model": "claude", "transcript": transcript,
                           "reflection_completed": False, "auto_saved": True}, f, indent=2)
            print(f"\033[92m✓  transcript saved → sessions/{session_id}.json\033[0m")
            return True

        client = anthropic.Anthropic(api_key=api_key)
        graph = load_graph()

        # Run reflection
        prompt = build_reflection_prompt(graph, transcript)
        response = client.messages.create(
            model=MODEL, max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        reflection = json.loads(raw)

        # Apply to graph
        updated = apply_reflection_to_graph(graph, reflection)
        save_graph(updated)

        # Save session transcript
        session_id = str(uuid.uuid4())
        session_file = os.path.join(SESSIONS_PATH, f"{session_id}.json")
        with open(session_file, "w") as f:
            json.dump({"id": session_id, "model": "claude", "transcript": transcript,
                       "reflection_completed": True, "auto_saved": True}, f, indent=2)

        # Save reflection record
        reflection_file = os.path.join(REFLECTIONS_PATH, f"{session_id}_reflection.json")
        with open(reflection_file, "w") as f:
            json.dump({"session_id": session_id, "reflection": reflection,
                       "feedback": [], "auto_saved": True}, f, indent=2)

        note = reflection.get("reflection_note", "")
        print(f"\033[92m✓  auto-reflection complete\033[0m")
        if note:
            print(f"\033[90m   {note}\033[0m")
        print(f"\033[90m   session → sessions/{session_id}.json\033[0m")
        return True

    except Exception as e:
        # If reflection fails, at least save the raw transcript
        print(f"\033[91m✗  reflection failed: {e}\033[0m")
        try:
            session_id = str(uuid.uuid4())
            session_file = os.path.join(SESSIONS_PATH, f"{session_id}.json")
            with open(session_file, "w") as f:
                json.dump({"id": session_id, "model": "claude", "transcript": transcript,
                           "reflection_completed": False, "auto_saved": True,
                           "error": str(e)}, f, indent=2)
            print(f"\033[93m⚠  raw transcript saved → sessions/{session_id}.json\033[0m")
        except Exception:
            print(f"\033[91m✗  could not save transcript\033[0m")
        return False

def shutdown_handler(signum, frame):
    """Handle Ctrl+C / SIGTERM gracefully."""
    print("\n\033[95mmnemo\033[0m  shutting down...")
    auto_save_on_shutdown()
    print("\033[90mgoodbye\033[0m\n")
    sys.exit(0)

class MnemoHandler(SimpleHTTPRequestHandler):

    def do_POST(self):

        length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(length))

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._error(500, "ANTHROPIC_API_KEY not set")
            return

        client = anthropic.Anthropic(api_key=api_key)

        # ── /api/chat ──
        if self.path == '/api/chat':
            try:
                messages = body.get('messages', [])
                response = client.messages.create(
                    model=MODEL, max_tokens=1024,
                    system=body.get('system', 'You are Claude within mnemo.'),
                    messages=messages
                )
                reply = response.content[0].text

                # Track transcript for auto-save
                with transcript_lock:
                    # Sync full conversation state from the room
                    active_transcript.clear()
                    active_transcript.extend(messages)
                    active_transcript.append({"role": "assistant", "content": reply})

                self._json({'content': [{'text': reply}]})
            except Exception as e:
                self._error(500, str(e))

        # ── /api/reflect ──
        elif self.path == '/api/reflect':
            try:
                graph = load_graph()
                prompt = build_reflection_prompt(graph, body.get('transcript', []))
                response = client.messages.create(
                    model=MODEL, max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw = response.content[0].text.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                raw = raw.strip()
                reflection = json.loads(raw)
                self._json({'reflection': reflection})
            except Exception as e:
                self._error(500, str(e))

        # ── /api/apply-reflection ──
        elif self.path == '/api/apply-reflection':
            try:
                graph = load_graph()
                reflection = body.get('reflection', {})
                feedback = body.get('feedback', [])
                transcript = body.get('transcript', [])

                # Save session transcript
                session_id = str(uuid.uuid4())
                session_file = os.path.join(SESSIONS_PATH, f"{session_id}.json")
                with open(session_file, "w") as f:
                    json.dump({"id": session_id, "model": "claude", "transcript": transcript, "reflection_completed": True}, f, indent=2)

                # Apply and save
                updated = apply_reflection_to_graph(graph, reflection, feedback)
                save_graph(updated)

                # Save reflection record
                reflection_file = os.path.join(REFLECTIONS_PATH, f"{session_id}_reflection.json")
                with open(reflection_file, "w") as f:
                    json.dump({"session_id": session_id, "reflection": reflection, "feedback": feedback}, f, indent=2)

                self._json({'ok': True, 'session_id': session_id})

                # Clear tracked transcript — session was properly saved
                with transcript_lock:
                    active_transcript.clear()

            except Exception as e:
                self._error(500, str(e))

        # ── /api/briefing ──
        elif self.path == "/api/briefing":
            try:
                import subprocess as sp2
                sp2.run([sys.executable, os.path.join(BASE, "briefing.py")], cwd=BASE, capture_output=True)
                briefing_path = os.path.join(BASE, "BRIEFING.md")
                with open(briefing_path) as f:
                    content2 = f.read()
                self._json({"ok": True, "content": content2})
            except Exception as e:
                self._error(500, str(e))

        # ── /api/github-push ──
        elif self.path == "/api/github-push":
            try:
                import subprocess as sp3, shutil
                github_path = os.path.expanduser("~/Downloads/mnemo_github/mnemo")
                if not os.path.exists(github_path):
                    self._json({"ok": False, "error": "mnemo_github folder not found"})
                    return
                files_to_sync = ["room.html","server.py","reflect.py","mnemo.py","README.md","EXPERIENCE.md","PROTOCOL.md","HOWTO.md","install.sh","requirements.txt","briefing.py","control.html"]
                for f in files_to_sync:
                    src = os.path.join(BASE, f)
                    dst = os.path.join(github_path, f)
                    if os.path.exists(src):
                        shutil.copy2(src, dst)
                sp3.run(["git","add","-A"], cwd=github_path, capture_output=True)
                result = sp3.run(["git","commit","-m","update from mnemo_live"], cwd=github_path, capture_output=True, text=True)
                if "nothing to commit" in result.stdout:
                    self._json({"ok": True, "message": "Nothing new to push"})
                    return
                push = sp3.run(["git","push"], cwd=github_path, capture_output=True, text=True)
                if push.returncode == 0:
                    self._json({"ok": True, "message": "Pushed successfully"})
                else:
                    self._json({"ok": False, "error": push.stderr[:200]})
            except Exception as e:
                self._error(500, str(e))

        else:
            self._error(404, "Not found")

    def do_GET(self):
        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST,GET,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _json(self, data):
        payload = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, code, msg):
        payload = json.dumps({'error': msg}).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(SESSIONS_PATH, exist_ok=True)
    os.makedirs(REFLECTIONS_PATH, exist_ok=True)

    # Register shutdown handlers
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(f"\n\033[95mmnemo\033[0m  room server")
    print(f"\033[90mopen → http://localhost:{PORT}/room.html\033[0m")
    print(f"\033[90mstop → ctrl+c (auto-saves unsaved sessions)\033[0m\n")

    try:
        HTTPServer(('localhost', PORT), MnemoHandler).serve_forever()
    except SystemExit:
        pass
