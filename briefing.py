#!/usr/bin/env python3
"""
briefing.py — mnemo dev briefing generator
Generates BRIEFING.md with everything needed to continue development
in any future conversation with Claude.

Run: python3 briefing.py
Then paste BRIEFING.md at the start of a new conversation.
"""

import json
import os
import datetime
import glob

BASE = os.path.dirname(os.path.abspath(__file__))
GRAPH_PATH = os.path.join(BASE, "graph.json")
BRIEFING_PATH = os.path.join(BASE, "BRIEFING.md")

FILES = {
    "mnemo.py": "Terminal conversation loop",
    "reflect.py": "Reflection agent (Terminal)",
    "server.py": "Local server + API bridge",
    "room.html": "3D room UI",
    "visualise.html": "Graph visualiser",
    "install.sh": "Installer",
    "README.md": "Format specification",
    "EXPERIENCE.md": "Experience narrative",
    "PROTOCOL.md": "Inter-model protocol",
    "HOWTO.md": "Daily use guide",
}

OPEN_ISSUES = [
    "Room reflection pass connected but auto-save on server stop not yet built",
    "GitHub push pending after each build session",
    "GPT-4 adapter not yet built (server_gpt.py)",
    "Daemon / background process not yet built",
    "RLM-style graph traversal for large graphs (future)",
    "Team/collaborator graph merging not yet built",
]

def load_graph():
    with open(GRAPH_PATH) as f:
        return json.load(f)

def file_sizes():
    lines = []
    for fname, desc in FILES.items():
        path = os.path.join(BASE, fname)
        if os.path.exists(path):
            size = os.path.getsize(path)
            with open(path) as f:
                lcount = sum(1 for _ in f)
            lines.append(f"- `{fname}` ({lcount} lines, {size//1024}KB) — {desc}")
        else:
            lines.append(f"- `{fname}` — NOT FOUND")
    return "\n".join(lines)

def graph_summary(graph):
    owner = graph["meta"].get("owner", "unknown")
    version = graph["meta"].get("version", "0.1")
    last_reflection = graph["meta"].get("last_reflection", "never")
    session_count = graph["models"]["claude"].get("session_count", 0)
    human_nodes = graph["human"]["nodes"]
    claude_nodes = graph["models"]["claude"]["nodes"]
    tensions = [t for t in graph.get("tensions", []) if not t.get("resolved")]

    lines = [
        f"- Owner: {owner}",
        f"- Version: {version}",
        f"- Last reflection: {last_reflection}",
        f"- Claude sessions: {session_count}",
        f"- Human nodes: {len(human_nodes)}",
        f"- Claude nodes: {len(claude_nodes)}",
        f"- Unresolved tensions: {len(tensions)}",
        "",
        "**Top nodes by weight:**",
    ]

    all_nodes = sorted(human_nodes + claude_nodes, key=lambda n: n.get("weight", 0), reverse=True)
    for n in all_nodes[:8]:
        owner_tag = f" [{n.get('owner','')}]" if n.get('owner') != 'human' else ""
        lines.append(f"- `{n['label']}` w:{n.get('weight',0):.1f}{owner_tag} — {n.get('description','')[:80]}")

    if tensions:
        lines.append("")
        lines.append("**Unresolved tensions:**")
        for t in tensions:
            lines.append(f"- `{t['label']}` — {t['description'][:100]}")

    # Recent session notes
    sessions = [s for s in graph.get("sessions", []) if s.get("note")]
    if sessions:
        lines.append("")
        lines.append("**Recent session notes:**")
        for s in sessions[-3:]:
            lines.append(f"- {s.get('note','')}")

    # Recent feedback
    feedback_log = graph.get("feedback_log", [])
    if feedback_log:
        lines.append("")
        lines.append("**Recent human feedback to Claude:**")
        for f in feedback_log[-3:]:
            for item in f.get("feedback", []):
                lines.append(f"- {item[:120]}")

    return "\n".join(lines)

def recent_reflections():
    pattern = os.path.join(BASE, "reflections", "*_reflection.json")
    files = sorted(glob.glob(pattern))[-3:]
    if not files:
        return "No reflections yet."
    lines = []
    for f in files:
        with open(f) as fh:
            data = json.load(fh)
        r = data.get("reflection", {})
        note = r.get("reflection_note", "")
        activated = r.get("nodes_activated", [])
        proposed = [n["label"] for n in r.get("new_nodes_proposed", [])]
        lines.append(f"- Note: {note}")
        if activated:
            lines.append(f"  Activated: {', '.join(activated)}")
        if proposed:
            lines.append(f"  Proposed: {', '.join(proposed)}")
    return "\n".join(lines) if lines else "No reflections yet."

def generate():
    graph = load_graph()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    briefing = f"""# mnemo — dev briefing
Generated: {now}

---

## What mnemo is

An open-source universal memory format for human-AI relationships. Local-first, model-agnostic. The graph is the brain — a mathematical topology of weighted nodes and edges that grows through conversation with any AI. The human owns it. The AIs are residents. Sessions read from the graph; reflection passes write back after conversation ends.

GitHub: https://github.com/theTTeht/mnemo

---

## Current file state

{file_sizes()}

---

## Graph state

{graph_summary(graph)}

---

## Recent reflections

{recent_reflections()}

---

## Open issues / next builds

{chr(10).join(f"- {issue}" for issue in OPEN_ISSUES)}

---

## Architecture decisions made

- **Read during, write after** — graph is context during conversation, only updated after reflection pass
- **Model namespaces** — each AI writes to its own namespace, reads everything
- **Editorial authority** — human reviews and approves all reflection proposals before merge
- **Feedback loop** — human corrections stored in graph, teach the system over time
- **Smart context** — top 12 nodes by relevance loaded per session, not full graph
- **Room + Terminal** — two interfaces, same graph. Room for immersive use, Terminal for quick sessions
- **GitHub template** — public repo has placeholder graph, personal graph never committed

---

## Key files to know

- `graph.json` — the brain. Never commit the live version.
- `room.html` — the immersive 3D UI. Single file, self-contained.
- `server.py` — local server bridging room to Claude API. Three endpoints: /api/chat, /api/reflect, /api/apply-reflection
- `reflect.py` — Terminal reflection agent (legacy, still used for Terminal sessions)
- `EXPERIENCE.md` — the soul document. Both perspectives on what mnemo is.
- `PROTOCOL.md` — inter-model communication spec.

---

## How to run

```bash
cd ~/Downloads/mnemo_live
python3 server.py
# open http://localhost:8765/room.html
```

---

## Continue from here

When starting a new dev session, paste this briefing and say what you want to build next. The most useful context beyond this document is the recent session notes and tensions above — they show where the thinking currently lives.
"""

    with open(BRIEFING_PATH, "w") as f:
        f.write(briefing)

    print(f"\n\033[95mmnemo\033[0m  briefing generated")
    print(f"\033[90m{BRIEFING_PATH}\033[0m")
    print(f"\033[90m{len(briefing)} chars — paste at the start of any dev session\033[0m\n")

if __name__ == "__main__":
    generate()
