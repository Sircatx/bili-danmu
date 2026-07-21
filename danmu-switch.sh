#!/bin/bash
# 切换 B站弹幕采集房间号
# 用法: danmu-switch.sh <房间号>
# 部署位置: HA 宿主机 /root/danmu-switch.sh
ROOM_ID="$1"
if [ -z "$ROOM_ID" ]; then
  echo "usage: danmu-switch.sh <room_id>"
  exit 1
fi
docker stop danmu_capture 2>/dev/null
docker rm danmu_capture 2>/dev/null
docker run -d \
  --name danmu_capture \
  --restart unless-stopped \
  -e ROOM_ID="$ROOM_ID" \
  -e WORKDIR=/data \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e GITHUB_REPO=Sircatx/bili-danmu-logs \
  -e GITHUB_BRANCH=main \
  -e PUSH_INTERVAL=3600 \
  -v /usr/share/hassio/share/danmu:/data \
  danmu:latest
echo "switched to room $ROOM_ID"
