FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home relay
COPY --chown=relay:relay relay ./relay
USER relay
CMD ["sh", "-c", "exec uvicorn relay.app:default_app --factory --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
