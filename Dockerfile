FROM python:3.11.9-slim-bookworm

WORKDIR /app

# Install dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Health check (matches echo_env pattern — pure Python, no curl needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" || exit 1

# HF Spaces expects port 7860; openenv.yaml declares port: 7860
EXPOSE 7860

# Entry point matches openenv.yaml app: server:app
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
