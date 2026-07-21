#!/usr/bin/with-contenv bashio
# ==============================================================================
# Bilibili 弹幕采集 add-on 启动器
# 从 HA 界面选项读取配置，支持多房间（逗号分隔），弹幕写到 /share/danmu/
# ==============================================================================
set -e

ROOM_IDS=$(bashio::config 'room_ids')
PUSH_INTERVAL=$(bashio::config 'push_interval')
GITHUB_REPO=$(bashio::config 'github_repo')
GITHUB_TOKEN=$(bashio::config 'github_token')
GITHUB_BRANCH=$(bashio::config 'github_branch')

# 弹幕落到 /share/danmu —— 通过 Samba \\HA\share\danmu 可直接查看
export WORKDIR="/share/danmu"
export PUSH_INTERVAL="${PUSH_INTERVAL:-300}"
export GITHUB_REPO="${GITHUB_REPO}"
export GITHUB_TOKEN="${GITHUB_TOKEN}"
export GITHUB_BRANCH="${GITHUB_BRANCH:-main}"

mkdir -p "${WORKDIR}"

bashio::log.info "弹幕采集启动：房间=[${ROOM_IDS}] 日志目录=${WORKDIR} 推送间隔=${PUSH_INTERVAL}s"
if bashio::var.has_value "${GITHUB_REPO}"; then
    bashio::log.info "GitHub 同步已启用 -> ${GITHUB_REPO}@${GITHUB_BRANCH}"
else
    bashio::log.info "GitHub 同步未配置（仅本地 /share，够用）。"
fi

# 优雅退出：转发信号给所有子进程
pids=()
term() {
    bashio::log.info "收到停止信号，正在结束子进程..."
    for p in "${pids[@]}"; do kill -TERM "$p" 2>/dev/null || true; done
    wait
    exit 0
}
trap term SIGTERM SIGINT

# 逗号分隔的多房间，各起一个进程
IFS=',' read -ra ROOMS <<< "${ROOM_IDS}"
for raw in "${ROOMS[@]}"; do
    room="$(echo "$raw" | tr -d '[:space:]')"
    [ -z "$room" ] && continue
    bashio::log.info "启动房间 ${room} 采集..."
    ROOM_ID="$room" PORT=0 python3 -u /app/danmu.py "$room" &
    pids+=($!)
done

if [ "${#pids[@]}" -eq 0 ]; then
    bashio::log.error "没有有效房间号，请在加载项配置里填写 room_ids"
    exit 1
fi

# 任一子进程退出即整体退出，交给 Supervisor 重启
wait -n
bashio::log.warning "有采集进程退出，触发整体重启。"
term
