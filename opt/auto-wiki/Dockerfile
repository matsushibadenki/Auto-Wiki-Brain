# src/Dockerfile
# Python環境の構築
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python libraries
RUN pip install --no-cache-dir \
    mwclient \
    openai \
    chromadb \
    duckduckgo-search \
    feedparser \
    schedule \
    fastapi \
    uvicorn \
    sentence-transformers \
    mwxml \
    pytrends \
    psutil \
    jinja2 \
    python-multipart

# Copy source code
COPY src/ /app/src/

# Set Python path
ENV PYTHONPATH=/app