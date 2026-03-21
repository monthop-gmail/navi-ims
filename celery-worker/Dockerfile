FROM python:3.12-slim

WORKDIR /app

# ติดตั้ง FFmpeg + OpenCV dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# PyTorch CPU-only (~200MB แทน ~5GB ที่มี CUDA)
# + ultralytics (YOLO) — ลงทีหลังเพื่อบังคับใช้ torch CPU
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir ultralytics==8.3.95

COPY . .

CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info", "--concurrency=4"]
