cat > Dockerfile << 'EOF'
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install --upgrade pip && pip install -r requirements.txt
ENV PYTHONUNBUFFERED=1
CMD ["gunicorn", "-w", "1", "-b", ":8080", "app:app"]
EOF
