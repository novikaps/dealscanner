"""
Settings for the local deal screener.

Everything here points at THIS computer. The AI model runs inside Ollama on
localhost, so the CIM text never leaves the machine.
"""

# Where Ollama listens. local_llm.py refuses to run if this is not localhost.
OLLAMA_URL = "http://localhost:11434"

# Default model. The app lists every model you have pulled, so you can pick
# a bigger one if your laptop has the memory (see README).
DEFAULT_MODEL = "qwen3:8b"

# Model settings
TEMPERATURE = 0.1        # low = factual, repeatable output
NUM_CTX = 8192           # context window (tokens) the model is given per call
REQUEST_TIMEOUT = 900    # seconds; local models can be slow on long chunks

# How much CIM text goes into one extraction call (characters, ~4 per token)
CHUNK_CHARS = 9000

# Pages with less text than this are skipped (cover pages, dividers, images)
MIN_PAGE_CHARS = 80

# Where finished reports are saved
OUTPUT_DIR = "reports"
