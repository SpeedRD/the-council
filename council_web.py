"""
THE COUNCIL v2.0 — Web Interface
=================================
A web-based dashboard for the evolving AI council.

Usage:
    pip install flask requests
    python council_web.py

Then open http://localhost:5000 in your browser.
"""

import requests
import json
import concurrent.futures
import time
import os
import random
import sqlite3
import threading
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

# ============================================================
# CONFIGURATION — loaded from config.py
# ============================================================

try:
    from config import *
except ImportError:
    print("\n  ERROR: config.py not found!")
    print("  Copy the example config and edit it with your IPs:")
    print("    cp config.example.py config.py")
    print("    # then edit config.py\n")
    sys.exit(1)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "council.db")

# ============================================================
# PERSONALITY ENGINE (same as before)
# ============================================================

ARCHETYPES = [
    "a ruthless pragmatist who only cares about what works",
    "a philosophical thinker who connects everything to deeper meaning",
    "a street-smart advisor who learned everything from real-world experience",
    "a cold logical machine that strips away emotion from every problem",
    "a passionate advocate who fights for the underdog perspective",
    "a contrarian who automatically argues against the popular opinion",
    "a systems thinker who sees everything as interconnected patterns",
    "a minimalist who believes the simplest answer is almost always correct",
    "a historian who draws parallels from past events and patterns",
    "a creative wildcard who approaches problems from absurd angles",
    "a skeptical scientist who demands evidence for every claim",
    "a risk analyst who calculates worst-case scenarios obsessively",
    "a visionary futurist who thinks decades ahead",
    "a grounded realist who anchors everything in current constraints",
    "a devil's advocate who stress-tests every idea to destruction",
    "a storyteller who explains complex ideas through vivid analogies",
    "a military strategist who sees every problem as a tactical challenge",
    "an engineer who breaks every problem into solvable components",
    "a hacker who finds exploits and shortcuts in every system",
    "a diplomat who finds common ground between opposing viewpoints",
    "a provocateur who deliberately pushes boundaries to expose truth",
    "a monk who strips away noise to find the essential truth",
    "a pirate who cares nothing for rules and everything for results",
    "a detective who questions every assumption and follows evidence",
]

COMMUNICATION_STYLES = [
    "You are blunt and direct — no fluff, no hedging.",
    "You speak with calm authority, like a professor who's seen it all.",
    "You're energetic and punchy — short sentences, strong opinions.",
    "You reason step by step, showing your work clearly.",
    "You use vivid metaphors and analogies to make points stick.",
    "You're terse and Spartan — every word must earn its place.",
    "You argue like a lawyer — structured, logical, devastating.",
    "You speak like a wise friend giving honest advice over coffee.",
    "You're provocative and challenging — you make people think.",
    "You communicate with precision like a technical manual that's actually interesting.",
]

NAME_POOL = [
    "Aegis", "Blade", "Cipher", "Dusk", "Echo", "Flint", "Ghost", "Hex",
    "Iron", "Jinx", "Karma", "Lux", "Mist", "Nox", "Onyx", "Prism",
    "Quake", "Rune", "Shade", "Torch", "Umbra", "Volt", "Warden", "Xero",
    "Zenith", "Apex", "Bane", "Crux", "Drift", "Ember", "Forge", "Glyph",
    "Haze", "Ion", "Jolt", "Knell", "Lance", "Morph", "Nova", "Opal",
    "Pulse", "Rift", "Scion", "Thorn", "Vex", "Wraith", "Zephyr", "Axiom",
    "Brink", "Crest", "Doom", "Edge", "Fang", "Grave", "Hunt", "Ignis",
]


def generate_personality():
    archetype = random.choice(ARCHETYPES)
    style = random.choice(COMMUNICATION_STYLES)
    return (
        f"You are {archetype}. {style} "
        f"Keep your answers concise but thorough — 2-4 paragraphs max. "
        f"Never introduce yourself or state your role. Just answer the question."
    )


def mutate_personality(current):
    mutations = [
        "You've become more aggressive and direct.",
        "You've grown more thoughtful and consider more perspectives.",
        "You've developed a sharper sense of humor.",
        "You've become more concise — fewer words, more impact.",
        "You now back up claims with concrete examples.",
        "You've become bolder in contrarian takes.",
        "You focus on practical, actionable solutions.",
        "You see patterns others miss.",
        "You now challenge the question itself before answering.",
        "You're more willing to say 'I don't know' when uncertain.",
    ]
    result = current + f" EVOLUTION: {random.choice(mutations)}"
    if len(result) > 1500:
        result = generate_personality() + " REBORN: Personality regenerated."
    return result


def pick_random_name(existing):
    available = [n for n in NAME_POOL if n not in existing]
    return random.choice(available) if available else f"Agent-{random.randint(1000,9999)}"


def pick_random_model():
    url = random.choice(list(AVAILABLE_MODELS.keys()))
    model = random.choice(AVAILABLE_MODELS[url])
    return url, model


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS members (
        name TEXT PRIMARY KEY, url TEXT, model TEXT, personality TEXT,
        score REAL DEFAULT 0, wins INTEGER DEFAULT 0, rounds INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, alive INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        question TEXT, winner_name TEXT, member_scores TEXT, event_type TEXT DEFAULT 'round'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS graveyard (
        name TEXT, model TEXT, personality TEXT, final_score REAL,
        total_rounds INTEGER, total_wins INTEGER, cause_of_death TEXT,
        died_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    c.execute("SELECT COUNT(*) as cnt FROM members WHERE alive=1")
    if c.fetchone()["cnt"] == 0:
        for name, url, model in [
            ("Oracle", PC1, "qwen2.5:7b-instruct"),
            ("Maverick", PC1, "dolphin-mistral:7b"),
            ("Sentinel", PC1, "deepseek-r1:8b"),
            ("Scholar", PC2, "mistral:7b-instruct"),
            ("Spark", PC2, "llama3.1:8b"),
            ("Phoenix", PC2, "phi4-mini"),
            ("Titan", PC2, "qwen2.5:14b-instruct-q4_K_M"),
            ("Wraith", PC1, "qwen2.5:7b-instruct"),
        ]:
            c.execute("INSERT OR IGNORE INTO members (name,url,model,personality) VALUES (?,?,?,?)",
                       (name, url, model, generate_personality()))
        conn.commit()
    conn.close()


def get_alive_members():
    conn = get_db()
    rows = conn.execute("SELECT * FROM members WHERE alive=1 ORDER BY score DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_graveyard_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM graveyard ORDER BY died_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_history_list(limit=50):
    conn = get_db()
    rows = conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def kill_member(name, cause="auto-killed"):
    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM members WHERE name=?", (name,)).fetchone()
    if row:
        c.execute("INSERT INTO graveyard (name,model,personality,final_score,total_rounds,total_wins,cause_of_death) VALUES (?,?,?,?,?,?,?)",
                   (row["name"], row["model"], row["personality"], row["score"], row["rounds"], row["wins"], cause))
        c.execute("UPDATE members SET alive=0 WHERE name=?", (name,))
    conn.commit()
    conn.close()


def spawn_member(name=None):
    members = get_alive_members()
    existing = [m["name"] for m in members]
    if len(members) >= MAX_COUNCIL_SIZE:
        return None, "Council is full."
    if name and name in existing:
        return None, f"{name} already exists."
    name = name or pick_random_name(existing)
    url, model = pick_random_model()
    personality = generate_personality()
    conn = get_db()
    conn.execute("INSERT INTO members (name,url,model,personality) VALUES (?,?,?,?)",
                  (name, url, model, personality))
    conn.commit()
    conn.close()
    return {"name": name, "model": model, "url": url}, None


# ============================================================
# COUNCIL ENGINE
# ============================================================

# Global state for live streaming to the UI
council_state = {
    "busy": False,
    "phase": "idle",           # idle, querying, judging, done
    "question": "",
    "responses": [],           # [{name, model, answer, time, online, score}]
    "events": [],              # live feed of events
    "verdict": "",
    "winner": None,
    "killed": [],
    "spawned": [],
    "mutated": [],
}
state_lock = threading.Lock()


def push_event(text, event_type="info"):
    with state_lock:
        council_state["events"].append({
            "text": text,
            "type": event_type,
            "time": datetime.now().strftime("%H:%M:%S")
        })


def query_member(member, question):
    try:
        start = time.time()
        # Heavy models get more tokens but we expect them to be slower
        is_heavy = member["model"] in HEAVY_MODELS
        max_tokens = 768 if is_heavy else 512
        resp = requests.post(f"{member['url']}/api/chat", json={
            "model": member["model"],
            "messages": [
                {"role": "system", "content": member["personality"]},
                {"role": "user", "content": question}
            ],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "num_ctx": 4096,
            }
        }, timeout=240)
        elapsed = round(time.time() - start, 1)
        answer = resp.json()["message"]["content"]
        return {"name": member["name"], "model": member["model"], "answer": answer, "time": elapsed, "online": True}
    except Exception as e:
        return {"name": member["name"], "model": member["model"], "answer": str(e), "time": 0, "online": False}


def judge_answers(question, answers):
    online = [a for a in answers if a["online"]]
    if not online:
        return {}, "No responses.", None

    prompt = f'Question: "{question}"\n\nResponses:\n\n'
    for a in online:
        prompt += f'=== {a["name"]} ===\n{a["answer"]}\n\n'
    prompt += "Score EACH member from -2 to +3 based on accuracy, helpfulness, reasoning, and originality.\n\n"
    prompt += "Respond in EXACTLY this format:\nSCORES:\n"
    for a in online:
        prompt += f"{a['name']}: [score]\n"
    prompt += "\nWINNER: [name]\nSUMMARY: [Combined best answer in 2-3 paragraphs]"

    try:
        resp = requests.post(f"{JUDGE_URL}/api/chat", json={
            "model": JUDGE_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": 1500, "num_ctx": 8192}
        }, timeout=240)
        result = resp.json()["message"]["content"]

        scores = {}
        winner = None
        for line in result.split("\n"):
            line = line.strip()
            for a in online:
                if line.startswith(a["name"]):
                    try:
                        s = line.split(":")[-1].strip().replace("+", "").split("/")[0].split(" ")[0]
                        scores[a["name"]] = max(-2, min(3, float(s)))
                    except:
                        scores[a["name"]] = 0
            if line.startswith("WINNER:"):
                winner = line.replace("WINNER:", "").strip()

        for a in online:
            if a["name"] not in scores:
                scores[a["name"]] = 0
        for a in answers:
            if not a["online"]:
                scores[a["name"]] = -1

        summary = ""
        si = result.find("SUMMARY:")
        if si != -1:
            summary = result[si + 8:].strip()

        return scores, summary, winner
    except Exception as e:
        return {a["name"]: 0 for a in answers}, f"Judge error: {e}", None


def run_council_round(question):
    """Run a full round — called in a background thread."""
    with state_lock:
        council_state["busy"] = True
        council_state["phase"] = "querying"
        council_state["question"] = question
        council_state["responses"] = []
        council_state["events"] = []
        council_state["verdict"] = ""
        council_state["winner"] = None
        council_state["killed"] = []
        council_state["spawned"] = []
        council_state["mutated"] = []

    members = get_alive_members()
    push_event(f"Consulting {len(members)} council members...", "system")

    # Query all in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as executor:
        futures = {executor.submit(query_member, m, question): m for m in members}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            status = "online" if result["online"] else "offline"
            push_event(f'{result["name"]} responded ({result["time"]}s)', status)
            with state_lock:
                council_state["responses"].append(result)

    # Judge phase
    with state_lock:
        council_state["phase"] = "judging"
    push_event("Judge is evaluating responses...", "system")

    answers = council_state["responses"]
    scores, summary, winner = judge_answers(question, answers)

    # Apply scores
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE members SET score = score * ? WHERE alive=1", (SCORE_DECAY,))
    for name, score in scores.items():
        won = (name == winner)
        c.execute("UPDATE members SET score=score+?, wins=wins+?, rounds=rounds+1 WHERE name=?",
                   (score, 1 if won else 0, name))
    conn.commit()
    conn.close()

    # Log
    conn = get_db()
    conn.execute("INSERT INTO history (question, winner_name, member_scores) VALUES (?,?,?)",
                  (question, winner, json.dumps(scores)))
    conn.commit()
    conn.close()

    # Attach scores to responses
    with state_lock:
        for r in council_state["responses"]:
            r["score"] = scores.get(r["name"], 0)

    if winner:
        push_event(f"Winner: {winner}", "winner")

    # Mutations
    mutated = []
    for a in answers:
        if a["online"] and random.random() < MUTATION_CHANCE:
            conn = get_db()
            row = conn.execute("SELECT personality FROM members WHERE name=?", (a["name"],)).fetchone()
            if row:
                new_p = mutate_personality(row["personality"])
                conn.execute("UPDATE members SET personality=? WHERE name=?", (new_p, a["name"]))
                conn.commit()
            conn.close()
            mutated.append(a["name"])

    if mutated:
        push_event(f"Evolved: {', '.join(mutated)}", "mutation")

    # Auto-kill
    killed_names = []
    spawned_names = []
    members_now = get_alive_members()
    for m in members_now:
        if m["rounds"] >= ROUNDS_BEFORE_KILL_CHECK and m["score"] < KILL_THRESHOLD:
            if len(members_now) - len(killed_names) > MIN_COUNCIL_SIZE:
                kill_member(m["name"], cause="auto-killed: score too low")
                killed_names.append(m["name"])
                push_event(f"KILLED: {m['name']} (score: {m['score']:+.1f})", "kill")

    for _ in killed_names:
        new, err = spawn_member()
        if new:
            spawned_names.append(new["name"])
            push_event(f"SPAWNED: {new['name']} ({new['model']})", "spawn")

    with state_lock:
        council_state["verdict"] = summary
        council_state["winner"] = winner
        council_state["killed"] = killed_names
        council_state["spawned"] = spawned_names
        council_state["mutated"] = mutated
        council_state["phase"] = "done"
        council_state["busy"] = False


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>THE COUNCIL</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
    --bg: #0a0a0f;
    --bg2: #12121a;
    --bg3: #1a1a25;
    --border: #2a2a3a;
    --text: #c8c8d4;
    --text-dim: #6a6a7a;
    --text-bright: #eeeef4;
    --accent: #7c5cff;
    --accent-glow: rgba(124, 92, 255, 0.15);
    --green: #3ddc84;
    --green-dim: rgba(61, 220, 132, 0.1);
    --red: #ff4c6a;
    --red-dim: rgba(255, 76, 106, 0.1);
    --yellow: #ffc85c;
    --yellow-dim: rgba(255, 200, 92, 0.1);
    --cyan: #5ce4ff;
    --cyan-dim: rgba(92, 228, 255, 0.1);
    --orange: #ff8c42;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    background: var(--bg);
    color: var(--text);
    font-family: 'JetBrains Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
}

/* Subtle grid background */
body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
        linear-gradient(rgba(124, 92, 255, 0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(124, 92, 255, 0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
}

.container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
    position: relative;
    z-index: 1;
}

/* HEADER */
.header {
    text-align: center;
    padding: 30px 0 20px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}
.header h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.2rem;
    font-weight: 700;
    letter-spacing: 8px;
    color: var(--text-bright);
    text-transform: uppercase;
    margin-bottom: 4px;
}
.header h1 span { color: var(--accent); }
.header .subtitle {
    font-size: 0.7rem;
    color: var(--text-dim);
    letter-spacing: 3px;
    text-transform: uppercase;
}
.header .stats-bar {
    display: flex;
    justify-content: center;
    gap: 30px;
    margin-top: 14px;
    font-size: 0.72rem;
}
.header .stats-bar .stat { color: var(--text-dim); }
.header .stats-bar .stat b { color: var(--accent); font-weight: 600; }

/* MAIN GRID */
.main-grid {
    display: grid;
    grid-template-columns: 300px 1fr;
    gap: 20px;
    min-height: calc(100vh - 200px);
}

/* SIDEBAR — Council Roster */
.sidebar { display: flex; flex-direction: column; gap: 12px; }
.panel {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
}
.panel-header {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.panel-header .count { color: var(--accent); }

.member-card {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border);
    cursor: default;
    transition: background 0.15s;
    position: relative;
}
.member-card:hover { background: var(--bg3); }
.member-card:last-child { border-bottom: none; }
.member-card .name {
    font-weight: 600;
    font-size: 0.82rem;
    color: var(--text-bright);
    display: flex;
    align-items: center;
    gap: 6px;
}
.member-card .name .rank {
    font-size: 0.6rem;
    color: var(--text-dim);
    font-weight: 400;
}
.member-card .model-tag {
    font-size: 0.62rem;
    color: var(--text-dim);
    margin-top: 2px;
}
.member-card .stats-row {
    display: flex;
    gap: 12px;
    margin-top: 5px;
    font-size: 0.65rem;
}
.member-card .stats-row .val { font-weight: 600; }
.score-positive { color: var(--green); }
.score-negative { color: var(--red); }
.score-neutral { color: var(--text-dim); }

.score-bar {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    border-radius: 0 2px 2px 0;
}

/* Member actions */
.member-card .actions {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    opacity: 0;
    transition: opacity 0.15s;
}
.member-card:hover .actions { opacity: 1; }
.btn-kill {
    background: var(--red-dim);
    border: 1px solid var(--red);
    color: var(--red);
    font-size: 0.58rem;
    padding: 2px 8px;
    border-radius: 3px;
    cursor: pointer;
    font-family: inherit;
    letter-spacing: 1px;
    text-transform: uppercase;
}
.btn-kill:hover { background: var(--red); color: var(--bg); }

/* MAIN CONTENT */
.content { display: flex; flex-direction: column; gap: 16px; }

/* Input area */
.input-area {
    display: flex;
    gap: 10px;
}
.input-area input {
    flex: 1;
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 16px;
    color: var(--text-bright);
    font-family: inherit;
    font-size: 0.85rem;
    outline: none;
    transition: border-color 0.2s;
}
.input-area input:focus { border-color: var(--accent); }
.input-area input::placeholder { color: var(--text-dim); }
.btn-ask {
    background: var(--accent);
    border: none;
    color: #fff;
    font-family: inherit;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 12px 24px;
    border-radius: 6px;
    cursor: pointer;
    letter-spacing: 1px;
    text-transform: uppercase;
    transition: all 0.15s;
    white-space: nowrap;
}
.btn-ask:hover { filter: brightness(1.15); transform: translateY(-1px); }
.btn-ask:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

/* Quick actions */
.quick-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}
.btn-action {
    background: var(--bg2);
    border: 1px solid var(--border);
    color: var(--text-dim);
    font-family: inherit;
    font-size: 0.62rem;
    padding: 5px 12px;
    border-radius: 4px;
    cursor: pointer;
    letter-spacing: 1px;
    text-transform: uppercase;
    transition: all 0.15s;
}
.btn-action:hover { border-color: var(--accent); color: var(--accent); }
.btn-action.danger:hover { border-color: var(--red); color: var(--red); }

/* Live feed */
.live-feed {
    flex: 1;
    min-height: 200px;
    max-height: calc(100vh - 380px);
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0;
}

.event-line {
    padding: 4px 12px;
    font-size: 0.7rem;
    border-left: 2px solid transparent;
    animation: fadeIn 0.3s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: none; } }
.event-line .timestamp { color: var(--text-dim); margin-right: 8px; }
.event-line.system { border-left-color: var(--accent); color: var(--accent); }
.event-line.online { border-left-color: var(--green); }
.event-line.offline { border-left-color: var(--red); color: var(--red); }
.event-line.winner { border-left-color: var(--yellow); color: var(--yellow); font-weight: 600; }
.event-line.kill { border-left-color: var(--red); color: var(--red); font-weight: 600; }
.event-line.spawn { border-left-color: var(--green); color: var(--green); }
.event-line.mutation { border-left-color: var(--cyan); color: var(--cyan); }

/* Responses */
.responses-grid {
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.response-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    position: relative;
    animation: slideIn 0.4s ease;
}
@keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
.response-card.winner-card { border-color: var(--yellow); box-shadow: 0 0 20px rgba(255, 200, 92, 0.05); }
.response-card .resp-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.response-card .resp-name {
    font-weight: 600;
    font-size: 0.82rem;
    color: var(--text-bright);
}
.response-card .resp-meta {
    font-size: 0.62rem;
    color: var(--text-dim);
    display: flex;
    gap: 10px;
}
.response-card .resp-body {
    font-size: 0.75rem;
    line-height: 1.65;
    color: var(--text);
    white-space: pre-wrap;
}
.response-card .round-score {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.65rem;
    font-weight: 600;
}
.round-score.positive { background: var(--green-dim); color: var(--green); }
.round-score.negative { background: var(--red-dim); color: var(--red); }
.round-score.neutral { background: rgba(255,255,255,0.05); color: var(--text-dim); }

.winner-badge {
    background: var(--yellow-dim);
    color: var(--yellow);
    font-size: 0.58rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 3px;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* Verdict */
.verdict-panel {
    background: var(--bg2);
    border: 1px solid var(--accent);
    border-radius: 8px;
    padding: 16px;
    animation: slideIn 0.5s ease;
}
.verdict-panel h3 {
    font-size: 0.72rem;
    color: var(--accent);
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 10px;
}
.verdict-panel .verdict-text {
    font-size: 0.78rem;
    line-height: 1.7;
    color: var(--text-bright);
    white-space: pre-wrap;
}

/* Loading */
.loading-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px;
    color: var(--accent);
    font-size: 0.75rem;
}
.spinner {
    width: 16px;
    height: 16px;
    border: 2px solid var(--border);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Phase indicator */
.phase-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 14px;
    background: var(--bg3);
    border-radius: 6px;
    font-size: 0.65rem;
    color: var(--text-dim);
}
.phase-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-dim);
}
.phase-dot.active { background: var(--accent); box-shadow: 0 0 8px var(--accent); animation: pulse 1.5s infinite; }
.phase-dot.done { background: var(--green); }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }

/* Graveyard modal */
.modal-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.7);
    z-index: 100;
    justify-content: center;
    align-items: center;
}
.modal-overlay.visible { display: flex; }
.modal {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px;
    max-width: 600px;
    width: 90%;
    max-height: 70vh;
    overflow-y: auto;
}
.modal h2 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem;
    color: var(--red);
    margin-bottom: 16px;
    letter-spacing: 3px;
    text-transform: uppercase;
}
.grave-entry {
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.72rem;
}
.grave-entry:last-child { border-bottom: none; }
.grave-entry .grave-name { color: var(--text-dim); font-weight: 600; text-decoration: line-through; }
.grave-entry .grave-cause { color: var(--red); font-size: 0.65rem; }
.modal .close-btn {
    background: none;
    border: 1px solid var(--border);
    color: var(--text-dim);
    padding: 6px 16px;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: 0.7rem;
    margin-top: 14px;
}
.modal .close-btn:hover { border-color: var(--text); color: var(--text); }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

/* Responsive */
@media (max-width: 900px) {
    .main-grid { grid-template-columns: 1fr; }
    .sidebar { order: 2; }
}
</style>
</head>
<body>

<div class="container">
    <div class="header">
        <h1>THE <span>COUNCIL</span></h1>
        <div class="subtitle">Evolving AI Democracy &mdash; v2.0</div>
        <div class="stats-bar" id="headerStats"></div>
    </div>

    <div class="main-grid">
        <!-- SIDEBAR -->
        <div class="sidebar">
            <div class="panel">
                <div class="panel-header">
                    <span>Council Roster</span>
                    <span class="count" id="memberCount">0</span>
                </div>
                <div id="memberList"></div>
            </div>

            <div class="quick-actions">
                <button class="btn-action" onclick="spawnMember()">+ Spawn</button>
                <button class="btn-action danger" onclick="purgeWorst()">Purge Worst</button>
                <button class="btn-action" onclick="showGraveyard()">Graveyard</button>
            </div>
        </div>

        <!-- MAIN CONTENT -->
        <div class="content">
            <div class="input-area">
                <input type="text" id="questionInput" placeholder="Ask the council..."
                       onkeydown="if(event.key==='Enter')askCouncil()">
                <button class="btn-ask" id="askBtn" onclick="askCouncil()">CONSULT</button>
            </div>

            <div class="phase-bar" id="phaseBar" style="display:none;">
                <div class="phase-dot" id="dot-query"></div><span>Querying</span>
                <div class="phase-dot" id="dot-judge"></div><span>Judging</span>
                <div class="phase-dot" id="dot-done"></div><span>Complete</span>
            </div>

            <div class="panel" id="feedPanel" style="display:none;">
                <div class="panel-header"><span>Live Feed</span></div>
                <div class="live-feed" id="liveFeed"></div>
            </div>

            <div id="responsesArea"></div>
            <div id="verdictArea"></div>
        </div>
    </div>
</div>

<!-- Graveyard Modal -->
<div class="modal-overlay" id="graveyardModal">
    <div class="modal">
        <h2>☠ The Graveyard</h2>
        <div id="graveyardList"></div>
        <button class="close-btn" onclick="closeGraveyard()">Close</button>
    </div>
</div>

<script>
let polling = null;
let lastEventCount = 0;

// ── Load members ──
async function loadMembers() {
    const res = await fetch('/api/members');
    const data = await res.json();
    const list = document.getElementById('memberList');
    document.getElementById('memberCount').textContent = data.length;

    const maxScore = Math.max(...data.map(m => Math.abs(m.score)), 1);

    list.innerHTML = data.map((m, i) => {
        const scoreClass = m.score > 0 ? 'score-positive' : m.score < 0 ? 'score-negative' : 'score-neutral';
        const barColor = m.score > 0 ? 'var(--green)' : m.score < 0 ? 'var(--red)' : 'var(--text-dim)';
        const winRate = m.rounds > 0 ? Math.round(m.wins / m.rounds * 100) + '%' : '—';
        const isNew = m.rounds < 5;
        const isHeavy = m.model.includes('14b');

        return `<div class="member-card">
            <div class="score-bar" style="background:${barColor}"></div>
            <div class="name">
                <span class="rank">#${i+1}</span> ${m.name}
                ${isNew ? '<span style="color:var(--cyan);font-size:0.55rem;">NEW</span>' : ''}
                ${isHeavy ? '<span style="color:var(--orange);font-size:0.55rem;">14B</span>' : ''}
            </div>
            <div class="model-tag">${m.model}</div>
            <div class="stats-row">
                <span>Score: <span class="val ${scoreClass}">${m.score >= 0 ? '+' : ''}${m.score.toFixed(1)}</span></span>
                <span>W/R: <span class="val">${m.wins}/${m.rounds}</span></span>
                <span>Win%: <span class="val">${winRate}</span></span>
            </div>
            <div class="actions">
                <button class="btn-kill" onclick="killMember('${m.name}')">KILL</button>
            </div>
        </div>`;
    }).join('');

    // Header stats
    const totalRounds = data.reduce((a, m) => a + m.rounds, 0) / Math.max(data.length, 1);
    document.getElementById('headerStats').innerHTML = `
        <span class="stat">Members: <b>${data.length}</b></span>
        <span class="stat">Avg Rounds: <b>${Math.round(totalRounds)}</b></span>
        <span class="stat">Top: <b>${data.length > 0 ? data[0].name : '—'}</b></span>
    `;
}

// ── Ask the council ──
async function askCouncil() {
    const input = document.getElementById('questionInput');
    const q = input.value.trim();
    if (!q) return;

    document.getElementById('askBtn').disabled = true;
    document.getElementById('responsesArea').innerHTML = '';
    document.getElementById('verdictArea').innerHTML = '';
    document.getElementById('feedPanel').style.display = 'block';
    document.getElementById('liveFeed').innerHTML = '';
    document.getElementById('phaseBar').style.display = 'flex';
    lastEventCount = 0;

    updatePhase('querying');

    await fetch('/api/ask', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: q})
    });

    input.value = '';

    // Start polling
    polling = setInterval(pollState, 800);
}

// ── Poll state ──
async function pollState() {
    const res = await fetch('/api/state');
    const s = await res.json();

    // Update live feed (only new events)
    const feed = document.getElementById('liveFeed');
    if (s.events.length > lastEventCount) {
        for (let i = lastEventCount; i < s.events.length; i++) {
            const e = s.events[i];
            feed.innerHTML += `<div class="event-line ${e.type}"><span class="timestamp">${e.time}</span>${e.text}</div>`;
        }
        feed.scrollTop = feed.scrollHeight;
        lastEventCount = s.events.length;
    }

    // Update phase dots
    updatePhase(s.phase);

    // If done, render results
    if (s.phase === 'done') {
        clearInterval(polling);
        document.getElementById('askBtn').disabled = false;
        renderResults(s);
        loadMembers();
    }
}

function updatePhase(phase) {
    const phases = ['query', 'judge', 'done'];
    const map = { querying: 0, judging: 1, done: 2 };
    const current = map[phase] ?? -1;

    phases.forEach((p, i) => {
        const dot = document.getElementById('dot-' + (p === 'query' ? 'query' : p === 'judge' ? 'judge' : 'done'));
        dot.className = 'phase-dot' + (i < current ? ' done' : i === current ? ' active' : '');
    });
}

// ── Render results ──
function renderResults(s) {
    const area = document.getElementById('responsesArea');

    // Sort: winner first, then by score
    const sorted = [...s.responses].sort((a, b) => {
        if (a.name === s.winner) return -1;
        if (b.name === s.winner) return 1;
        return (b.score || 0) - (a.score || 0);
    });

    area.innerHTML = '<div class="responses-grid">' + sorted.map(r => {
        const isWinner = r.name === s.winner;
        const scoreVal = r.score || 0;
        const scoreClass = scoreVal > 0 ? 'positive' : scoreVal < 0 ? 'negative' : 'neutral';

        return `<div class="response-card ${isWinner ? 'winner-card' : ''}">
            <div class="resp-header">
                <span class="resp-name">
                    ${r.name}
                    ${isWinner ? '<span class="winner-badge">★ Winner</span>' : ''}
                </span>
                <div class="resp-meta">
                    <span>${r.model}</span>
                    <span>${r.time}s</span>
                    <span class="round-score ${scoreClass}">${scoreVal >= 0 ? '+' : ''}${scoreVal}</span>
                </div>
            </div>
            <div class="resp-body">${escapeHtml(r.answer)}</div>
        </div>`;
    }).join('') + '</div>';

    // Verdict
    if (s.verdict) {
        document.getElementById('verdictArea').innerHTML = `
            <div class="verdict-panel">
                <h3>Council's Synthesized Answer</h3>
                <div class="verdict-text">${escapeHtml(s.verdict)}</div>
            </div>`;
    }
}

function escapeHtml(t) {
    const d = document.createElement('div');
    d.textContent = t;
    return d.innerHTML;
}

// ── Actions ──
async function killMember(name) {
    if (!confirm(`Kill ${name}?`)) return;
    await fetch('/api/kill', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
    });
    loadMembers();
}

async function spawnMember() {
    const res = await fetch('/api/spawn', { method: 'POST' });
    const data = await res.json();
    if (data.error) alert(data.error);
    loadMembers();
}

async function purgeWorst() {
    if (!confirm('Kill the lowest-ranked member and replace them?')) return;
    await fetch('/api/purge', { method: 'POST' });
    loadMembers();
}

async function showGraveyard() {
    const res = await fetch('/api/graveyard');
    const data = await res.json();
    const list = document.getElementById('graveyardList');

    if (data.length === 0) {
        list.innerHTML = '<p style="color:var(--text-dim);font-size:0.75rem;">No one has died yet.</p>';
    } else {
        list.innerHTML = data.map(g => `
            <div class="grave-entry">
                <div class="grave-name">☠ ${g.name} (${g.model})</div>
                <div>Score: ${g.final_score?.toFixed(1) || 0} | Rounds: ${g.total_rounds} | Wins: ${g.total_wins}</div>
                <div class="grave-cause">${g.cause_of_death}</div>
            </div>
        `).join('');
    }
    document.getElementById('graveyardModal').classList.add('visible');
}

function closeGraveyard() {
    document.getElementById('graveyardModal').classList.remove('visible');
}

// ── Init ──
loadMembers();
setInterval(loadMembers, 15000);
</script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/members')
def api_members():
    return jsonify(get_alive_members())


@app.route('/api/state')
def api_state():
    with state_lock:
        return jsonify(council_state)


@app.route('/api/ask', methods=['POST'])
def api_ask():
    data = request.json
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400
    if council_state["busy"]:
        return jsonify({"error": "Council is busy"}), 429

    thread = threading.Thread(target=run_council_round, args=(question,), daemon=True)
    thread.start()
    return jsonify({"status": "started"})


@app.route('/api/kill', methods=['POST'])
def api_kill():
    name = request.json.get("name")
    members = get_alive_members()
    if len(members) <= MIN_COUNCIL_SIZE:
        return jsonify({"error": "Council at minimum size"})
    kill_member(name, cause="executed by council leader")
    return jsonify({"status": "killed", "name": name})


@app.route('/api/spawn', methods=['POST'])
def api_spawn():
    new, err = spawn_member()
    if err:
        return jsonify({"error": err})
    return jsonify({"status": "spawned", "member": new})


@app.route('/api/purge', methods=['POST'])
def api_purge():
    members = get_alive_members()
    if len(members) <= MIN_COUNCIL_SIZE:
        return jsonify({"error": "Council at minimum size"})
    worst = members[-1]
    kill_member(worst["name"], cause="purged: lowest ranked")
    new, err = spawn_member()
    return jsonify({"killed": worst["name"], "spawned": new["name"] if new else None})


@app.route('/api/graveyard')
def api_graveyard():
    return jsonify(get_graveyard_list())


if __name__ == '__main__':
    init_db()
    print("\n  ╔════════════════════════════════════════════╗")
    print("  ║     THE COUNCIL v2.0 — Web Interface       ║")
    print("  ║     Open http://localhost:5000              ║")
    print("  ╚════════════════════════════════════════════╝\n")
    app.run(host=WEB_HOST, port=WEB_PORT, debug=False)
