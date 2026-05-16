FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY corpus/ corpus/
COPY sdk/ sdk/

RUN pip install --no-cache-dir -e . -e sdk/python

ENV CORPUS_HOST=0.0.0.0
ENV CORPUS_PORT=8000
ENV CORPUS_DB_PATH=/data/corpus.db

VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "corpus.server:app", \
     "--host", "0.0.0.0", "--port", "8000"]
