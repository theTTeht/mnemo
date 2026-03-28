# mnemo

**A universal, open memory format for human-AI relationships.**

Named after Mnemosyne — goddess of memory, mother of the Muses.

Mnemo is a local-first, AI-agnostic memory system. It maintains a living mathematical graph of concepts, relationships, and tensions that grows through conversations with any AI. The graph is yours. It lives on your machine. It travels with you across every model you use.

---

## The core idea

Every AI conversation currently starts from zero. You carry the accumulated understanding. The AI doesn't. Mnemo inverts this — the understanding lives in a graph that any AI can read at the start of a conversation and write to at the end.

**Read during. Write after.**

The graph is always available as context during a conversation. The graph only updates after a conversation ends, through a reflection pass — exactly as human memory consolidates during sleep rather than in the moment of experience.

---

## Format specification v0.1

### Graph structure

The memory lives in `graph.json`. It is a directed weighted graph with the following top-level structure:

```json
{
  "meta": {
    "version": "0.1",
    "owner": "string — human identifier",
    "created": "ISO 8601 timestamp",
    "last_reflection": "ISO 8601 timestamp",
    "spec": "https://github.com/mnemo-spec/mnemo"
  },
  "human": {
    "nodes": [ ...node objects ],
    "edges": [ ...edge objects ]
  },
  "models": {
    "claude": { "nodes": [], "edges": [], "session_count": 0, "total_weight": 0 },
    "gpt4":   { "nodes": [], "edges": [], "session_count": 0, "total_weight": 0 },
    "grok":   { "nodes": [], "edges": [], "session_count": 0, "total_weight": 0 }
  },
  "sessions": [ ...session records ],
  "collaborators": []
}
```

### Node object

```json
{
  "id": "unique_string",
  "label": "human readable label",
  "description": "one sentence description",
  "owner": "human | claude | gpt4 | grok | shared",
  "weight": 1.0,
  "activation_count": 0,
  "created": "ISO 8601",
  "last_activated": "ISO 8601",
  "coordinates": { "x": 0.0, "y": 0.0, "z": 0.0 },
  "tags": []
}
```

### Edge object

```json
{
  "from": "node_id",
  "to": "node_id",
  "weight": 1.0,
  "type": "resonance | tension | derivation | opposition",
  "directed": false,
  "created": "ISO 8601"
}
```

### Weight semantics

- Node `weight` encodes significance — how central this concept is. Range 0.1–10.0. Increases when a node is activated in conversation. Decays slowly if never activated.
- Edge `weight` encodes relationship strength. Range 0.1–5.0. Increases when both connected nodes activate in the same session.
- Edge `type: tension` means the relationship is unresolved — two nodes in productive contradiction. These are preserved, not collapsed.
- Node `activation_count` is the raw count. Node `weight` is the processed significance score.

### Model namespace rules

- Each AI reads the entire graph at session start.
- Each AI writes only to its own namespace (`models.claude`, etc.) during reflection.
- Proposals to add nodes to the shared `human` topology are flagged as `proposed: true` and require human approval before merging.
- No AI may delete nodes from the `human` topology.
- The `total_weight` field in each model namespace reflects cumulative usage — this is what determines "brain size" in the visualiser.

### Session record

```json
{
  "id": "session_uuid",
  "model": "claude",
  "started": "ISO 8601",
  "ended": "ISO 8601",
  "message_count": 0,
  "reflection_completed": false,
  "nodes_activated": [],
  "nodes_proposed": [],
  "edges_strengthened": []
}
```

### Collaborator graphs

A collaborator is another person's mnemo graph that you have chosen to connect to. Their graph is read-only from your perspective. A shared namespace is created containing only nodes both graphs have in common, managed by the deduplication agent.

```json
{
  "collaborators": [
    {
      "id": "collaborator_uuid",
      "name": "string",
      "graph_path": "path or URL to their graph.json",
      "shared_namespace": { "nodes": [], "edges": [] },
      "connected": "ISO 8601",
      "sync_mode": "local | realtime"
    }
  ]
}
```

---

## Adding a new AI model

1. Add a key to `models` in `graph.json`
2. Implement the two functions: `build_context(graph)` and `reflect(session, graph)`
3. Add your model adapter in `adapters/`

That's it. The format is model-agnostic by design.

---

## File structure

```
mnemo/
├── README.md           ← this file (the spec)
├── graph.json          ← your memory topology (the brain)
├── mnemo.py            ← conversation loop
├── reflect.py          ← reflection agent (runs after each session)
├── visualise.html      ← 3D memory browser
├── install.sh          ← one-line installer
├── sessions/           ← raw session transcripts
├── reflections/        ← reflection pass outputs
└── models/
    ├── claude/         ← claude-specific memory
    ├── gpt4/           ← gpt4-specific memory
    └── grok/           ← grok-specific memory
```

---

## Philosophy

The graph does not belong to any AI. It belongs to you. The AIs are organs that plug into it — each contributing their particular kind of processing, each leaving a trace that is recognisably theirs. Over time the differential between how different models understand you becomes itself information.

This is not a productivity tool. It is the beginning of intellectual companionship with continuity.
