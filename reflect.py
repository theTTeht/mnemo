#!/usr/bin/env python3
"""
reflect.py — reflection agent
Runs after each session. Processes the transcript, updates graph weights,
proposes new nodes, surfaces new tensions. The consolidation cycle.
"""

import json
import os
import sys
import datetime
import anthropic

GRAPH_PATH = os.path.join(os.path.dirname(__file__), "graph.json")
REFLECTIONS_PATH = os.path.join(os.path.dirname(__file__), "reflections")
MODEL = "claude-sonnet-4-20250514"

PURPLE = "\033[95m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"
GREEN  = "\033[92m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def load_graph():
    with open(GRAPH_PATH) as f:
        return json.load(f)

def save_graph(graph):
    graph["meta"]["last_reflection"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(GRAPH_PATH, "w") as f:
        json.dump(graph, f, indent=2)

def build_reflection_prompt(graph, session):
    existing_nodes = []
    for n in graph["human"]["nodes"] + graph["models"]["claude"]["nodes"]:
        existing_nodes.append(f"{n['id']}: {n['label']} — {n['description']}")

    existing_tensions = []
    for t in graph.get("tensions", []):
        existing_tensions.append(f"{t['id']}: {t['label']} — {t['description']}")

    transcript_text = ""
    for msg in session.get("transcript", []):
        role = graph["meta"]["owner"] if msg["role"] == "user" else "Claude"
        transcript_text += f"\n{role}: {msg['content']}\n"

    return f"""You are the reflection agent for mnemo — a memory system that maintains a living graph of concepts for a human-AI relationship.

A conversation session has just ended. Your job is to process it and update the memory graph.

=== EXISTING GRAPH NODES ===
{chr(10).join(existing_nodes)}

=== EXISTING UNRESOLVED TENSIONS ===
{chr(10).join(existing_tensions) if existing_tensions else "None"}

=== SESSION TRANSCRIPT ===
{transcript_text}

=== YOUR TASK ===

Analyse this conversation carefully and respond with ONLY valid JSON in this exact structure:

{{
  "nodes_activated": ["list of existing node IDs that were meaningfully engaged in this conversation"],
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
  "tensions_resolved": ["tension_id if any tension was genuinely resolved in this conversation"],
  "reflection_note": "One or two sentences capturing the essential quality of this conversation for future context."
}}

Rules:
- Only propose genuinely new nodes — do not duplicate existing ones
- Node weights for new proposals: 1.0–2.5 for first appearance
- Edge weight deltas: 0.05–0.3 per session (slow accumulation)
- Coordinates: place new nodes near related existing ones, units are roughly -100 to 100
- Be conservative — three real nodes beat ten shallow ones
- The reflection_note will be shown at the start of the next session
"""

def decay_weights(graph):
    """Very slow decay on nodes not activated — keeps graph honest over time."""
    DECAY = 0.02
    MIN_WEIGHT = 0.5
    for n in graph["human"]["nodes"] + graph["models"]["claude"]["nodes"]:
        n["weight"] = max(MIN_WEIGHT, n["weight"] - DECAY)

def apply_reflection(graph, reflection, session_id):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    all_nodes = {n["id"]: n for n in graph["human"]["nodes"] + graph["models"]["claude"]["nodes"]}

    # Activate nodes — boost weight
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
            # Create edge if it doesn't exist yet
            graph["models"]["claude"]["edges"].append({
                "from": delta_spec["from"],
                "to": delta_spec["to"],
                "weight": delta_spec.get("delta", 0.1),
                "type": "resonance",
                "directed": False,
                "created": now
            })

    # Add proposed new nodes (flagged for approval)
    for node in reflection.get("new_nodes_proposed", []):
        node["created"] = now
        node["last_activated"] = now
        node["activation_count"] = 1
        graph["models"]["claude"]["nodes"].append(node)
        print(f"  {GREEN}+ proposed node:{RESET} {node['label']} — {node['description']}")

    # Add proposed new tensions
    for tension in reflection.get("new_tensions_proposed", []):
        tension["created"] = now
        graph["tensions"].append(tension)
        print(f"  {PURPLE}~ tension flagged:{RESET} {tension['label']}")

    # Resolve tensions
    for tension_id in reflection.get("tensions_resolved", []):
        for t in graph["tensions"]:
            if t["id"] == tension_id:
                t["resolved"] = True
                t["resolved_at"] = now
                print(f"  {GREEN}✓ tension resolved:{RESET} {t['label']}")

    # Update model stats
    graph["models"]["claude"]["session_count"] += 1
    graph["models"]["claude"]["total_weight"] += sum(
        all_nodes[nid]["weight"] for nid in reflection.get("nodes_activated", [])
        if nid in all_nodes
    )

    # Record session in graph
    note = reflection.get("reflection_note", "")
    graph["sessions"].append({
        "id": session_id,
        "model": "claude",
        "started": now,
        "ended": now,
        "message_count": 0,
        "reflection_completed": True,
        "nodes_activated": reflection.get("nodes_activated", []),
        "nodes_proposed": [n["id"] for n in reflection.get("new_nodes_proposed", [])],
        "edges_strengthened": reflection.get("edges_to_strengthen", []),
        "note": note
    })

    return note

def run(session_file):
    if not os.path.exists(session_file):
        print(f"Session file not found: {session_file}")
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    with open(session_file) as f:
        session = json.load(f)

    graph = load_graph()
    client = anthropic.Anthropic(api_key=api_key)

    print(f"{PURPLE}{BOLD}mnemo reflection{RESET}")
    print(f"{GRAY}processing session {session['id'][:8]}...{RESET}\n")

    prompt = build_reflection_prompt(graph, session)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()

    # Clean JSON from any markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        reflection = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Reflection parse error: {e}")
        print("Raw response:", raw[:500])
        sys.exit(1)

    # Apply slow decay first
    decay_weights(graph)

    # Apply reflection
    note = apply_reflection(graph, reflection, session["id"])

    # Save updated graph
    save_graph(graph)

    # Save reflection record
    reflection_file = os.path.join(
        REFLECTIONS_PATH,
        f"{session['id']}_reflection.json"
    )
    with open(reflection_file, "w") as f:
        json.dump({
            "session_id": session["id"],
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "reflection": reflection,
            "raw_response": raw
        }, f, indent=2)

    # Mark session as reflected
    session["reflection_completed"] = True
    with open(session_file, "w") as f:
        json.dump(session, f, indent=2)

    print(f"\n{GREEN}{BOLD}reflection complete{RESET}")
    if note:
        print(f"{GRAY}{note}{RESET}")
    print(f"\n{GRAY}graph updated · {len(reflection.get('nodes_activated',[]))} nodes activated · {len(reflection.get('new_nodes_proposed',[]))} proposed · {len(reflection.get('new_tensions_proposed',[]))} tensions flagged{RESET}\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reflect.py <session_file.json>")
        sys.exit(1)
    run(sys.argv[1])
