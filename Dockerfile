FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md requirements.txt wsgi.py ./
COPY src ./src
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY migrations ./migrations
COPY deploy ./deploy

EXPOSE 8000

CMD ["gunicorn", "--config", "deploy/gunicorn.conf.py", "wsgi:app"]
