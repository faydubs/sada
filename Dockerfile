# صورة الواجهة الخلفية (FastAPI) — مهيّأة لـ Hugging Face Spaces (Docker SDK)
FROM python:3.12-slim

# مكتبات نظام يحتاجها torch / ctranslate2(faster-whisper) / soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# HF Spaces يتطلب التشغيل بمستخدم غير جذر (uid 1000)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /home/user/app

# تثبيت torch/torchaudio من فهرس CPU أولاً (أصغر وأسرع من نسخة CUDA الافتراضية)
COPY --chown=user backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# نسخ كود الـ backend
COPY --chown=user backend/ .

# HF Spaces يتوقّع المنفذ 7860
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
