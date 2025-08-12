# syntax=docker/dockerfile:1

FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8080

# Entrypoint
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080"]


