ARG BUILD_FROM
FROM $BUILD_FROM

# 最小化构建：只复制文件，不装任何包，不拉网络。
# pip 依赖在 run.sh 第一次启动时装（运行时网络正常可装）。
COPY danmu.py /app/danmu.py
COPY run.sh /run.sh
RUN chmod a+x /run.sh

WORKDIR /app
CMD ["/run.sh"]