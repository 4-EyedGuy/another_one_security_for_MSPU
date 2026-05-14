FROM python:3.10-slim

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/storage && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app/storage

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]