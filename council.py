"""
THE COUNCIL v2.0 — Evolving AI Council System
=============================================
An AI council that evolves over time. Members compete, get scored,
mutate personalities, and the worst performers get replaced.

Usage:
    python council.py                  # Start interactive mode
    python council.py --status         # Show current council standings
    python council.py --purge          # Kill lowest-ranked member immediately
    python council.py --add            # Add a new council member
    python council.py --remove NAME    # Remove a specific member
    python council.py --reset          # Reset all scores and history
"""

import requests
import json
import concurrent.futures
import time
import sys
import os
import random
import sqlite3
import argparse
from datetime import datetime

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

# Database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "council.db")

# ============================================================
# PERSONALITY GENERATOR
# ============================================================

# Building blocks for generating random personalities
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
    "a philosopher-king who balances wisdom with decisive action",
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
    "Judge", "Kite", "Lore", "Myth", "Null", "Omega", "Pyre", "Quest",
]


def generate_personality():
    """Generate a random unique personality."""
    archetype = random.choice(ARCHETYPES)
    style = random.choice(COMMUNICATION_STYLES)
    return (
        f"You are {archetype}. {style} "
        f"Keep your answers concise but thorough — 2-4 paragraphs max. "
        f"Never introduce yourself or state your role. Just answer the question."
    )


def mutate_personality(current_personality):
    """Slightly alter an existing personality to evolve it."""
    mutations = [
        "You've become more aggressive and direct in your opinions.",
        "You've grown more thoughtful and now consider more perspectives before answering.",
        "You've developed a sharper sense of humor that you weave into your analysis.",
        "You've become more concise — you now say more with fewer words.",
        "You've started backing up your claims with more concrete examples.",
        "You've become bolder in your contrarian takes.",
        "You've developed a talent for finding practical, actionable solutions.",
        "You've started seeing patterns others miss and pointing them out.",
        "You now challenge the question itself before answering it.",
        "You've become more willing to say 'I don't know' when uncertain.",
    ]
    mutation = random.choice(mutations)
    return current_personality + f" EVOLUTION: {mutation}"


def pick_random_name(existing_names):
    """Pick a name not already in use."""
    available = [n for n in NAME_POOL if n not in existing_names]
    if not available:
        return f"Agent-{random.randint(1000, 9999)}"
    return random.choice(available)


def pick_random_model():
    """Pick a random model and its URL from available models."""
    url = random.choice(list(AVAILABLE_MODELS.keys()))
    model = random.choice(AVAILABLE_MODELS[url])
    return url, model


# ============================================================
# DATABASE
# ============================================================

def init_db():
    """Create the database and tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS members (
            name TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            model TEXT NOT NULL,
            personality TEXT NOT NULL,
            score REAL DEFAULT 0.0,
            wins INTEGER DEFAULT 0,
            rounds INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            alive INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            question TEXT,
            winner_name TEXT,
            member_scores TEXT,
            event_type TEXT DEFAULT 'round'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS graveyard (
            name TEXT,
            model TEXT,
            personality TEXT,
            final_score REAL,
            total_rounds INTEGER,
            total_wins INTEGER,
            cause_of_death TEXT,
            died_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

    # Seed initial council if empty
    c.execute("SELECT COUNT(*) FROM members WHERE alive = 1")
    if c.fetchone()[0] == 0:
        seed_council(conn)

    conn.close()


def seed_council(conn):
    """Create the initial council members."""
    c = conn.cursor()
    existing = []

    initial_members = [
        ("Oracle", PC1, "qwen2.5:7b-instruct"),
        ("Maverick", PC1, "dolphin-mistral:7b"),
        ("Sentinel", PC1, "deepseek-r1:8b"),
        ("Scholar", PC2, "mistral:7b-instruct"),
        ("Spark", PC2, "llama3.1:8b"),
        ("Phoenix", PC2, "phi4-mini"),
    ]

    for name, url, model in initial_members:
        personality = generate_personality()
        c.execute(
            "INSERT OR IGNORE INTO members (name, url, model, personality) VALUES (?, ?, ?, ?)",
            (name, url, model, personality)
        )
        existing.append(name)

    conn.commit()


def get_alive_members():
    """Get all living council members."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, url, model, personality, score, wins, rounds FROM members WHERE alive = 1 ORDER BY score DESC")
    rows = c.fetchall()
    conn.close()
    return [
        {
            "name": r[0], "url": r[1], "model": r[2], "personality": r[3],
            "score": r[4], "wins": r[5], "rounds": r[6]
        }
        for r in rows
    ]


def update_member_after_round(name, won, score_delta):
    """Update a member's stats after a round."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Apply score decay to everyone first (done once per round in the main loop)
    c.execute(
        "UPDATE members SET score = score + ?, wins = wins + ?, rounds = rounds + 1 WHERE name = ?",
        (score_delta, 1 if won else 0, name)
    )
    conn.commit()
    conn.close()


def apply_score_decay():
    """Decay all scores slightly to prevent runaway leaders."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE members SET score = score * ? WHERE alive = 1", (SCORE_DECAY,))
    conn.commit()
    conn.close()


def maybe_mutate_personality(name):
    """Randomly mutate a member's personality."""
    if random.random() > MUTATION_CHANCE:
        return False

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT personality FROM members WHERE name = ?", (name,))
    row = c.fetchone()
    if row:
        new_personality = mutate_personality(row[0])
        # Keep personality from growing too long — truncate evolution history
        if len(new_personality) > 1500:
            new_personality = generate_personality() + " REBORN: This personality was regenerated from scratch."
        c.execute("UPDATE members SET personality = ? WHERE name = ?", (new_personality, name))
    conn.commit()
    conn.close()
    return True


def kill_member(name, cause="auto-killed: score too low"):
    """Kill a council member and send them to the graveyard."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT model, personality, score, rounds, wins FROM members WHERE name = ?", (name,))
    row = c.fetchone()
    if row:
        c.execute(
            "INSERT INTO graveyard (name, model, personality, final_score, total_rounds, total_wins, cause_of_death) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, row[0], row[1], row[2], row[3], row[4], cause)
        )
        c.execute("UPDATE members SET alive = 0 WHERE name = ?", (name,))

    conn.commit()
    conn.close()


def spawn_member(name=None):
    """Create a new council member with random personality."""
    members = get_alive_members()
    existing_names = [m["name"] for m in members]

    if len(members) >= MAX_COUNCIL_SIZE:
        return None, "Council is full."

    if name is None:
        name = pick_random_name(existing_names)
    elif name in existing_names:
        return None, f"{name} already exists."

    url, model = pick_random_model()
    personality = generate_personality()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO members (name, url, model, personality) VALUES (?, ?, ?, ?)",
        (name, url, model, personality)
    )
    conn.commit()
    conn.close()

    return {"name": name, "url": url, "model": model}, None


def auto_kill_check():
    """Check if any members should be killed and replaced."""
    members = get_alive_members()
    killed = []
    spawned = []

    for m in members:
        if m["rounds"] < ROUNDS_BEFORE_KILL_CHECK:
            continue
        if m["score"] < KILL_THRESHOLD and len(members) - len(killed) > MIN_COUNCIL_SIZE:
            kill_member(m["name"])
            killed.append(m["name"])

    # Replace killed members
    for _ in killed:
        new_member, err = spawn_member()
        if new_member:
            spawned.append(new_member["name"])

    return killed, spawned


def log_round(question, winner_name, member_scores):
    """Log a round to the history database."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO history (question, winner_name, member_scores, event_type) VALUES (?, ?, ?, ?)",
        (question, winner_name, json.dumps(member_scores), "round")
    )
    conn.commit()
    conn.close()


def get_graveyard():
    """Get all dead council members."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, model, final_score, total_rounds, total_wins, cause_of_death, died_at FROM graveyard ORDER BY died_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows


def get_history_stats():
    """Get round history stats."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM history WHERE event_type = 'round'")
    total_rounds = c.fetchone()[0]
    c.execute("SELECT winner_name, COUNT(*) as cnt FROM history WHERE event_type = 'round' GROUP BY winner_name ORDER BY cnt DESC LIMIT 5")
    top_winners = c.fetchall()
    conn.close()
    return total_rounds, top_winners


# ============================================================
# CORE ENGINE
# ============================================================

def query_member(member, question):
    """Send a question to one council member."""
    try:
        start = time.time()
        resp = requests.post(
            f"{member['url']}/api/chat",
            json={
                "model": member["model"],
                "messages": [
                    {"role": "system", "content": member["personality"]},
                    {"role": "user", "content": question}
                ],
                "stream": False,
                "options": {"num_predict": 512}
            },
            timeout=180
        )
        elapsed = round(time.time() - start, 1)
        data = resp.json()
        answer = data["message"]["content"]
        return {
            "name": member["name"],
            "model": member["model"],
            "answer": answer,
            "time": elapsed,
            "online": True
        }
    except Exception as e:
        return {
            "name": member["name"],
            "model": member["model"],
            "answer": f"[OFFLINE: {e}]",
            "time": 0,
            "online": False
        }


def judge_answers(question, answers):
    """
    Have the judge score ALL members (not just pick a winner).
    Returns a dict of {name: score} and a summary.
    """
    online_answers = [a for a in answers if a["online"]]
    if not online_answers:
        return {}, "No council members responded."

    prompt = f'Question asked: "{question}"\n\nCouncil member responses:\n\n'
    for a in online_answers:
        prompt += f'=== {a["name"]} ===\n{a["answer"]}\n\n'

    prompt += (
        f"You are the Judge. Score EACH council member from -2 to +3 based on:\n"
        f"- Accuracy and correctness\n"
        f"- Helpfulness and actionability\n"
        f"- Quality of reasoning\n"
        f"- Originality and insight\n\n"
        f"Respond in this EXACT format (one line per member, then a summary):\n"
        f"SCORES:\n"
    )
    for a in online_answers:
        prompt += f"{a['name']}: [score]\n"
    prompt += (
        f"\nWINNER: [name of the best one]\n"
        f"SUMMARY: [A combined best answer in 2-3 paragraphs, synthesizing the best insights from all members]"
    )

    try:
        resp = requests.post(
            f"{JUDGE_URL}/api/chat",
            json={
                "model": JUDGE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_predict": 1024}
            },
            timeout=180
        )
        result = resp.json()["message"]["content"]

        # Parse scores from the response
        scores = {}
        winner = None
        for line in result.split("\n"):
            line = line.strip()
            # Try to parse "Name: score" lines
            for a in online_answers:
                if line.startswith(a["name"]):
                    try:
                        score_str = line.split(":")[-1].strip()
                        # Extract number from possible formats like "+2", "2", "2/3", etc.
                        score_str = score_str.replace("+", "").split("/")[0].split(" ")[0]
                        score = float(score_str)
                        score = max(-2, min(3, score))  # Clamp
                        scores[a["name"]] = score
                    except (ValueError, IndexError):
                        scores[a["name"]] = 0

            if line.startswith("WINNER:"):
                winner = line.replace("WINNER:", "").strip()

        # Anyone not scored gets 0
        for a in online_answers:
            if a["name"] not in scores:
                scores[a["name"]] = 0

        # Offline members get penalized
        for a in answers:
            if not a["online"]:
                scores[a["name"]] = -1

        return scores, result

    except Exception as e:
        return {a["name"]: 0 for a in answers}, f"[Judge failed: {e}]"


def run_round(question):
    """Execute a full council round: query, judge, score, evolve."""
    members = get_alive_members()

    if not members:
        print("  No council members alive. Use --add to spawn some.")
        return

    print(f"\n  {'='*60}")
    print(f"  QUESTION: {question}")
    print(f"  {'='*60}")
    print(f"\n  Consulting {len(members)} council members...\n")

    # Query all members in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as executor:
        futures = {
            executor.submit(query_member, m, question): m
            for m in members
        }
        answers = []
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            status = "OK" if result["online"] else "OFFLINE"
            print(f"  >> {result['name']:12s} responded ({result['time']:5.1f}s) [{status}]")
            answers.append(result)

    # Show each answer
    for a in answers:
        print(f"\n  {'─'*55}")
        score_info = ""
        member_data = next((m for m in members if m["name"] == a["name"]), None)
        if member_data:
            score_info = f" | Career: {member_data['score']:+.1f} pts, {member_data['wins']}W/{member_data['rounds']}R"
        print(f"  {a['name']} ({a['model']}){score_info}")
        print(f"  {'─'*55}")
        preview = a["answer"][:500]
        if len(a["answer"]) > 500:
            preview += "..."
        for line in preview.split("\n"):
            print(f"  {line}")

    # Judge
    print(f"\n  {'='*60}")
    print(f"  JUDGING...")
    print(f"  {'='*60}\n")

    scores, verdict = judge_answers(question, answers)

    # Find winner
    winner_name = max(scores, key=scores.get) if scores else None

    # Display scores
    print(f"  Round scores:")
    for name, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        marker = " ★ WINNER" if name == winner_name else ""
        print(f"    {name:12s}: {score:+.0f}{marker}")

    # Apply scores to database
    apply_score_decay()
    for name, score in scores.items():
        won = (name == winner_name)
        update_member_after_round(name, won, score)

    # Log the round
    log_round(question, winner_name, scores)

    # Print the judge's summary (extract just the SUMMARY part)
    summary_start = verdict.find("SUMMARY:")
    if summary_start != -1:
        summary = verdict[summary_start + 8:].strip()
        print(f"\n  {'─'*55}")
        print(f"  COUNCIL'S ANSWER:")
        print(f"  {'─'*55}")
        for line in summary.split("\n"):
            print(f"  {line}")

    # Mutate personalities
    mutated = []
    for a in answers:
        if a["online"] and maybe_mutate_personality(a["name"]):
            mutated.append(a["name"])
    if mutated:
        print(f"\n  ⟳ Personalities evolved: {', '.join(mutated)}")

    # Auto-kill check
    killed, spawned = auto_kill_check()
    if killed:
        print(f"\n  ☠ KILLED for poor performance: {', '.join(killed)}")
    if spawned:
        print(f"  ★ NEW members spawned: {', '.join(spawned)}")

    print(f"\n  {'='*60}\n")


# ============================================================
# DISPLAY
# ============================================================

def show_status():
    """Display current council standings."""
    members = get_alive_members()
    total_rounds, top_winners = get_history_stats()
    graveyard = get_graveyard()

    print(f"\n  {'='*60}")
    print(f"  THE COUNCIL — STATUS REPORT")
    print(f"  Total rounds played: {total_rounds}")
    print(f"  {'='*60}\n")

    print(f"  ACTIVE MEMBERS ({len(members)}):")
    print(f"  {'─'*55}")
    print(f"  {'Name':12s} {'Model':24s} {'Score':>7s} {'W/R':>7s} {'Win%':>6s}")
    print(f"  {'─'*55}")

    for m in members:
        win_pct = f"{(m['wins']/m['rounds']*100):.0f}%" if m['rounds'] > 0 else "—"
        wr = f"{m['wins']}/{m['rounds']}"
        protected = " (new)" if m['rounds'] < ROUNDS_BEFORE_KILL_CHECK else ""
        danger = " ⚠" if m['score'] < KILL_THRESHOLD * 0.5 and m['rounds'] >= ROUNDS_BEFORE_KILL_CHECK else ""
        print(f"  {m['name']:12s} {m['model']:24s} {m['score']:+7.1f} {wr:>7s} {win_pct:>6s}{protected}{danger}")

    if graveyard:
        print(f"\n  GRAVEYARD ({len(graveyard)} fallen):")
        print(f"  {'─'*55}")
        for g in graveyard[:10]:
            print(f"  ☠ {g[0]:12s} {g[1]:20s} score:{g[2]:+.1f}  rounds:{g[3]}  cause: {g[5]}")

    if top_winners:
        print(f"\n  ALL-TIME TOP WINNERS:")
        print(f"  {'─'*55}")
        for name, count in top_winners:
            print(f"    {name:12s}: {count} wins")

    print(f"\n  {'='*60}\n")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="The Council v2.0 — Evolving AI Council")
    parser.add_argument("--status", action="store_true", help="Show council standings")
    parser.add_argument("--purge", action="store_true", help="Kill the lowest-ranked member")
    parser.add_argument("--add", nargs="?", const="__random__", default=None, metavar="NAME",
                        help="Add a new member (random name if none given)")
    parser.add_argument("--remove", metavar="NAME", help="Remove a specific member")
    parser.add_argument("--reset", action="store_true", help="Reset all scores and history")
    parser.add_argument("--graveyard", action="store_true", help="Show the graveyard")
    args = parser.parse_args()

    init_db()

    if args.status:
        show_status()
        return

    if args.graveyard:
        graveyard = get_graveyard()
        if not graveyard:
            print("\n  The graveyard is empty. No one has died yet.\n")
        else:
            print(f"\n  {'='*60}")
            print(f"  THE GRAVEYARD")
            print(f"  {'='*60}\n")
            for g in graveyard:
                print(f"  ☠ {g[0]:12s} | {g[1]:20s} | score: {g[2]:+.1f} | {g[3]} rounds | {g[4]} wins")
                print(f"    Cause: {g[5]}")
                print(f"    Died: {g[6]}")
                print()
        return

    if args.purge:
        members = get_alive_members()
        if len(members) <= MIN_COUNCIL_SIZE:
            print(f"\n  Can't purge — council is at minimum size ({MIN_COUNCIL_SIZE}).\n")
            return
        worst = members[-1]  # Already sorted by score DESC
        kill_member(worst["name"], cause="manually purged by council leader")
        new, err = spawn_member()
        print(f"\n  ☠ Purged: {worst['name']} (score: {worst['score']:+.1f})")
        if new:
            print(f"  ★ Replaced with: {new['name']} ({new['model']})")
        print()
        return

    if args.add is not None:
        name = None if args.add == "__random__" else args.add
        new, err = spawn_member(name)
        if err:
            print(f"\n  Error: {err}\n")
        else:
            print(f"\n  ★ Spawned: {new['name']} ({new['model']})")
            print(f"    They have {ROUNDS_BEFORE_KILL_CHECK} rounds of protection before they can be killed.\n")
        return

    if args.remove:
        members = get_alive_members()
        target = next((m for m in members if m["name"].lower() == args.remove.lower()), None)
        if not target:
            print(f"\n  No active member named '{args.remove}'. Current members:")
            for m in members:
                print(f"    - {m['name']}")
            print()
            return
        if len(members) <= MIN_COUNCIL_SIZE:
            print(f"\n  Can't remove — council is at minimum size ({MIN_COUNCIL_SIZE}).\n")
            return
        kill_member(target["name"], cause=f"manually removed by council leader")
        print(f"\n  ☠ Removed: {target['name']} (score: {target['score']:+.1f})\n")
        return

    if args.reset:
        confirm = input("\n  This will reset ALL scores, history, and the graveyard. Type 'yes' to confirm: ")
        if confirm.strip().lower() == "yes":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM history")
            c.execute("DELETE FROM graveyard")
            c.execute("DELETE FROM members")
            conn.commit()
            conn.close()
            init_db()
            print("  Council has been reset.\n")
        else:
            print("  Cancelled.\n")
        return

    # ── Interactive mode ──
    print()
    print("  ╔════════════════════════════════════════════════════════╗")
    print("  ║           THE COUNCIL v2.0 — EVOLVING AI              ║")
    print("  ╠════════════════════════════════════════════════════════╣")
    print("  ║  Members compete, evolve, and the weak get replaced.  ║")
    print("  ║                                                        ║")
    print("  ║  Commands:                                             ║")
    print("  ║    /status     — show standings                        ║")
    print("  ║    /add [name] — add a new member                      ║")
    print("  ║    /remove name — remove a member                      ║")
    print("  ║    /purge      — kill the worst performer              ║")
    print("  ║    /graveyard  — see the fallen                        ║")
    print("  ║    /quit       — exit                                  ║")
    print("  ╚════════════════════════════════════════════════════════╝")

    members = get_alive_members()
    print(f"\n  Council has {len(members)} active members:")
    for m in members:
        print(f"    {m['name']:12s} ({m['model']})")
    print()

    while True:
        try:
            user_input = input("  You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Council dismissed.")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            cmd = user_input.split()
            if cmd[0] == "/quit" or cmd[0] == "/exit":
                print("\n  Council dismissed.")
                break
            elif cmd[0] == "/status":
                show_status()
            elif cmd[0] == "/graveyard":
                graveyard = get_graveyard()
                if not graveyard:
                    print("\n  The graveyard is empty.\n")
                else:
                    for g in graveyard[:10]:
                        print(f"  ☠ {g[0]:12s} score:{g[2]:+.1f} rounds:{g[3]} cause: {g[5]}")
                    print()
            elif cmd[0] == "/purge":
                members = get_alive_members()
                if len(members) <= MIN_COUNCIL_SIZE:
                    print(f"\n  Can't purge — at minimum size.\n")
                else:
                    worst = members[-1]
                    kill_member(worst["name"], cause="purged by council leader")
                    new, err = spawn_member()
                    print(f"\n  ☠ Purged: {worst['name']} (score: {worst['score']:+.1f})")
                    if new:
                        print(f"  ★ Replaced: {new['name']} ({new['model']})\n")
            elif cmd[0] == "/add":
                name = cmd[1] if len(cmd) > 1 else None
                new, err = spawn_member(name)
                if err:
                    print(f"\n  {err}\n")
                else:
                    print(f"\n  ★ Spawned: {new['name']} ({new['model']})\n")
            elif cmd[0] == "/remove":
                if len(cmd) < 2:
                    print("\n  Usage: /remove NAME\n")
                else:
                    members = get_alive_members()
                    target = next((m for m in members if m["name"].lower() == cmd[1].lower()), None)
                    if not target:
                        print(f"\n  No member named '{cmd[1]}'.\n")
                    elif len(members) <= MIN_COUNCIL_SIZE:
                        print(f"\n  Can't remove — at minimum size.\n")
                    else:
                        kill_member(target["name"], cause="manually removed")
                        print(f"\n  ☠ Removed: {target['name']}\n")
            else:
                print(f"\n  Unknown command: {cmd[0]}\n")
            continue

        # It's a question — run a round
        run_round(user_input)


if __name__ == "__main__":
    main()
