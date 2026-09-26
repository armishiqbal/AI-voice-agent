FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 API_HOST=0.0.0.0
WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir './backend[providers,local-rag,voice-openai,voice-deepgram,voice-fish,voice-elevenlabs,google,telephony,ingestion]' \
    && useradd --create-home --uid 10001 awaaz
COPY run.py worker.py ./
COPY evals/ ./evals/
COPY scripts/ ./scripts/
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist/
RUN mkdir -p /app/artifacts && chown -R awaaz:awaaz /app
USER awaaz
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["python", "run.py"]
