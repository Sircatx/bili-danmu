FROM python:3.11-slim
ENV TZ=Asia/Shanghai
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates tzdata && \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && echo "Asia/Shanghai" > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
        bilibili-api-python aiohttp
COPY danmu.py /app/danmu.py
WORKDIR /app
CMD ["python", "danmu.py"]
