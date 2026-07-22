#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bilibili 直播间弹幕采集（云端版，基于 bilibili-api-python）

部署目标：Koyeb Worker（免费 nano 实例，免绑卡，从 GitHub 仓库部署）
弹幕日志：定时 git push 到你的 GitHub 私有仓库，换电脑 git pull 即可看，
          容器重启也不丢（每次启动先 pull 续传，停止前最后 push 一次）。

配置（全部环境变量）：
  ROOM_ID        要抓的直播间房间号（默认 6，也可用命令行参数）
  PORT           HTTP 健康检查端口（默认 7860，worker 类型可忽略）
  WORKDIR        弹幕本地暂存目录（默认 data）
  GITHUB_TOKEN   GitHub 私人令牌（需 repo 权限），建议放 Koyeb Secret
  GITHUB_REPO    日志仓库 owner/repo（与代码仓库分开，避免触发重新部署）
  GITHUB_BRANCH  日志仓库分支（默认 main）
  PUSH_INTERVAL  多少秒推送一次（默认 300）

本地用法（可选）：
    python danmu.py 房间号
"""
import os
import sys
import subprocess
import threading
import signal
from datetime import datetime

from bilibili_api import live, sync

# ---------- 配置（环境变量）----------
ROOM_ID = int(os.environ.get("ROOM_ID", sys.argv[1] if len(sys.argv) > 1 else 6))
PORT = int(os.environ.get("PORT", "7860"))
WORKDIR = os.environ.get("WORKDIR", "data")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")        # 形如 owner/repo
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
# Git 托管平台：默认 gitee.com（国内直连，HA 盒子不依赖电脑代理，电脑关机也能推）。
# 也可设 github.com（但被墙，需容器走代理）。
GIT_HOST = os.environ.get("GIT_HOST", "gitee.com")
GIT_USER = os.environ.get("GIT_USER", "sircatx")       # Gitee 用户名（URL 鉴权用）
PUSH_INTERVAL = int(os.environ.get("PUSH_INTERVAL", "300"))
SESSDATA = os.environ.get("SESSDATA", "")  # 可选：B站登录凭据，设置后可获取完整用户名（不匿名）

# 如果环境变量没配 SESSDATA，尝试从文件读取（扫码登录脚本写入）
if not SESSDATA:
    _sessdata_file = os.path.join(WORKDIR, ".sessdata")
    if os.path.exists(_sessdata_file):
        with open(_sessdata_file, "r") as f:
            SESSDATA = f.read().strip()
        if SESSDATA:
            print(f"[config] 从 {_sessdata_file} 读取到 SESSDATA")

os.makedirs(WORKDIR, exist_ok=True)

# 弹幕日志按 房间号/年/月/年-月-日 分类：<WORKDIR>/房间号_<房间号>/<YYYY>/<MM>/<YYYY-MM-DD>.log
LOG_SUBDIR = os.path.join(WORKDIR, f"房间号_{ROOM_ID}")
os.makedirs(LOG_SUBDIR, exist_ok=True)

def today_logfile():
    """返回当天日志文件路径（跨零点自动切换到新文件；按年/月分目录）。"""
    now = datetime.now()
    month_dir = os.path.join(LOG_SUBDIR, now.strftime("%Y"), now.strftime("%m"))
    os.makedirs(month_dir, exist_ok=True)
    return os.path.join(month_dir, f"{now:%Y-%m-%d}.log")

if SESSDATA:
    room = live.LiveDanmaku(ROOM_ID, credential=live.Credential(sessdata=SESSDATA))
    print(f"[config] 使用登录凭据连接（SESSDATA 已配置），用户名将完整显示")
else:
    room = live.LiveDanmaku(ROOM_ID)
    print(f"[config] 未配置 SESSDATA，匿名连接（用户名会被打码）")


# ---------- HTTP 健康检查（Koyeb worker 类型不暴露端口，起一个也无害）----------
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"danmu capture running, room={ROOM_ID}".encode("utf-8"))

    def log_message(self, *args):
        pass

def start_health():
    try:
        srv = HTTPServer(("0.0.0.0", PORT), HealthHandler)
        srv.serve_forever()
    except Exception as e:
        print("健康检查启动失败:", e)

threading.Thread(target=start_health, daemon=True).start()


# ---------- GitHub 同步（弹幕日志）----------
def github_remote():
    # 用 token 作为凭证嵌入 URL；此 URL 只用于 subprocess（capture_output），不打印到日志。
    # Gitee 用 "用户名:令牌@" 格式；GitHub 用 "x-access-token:令牌@" 格式。
    if "gitee" in GIT_HOST:
        return f"https://{GIT_USER}:{GITHUB_TOKEN}@{GIT_HOST}/{GITHUB_REPO}.git"
    return f"https://x-access-token:{GITHUB_TOKEN}@{GIT_HOST}/{GITHUB_REPO}.git"

def git_setup():
    if not (GITHUB_REPO and GITHUB_TOKEN):
        print("[git] 未配置 GITHUB_REPO/GITHUB_TOKEN，仅本地记录弹幕（容器重启会丢）。")
        return False
    # 写入 .gitignore，排除凭据和临时文件（只推送弹幕日志）
    gitignore_path = os.path.join(WORKDIR, ".gitignore")
    with open(gitignore_path, "w", encoding="utf-8") as gf:
        gf.write(".sessdata\n*.png\nbilibili_login.py\n__pycache__/\n*.pyc\n")
    # 原地 init（不用 clone，避免 WORKDIR 非空时 clone 报 "destination not empty"），
    # 再 fetch + checkout 拉取历史弹幕，实现容器重启续传。幂等：重复调用安全。
    subprocess.run(["git", "-C", WORKDIR, "init", "-q"], capture_output=True)
    subprocess.run(["git", "-C", WORKDIR, "config", "user.email", "danmu@bot"],
                   capture_output=True)
    subprocess.run(["git", "-C", WORKDIR, "config", "user.name", "danmu-bot"],
                   capture_output=True)
    # 设置/更新 remote（token 轮换后也能生效）
    r = subprocess.run(["git", "-C", WORKDIR, "remote", "set-url", "origin", github_remote()],
                       capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["git", "-C", WORKDIR, "remote", "add", "origin", github_remote()],
                       capture_output=True)
    # 拉取远端历史（若远端已有该分支）
    f = subprocess.run(["git", "-C", WORKDIR, "fetch", "-q", "origin", GITHUB_BRANCH],
                       capture_output=True, text=True)
    if f.returncode == 0:
        # 用远端分支为基线，保留本地未提交的新弹幕文件
        subprocess.run(["git", "-C", WORKDIR, "checkout", "-B", GITHUB_BRANCH,
                        f"origin/{GITHUB_BRANCH}"], capture_output=True)
        print(f"[git] 已拉取远端 {GITHUB_REPO}@{GITHUB_BRANCH}（续传历史弹幕）")
    else:
        subprocess.run(["git", "-C", WORKDIR, "checkout", "-B", GITHUB_BRANCH],
                       capture_output=True)
        print(f"[git] 远端无 {GITHUB_BRANCH} 分支，将首次创建（{f.stderr.strip()[-120:]}）")
    return True

def git_push():
    if not GITHUB_REPO:
        return
    try:
        subprocess.run(["git", "-C", WORKDIR, "checkout", "-B", GITHUB_BRANCH],
                       capture_output=True)
        subprocess.run(["git", "-C", WORKDIR, "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", WORKDIR, "commit", "-m",
                        f"danmu {datetime.now():%Y-%m-%d %H:%M:%S}"],
                       capture_output=True)
        subprocess.run(["git", "-C", WORKDIR, "pull", "--rebase",
                        "origin", GITHUB_BRANCH], capture_output=True)
        p = subprocess.run(["git", "-C", WORKDIR, "push", "-u",
                           "origin", GITHUB_BRANCH], capture_output=True, text=True)
        if p.returncode == 0:
            print(f"[{datetime.now():%H:%M:%S}] 已推送弹幕到 GitHub")
        else:
            print(f"[{datetime.now():%H:%M:%S}] push 失败:", p.stderr.strip()[-200:])
    except Exception as e:
        print("git 错误:", e)

def schedule_push():
    t = threading.Timer(PUSH_INTERVAL, schedule_push)
    t.daemon = True
    t.start()
    git_push()


# ---------- 弹幕回调 ----------
def _write_log(line):
    """写入当天日志文件（按天分类，跨零点自动落到新文件）。"""
    print(line)
    with open(today_logfile(), "a", encoding="utf-8") as f:
        f.write(line + "\n")

@room.on("DANMU_MSG")
async def on_danmu(event):
    info = event["data"]["info"]
    text = info[1]
    username = info[2][1]
    uid = info[2][0]
    _write_log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {username}({uid}): {text}")

@room.on("SEND_GIFT")
async def on_gift(event):
    data = event["data"]["data"]
    _write_log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [礼物] {data.get('username', '')} 送出 {data.get('giftName', '')} x{data.get('num', 1)}")

@room.on("GUARD_BUY")
async def on_guard(event):
    data = event["data"]["data"]
    _write_log(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [上舰] {data.get('username', '')} {data.get('gift_name', '')}")


# ---------- 优雅退出（容器停止时最后推一次）----------
def handle_sig(signum, frame):
    print("收到退出信号，最后推送一次...")
    git_push()
    os._exit(0)

signal.signal(signal.SIGTERM, handle_sig)
signal.signal(signal.SIGINT, handle_sig)


if __name__ == "__main__":
    has_git = git_setup()
    if has_git:
        schedule_push()
    print(f"开始监控房间 {ROOM_ID}，按 Ctrl+C 停止。")
    sync(room.connect())
