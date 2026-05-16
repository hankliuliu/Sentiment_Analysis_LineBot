FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.5.1 --extra-index-url https://download.pytorch.org/whl/cpu
RUN grep -v torch requirements.txt | pip install --no-cache-dir -r /dev/stdin
COPY . .
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "--timeout", "120", "--access-logfile", "/app/logs/access.log", "--error-logfile", "/app/logs/error.log", "webhook:app"]
