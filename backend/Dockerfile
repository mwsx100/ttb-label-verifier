FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y tesseract-ocr && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV TESSERACT_CMD=/usr/bin/tesseract

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]