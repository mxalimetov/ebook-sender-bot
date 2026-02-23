FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY requirements.txt ./
RUN uv pip install --system -r requirements.txt

COPY ebook_sender ./ebook_sender

ENV PYTHONPATH=/app/ebook_sender

CMD ["python", "-m", "ebook_sender"]
