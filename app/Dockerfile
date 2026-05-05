FROM python:3.14-slim

# Install deps in a separate layer that only invalidates when requirements.txt
# changes — code edits no longer rebuild pip install.
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user. Avoids running the app as root in the container.
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --chown=app:app . .

USER app

EXPOSE 8000

# Container-level liveness signal. depends_on: condition: service_healthy in
# docker-compose can wait for this instead of just process startup.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/').read()" || exit 1

CMD ["python", "main.py"]
