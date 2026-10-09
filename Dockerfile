FROM python:3.12-slim

# No .pyc files, and print logs immediately instead of buffering them.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first: this slow layer is rebuilt only when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

# Never run the app as root inside the container.
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000
# 0.0.0.0 = listen on all interfaces inside the container, so published ports work.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
