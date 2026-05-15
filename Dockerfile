# Cliente Moodle quiz — imagen mínima para ejecutar moodle_quiz.py
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY moodle_quiz.py .

ENTRYPOINT ["python", "moodle_quiz.py"]
CMD ["fetch", "--config", "/app/config.json"]
