import os

DB_PATH: str = os.environ.get("CORPUS_DB_PATH", "corpus.db")
HOST: str = os.environ.get("CORPUS_HOST", "0.0.0.0")
PORT: int = int(os.environ.get("CORPUS_PORT", "8000"))
VERSION: str = "0.1.0"
LOG_LEVEL: str = os.environ.get("CORPUS_LOG_LEVEL", "INFO")
