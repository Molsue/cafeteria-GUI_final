FROM python:3.10-alpine

WORKDIR /app

COPY generator.py .
COPY config/ ./config/

RUN mkdir -p output

ENV OUTPUT_DIR=/app/output
ENV PYTHONUNBUFFERED=1

CMD ["python3", "generator.py", "--interval", "30"]
