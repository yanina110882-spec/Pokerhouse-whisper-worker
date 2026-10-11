FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus ffmpeg fonts-dejavu-core tzdata time && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir Pillow==12.0.0 pypdf==6.1.1
WORKDIR /app
COPY *.py /app/
RUN useradd -m -u 10001 media-test
USER media-test
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["/usr/bin/time","-v","python","run.py"]
