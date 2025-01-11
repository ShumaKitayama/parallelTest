FROM python:3.9-slim

# 必要なパッケージのインストール
RUN apt-get update && apt-get install -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pythonパッケージのインストール
# redis, numpyなど必要なものはまとめて入れる
RUN pip install redis numpy

WORKDIR /app
COPY Worker.py /app/Worker.py

CMD ["python", "Worker.py"]
