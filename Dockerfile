FROM python:3.12-slim

WORKDIR /app

# 换清华源加速 + 装 git（Debian trixie deb822 格式）
RUN sed -i 's|http://deb.debian.org/debian|https://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources \
    && sed -i 's|http://deb.debian.org/debian-security|https://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY danmu.py bilibili_login.py ./

# Koyeb Worker 类型不暴露公网端口；脚本内部仍起一个 HTTP 健康检查 server（无害）。
# 若用 Web 类型，Koyeb 会注入 PORT，脚本监听它做 /health 探测。
CMD ["python", "danmu.py"]
