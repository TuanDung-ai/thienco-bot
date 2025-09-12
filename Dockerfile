FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Tạo user không phải root
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER appuser

ENV PORT=8080

# Gunicorn: 2 workers, 8 threads (I/O bound), phù hợp webhook
CMD ["bash","-lc","exec gunicorn app:app -w ${WEB_CONCURRENCY:-1} -k gthread --threads ${THREADS:-8} -b :${PORT} --timeout 120 --keep-alive 5"]
