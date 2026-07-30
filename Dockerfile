FROM python:3.12-alpine3.23

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HSP_DISPATCH_SERVICE_LOG_DIR=/app/logs

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup -S app \
    && adduser -S -G app app \
    && mkdir -p /app/logs \
    && chown app:app /app/logs

COPY --chown=app:app . .

USER app

EXPOSE 8080
EXPOSE 50051

CMD ["python", "-m", "hsp_dispatch_service.main"]
