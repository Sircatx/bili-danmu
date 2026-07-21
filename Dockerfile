FROM python:3.12-slim

WORKDIR /app

# 系统 git，用于把弹幕同步到 GitHub 私有仓库
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY danmu.py .

# Koyeb Worker 类型不暴露公网端口；脚本内部仍起一个 HTTP 健康检查 server（无害）。
# 若用 Web 类型，Koyeb 会注入 PORT，脚本监听它做 /health 探测。
CMD ["python", "danmu.py"]
