"""Entry point for: python -m corpus"""
import uvicorn
from corpus.config import HOST, PORT

uvicorn.run("corpus.server:app", host=HOST, port=PORT, reload=False)
