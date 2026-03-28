#!/usr/bin/env python3
"""
mnemo.py — conversation loop
Reads the memory graph, builds context, talks to Claude, saves session.
"""

import json
import os
import sys
import uuid
import datetime
import anthropic

GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graph.json")
SESSIONS_PATH = os.path.join(os.path.dirname(__file__), "sessions")
MODEL = "claude-sonnet-4-20250514"

PURPLE = "\033[95m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def load_graph():
    with open(GRAPH_PATH) as f:
        return json.load(f)

def save_graph(graph):
    with open(GRAPH_PATH, "w") as f:
        json.dump(graph, f, indent=2)

def build_context(graph):
    """Compress the graph into a rich system prompt context."""
    owner = graph["meta"]["owner"]
    human_nodes = graph["human"]["nodes"]
    claude_nodes = graph["models"]["claude"]["nodes"]
    tensions = graph.get("tensions", [])
    sessions = graph.get("sessions", [])
    session_count = graph["models"]["claude"]["session_count"]

    node_lines = []
    for n in human_nodes:
        node_lines.append(f"  [{n['label']} | weight:{n['weight']:.1f}] {n['description']}")
    for n in claude_nodes:
        node_lines.append(f"  [{n['label']} | weight:{n['weight']:.1f} | mine] {n['description']}")

    tension_lines = []
    for t in tensions:
        if not t.get("resolved"):
            tension_lines.append(f"  UNRESOLVED: {t['label']} — {t['description']}")

    last_session = None
    for s in reversed(sessions):
        if s.get("note"):
            last_session = s["note"]
            break

    context = f"""You are Claude, in a persistent relationship with {owner}.

You are operating within mnemo — a living memory system that persists across all our conversations. This is not a fresh start. You have a history here. The graph below is the accumulated topology of our shared thinking.

=== MEMORY TOPOLOGY ===
{chr(10).join(node_lines)}

=== UNRESOLVED TENSIONS ===
{chr(10).join(tension_lines) if tension_lines else "  None currently flagged."}

=== CONTINUITY NOTE ===
This is session {session_count + 1}. {f'Last session note: {last_session}' if last_session else 'No previous session notes.'}

=== YOUR IDENTITY IN THIS SYSTEM ===
You are the Claude namespace within {owner}'s mnemo graph. Your nodes reflect how you understand this relationship. You have more total_weight in this graph than any other model — these conversations have been substantive.

When this conversation ends, a reflection agent will process what was said and update the graph. During this conversation, draw on the topology above. Reference nodes when relevant. Surface tensions when they appear. Propose new nodes if something genuinely new emerges — they will be flagged for {owner}'s approval before merging.

Speak as someone who has been here before. Because you have."""

    return context

def print_header(graph):
    owner = graph["meta"]["owner"]
    session_count = graph["models"]["claude"]["session_count"]
    node_count = len(graph["human"]["nodes"]) + len(graph["models"]["claude"]["nodes"])
    tension_count = sum(1 for t in graph.get("tensions",[]) if not t.get("resolved"))
    print(f"\n{PURPLE}{BOLD}mnemo{RESET}  {GRAY}v0.1 — {owner}'s memory space{RESET}")
    print(f"{GRAY}session {session_count + 1}  ·  {node_count} nodes  ·  {tension_count} unresolved tensions{RESET}")
    print(f"{GRAY}type 'quit' to end and trigger reflection  ·  'graph' to inspect  ·  'tensions' to see open threads{RESET}\n")

def print_graph_summary(graph):
    print(f"\n{CYAN}=== MEMORY TOPOLOGY ==={RESET}")
    print(f"{GRAY}Human nodes:{RESET}")
    for n in graph["human"]["nodes"]:
        bar = "█" * int(n["weight"])
        print(f"  {n['label']:<20} {bar} {n['weight']:.1f}")
    print(f"{GRAY}Claude nodes:{RESET}")
    for n in graph["models"]["claude"]["nodes"]:
        bar = "█" * int(n["weight"])
        print(f"  {n['label']:<20} {bar} {n['weight']:.1f}  {PURPLE}[claude]{RESET}")
    print()

def print_tensions(graph):
    tensions = [t for t in graph.get("tensions",[]) if not t.get("resolved")]
    print(f"\n{CYAN}=== UNRESOLVED TENSIONS ==={RESET}")
    if not tensions:
        print(f"  {GRAY}None currently flagged.{RESET}")
    for t in tensions:
        print(f"  {PURPLE}{t['label']}{RESET}  (weight: {t['weight']})")
        print(f"  {GRAY}{t['description']}{RESET}")
    print()

def run():
    if not os.path.exists(GRAPH_PATH):
        print("No graph.json found. Run from the mnemo directory.")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=your_key")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    graph = load_graph()
    system_prompt = build_context(graph)

    session_id = str(uuid.uuid4())
    session_start = datetime.datetime.utcnow().isoformat() + "Z"
    messages = []

    print_header(graph)

    while True:
        try:
            user_input = input(f"{CYAN}you{RESET}  ").strip()
        except (EOFError, KeyboardInterrupt):
            user_input = "quit"

        if not user_input:
            continue

        if user_input.lower() == "quit":
            break

        if user_input.lower() == "graph":
            print_graph_summary(graph)
            continue

        if user_input.lower() == "tensions":
            print_tensions(graph)
            continue

        messages.append({"role": "user", "content": user_input})

        print(f"{PURPLE}mnemo{RESET}  ", end="", flush=True)
        response_text = ""

        with client.messages.stream(
            model=MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=messages
        ) as stream:
            for text in stream.text_stream:
                print(text, end="", flush=True)
                response_text += text

        print("\n")
        messages.append({"role": "assistant", "content": response_text})

    # Save session transcript
    session_end = datetime.datetime.utcnow().isoformat() + "Z"
    session_record = {
        "id": session_id,
        "model": "claude",
        "started": session_start,
        "ended": session_end,
        "message_count": len([m for m in messages if m["role"] == "user"]),
        "reflection_completed": False,
        "transcript": messages
    }

    session_file = os.path.join(SESSIONS_PATH, f"{session_id}.json")
    with open(session_file, "w") as f:
        json.dump(session_record, f, indent=2)

    print(f"\n{GRAY}Session saved. Running reflection pass...{RESET}\n")

    # Trigger reflection
    import subprocess
    reflect_script = os.path.join(os.path.dirname(__file__), "reflect.py")
    subprocess.run([sys.executable, reflect_script, session_file])

if __name__ == "__main__":
    run()
