# ============================================================
# THE COUNCIL — Configuration
# ============================================================
# 1. Copy this file:  cp config.example.py config.py
# 2. Edit config.py with YOUR values
# 3. Never commit config.py (it's in .gitignore)
# ============================================================

# Your Ollama endpoints — replace with your actual IPs
PC1 = "http://localhost:11434"          # The PC running the council script
PC2 = "http://192.168.1.100:11434"     # Your second PC — CHANGE THIS

# All models available on each PC
# Run `ollama list` on each PC to see what you have installed
AVAILABLE_MODELS = {
    PC1: [
        "qwen2.5:7b-instruct",
        "dolphin-mistral:7b",
        "deepseek-r1:8b",
    ],
    PC2: [
        "mistral:7b-instruct",
        "llama3.1:8b",
        "phi4-mini",
        "qwen2.5:14b-instruct-q4_K_M",
    ],
}

# Models tagged as "heavy" — slower but smarter
HEAVY_MODELS = ["qwen2.5:14b-instruct-q4_K_M"]

# Which model judges the council (should be your most reliable model)
JUDGE_URL = PC1
JUDGE_MODEL = "qwen2.5:7b-instruct"

# Council rules
MIN_COUNCIL_SIZE = 3            # Never go below this many members
MAX_COUNCIL_SIZE = 12           # Never exceed this many members
KILL_THRESHOLD = -3             # Score below which a member gets auto-killed
ROUNDS_BEFORE_KILL_CHECK = 5    # Protection rounds for new members
MUTATION_CHANCE = 0.3           # Probability of personality mutation after each round (0.0 - 1.0)
SCORE_DECAY = 0.95              # Scores decay by this factor each round

# Web UI settings
WEB_HOST = "0.0.0.0"           # 0.0.0.0 = accessible from network, 127.0.0.1 = local only
WEB_PORT = 5000
