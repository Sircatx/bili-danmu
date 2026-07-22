#!/usr/bin/env python3
"""
B站弹幕采集 - 登录状态检测

SSH 到 HA 主机，在 danmu_capture 容器内用 SESSDATA 调 B站接口验证登录态。
登录失效时推送提醒重新扫码。

no_agent cron 模式：登录有效时静默（return 0，无输出），
仅在失效或检测异常时推送并打印。

配置（环境变量）：
  HA_HOST      HA 主机 IP（默认 192.168.1.3）
  HA_USER      SSH 用户（默认 root）
  HA_PASS      SSH 密码（必填）
  CONTAINER    容器名（默认 danmu_capture）

推送：本脚本部署在 Hermes scripts 目录时用共享库 push_lib.push()
      （Bark + 回逍双通道）。此仓库版本用占位 push()，请按需替换。
"""
import sys
import os
import base64

HA_HOST = os.environ.get("HA_HOST", "192.168.1.3")
HA_USER = os.environ.get("HA_USER", "root")
HA_PASS = os.environ.get("HA_PASS", "")
CONTAINER = os.environ.get("CONTAINER", "danmu_capture")

# 容器内检测脚本：读 /data/.sessdata，调 check_valid()
CHECK_PY = (
    "import asyncio,os\n"
    "from bilibili_api import Credential, sync\n"
    "sess=open('/data/.sessdata').read().strip() if os.path.exists('/data/.sessdata') else ''\n"
    "async def m():\n"
    "    if not sess:\n"
    "        print('NO_SESSDATA'); return\n"
    "    c=Credential(sessdata=sess)\n"
    "    try:\n"
    "        print('VALID' if await c.check_valid() else 'INVALID')\n"
    "    except Exception as e:\n"
    "        print('ERROR',e)\n"
    "sync(m())\n"
)


def push(title, body, **kwargs):
    """推送占位实现。部署到 Hermes scripts 目录时替换为:
        from push_lib import push
    此处默认打印到 stdout。返回 (ok, reports)。
    """
    print(f"[PUSH] {title}\n{body}")
    return True, []


def ssh_check():
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HA_HOST, username=HA_USER, password=HA_PASS, timeout=10)
    b64 = base64.b64encode(CHECK_PY.encode()).decode()
    cmd = f'docker exec {CONTAINER} sh -c "echo {b64} | base64 -d | python3 -" 2>&1'
    stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode(errors="replace").strip()
    c.close()
    return out


def main():
    try:
        result = ssh_check()
    except Exception as e:
        title = "⚠️ B站弹幕采集检测失败"
        body = f"无法连接容器检测登录态：{type(e).__name__}: {e}"
        ok, reports = push(title, body, group="Hermes", level="timeSensitive")
        print(f"检测异常: {e}")
        return 1

    # 登录有效 → 静默
    if result.endswith("VALID") and not result.endswith("INVALID"):
        return 0

    # 登录失效 / 无凭据 → 推送
    cmd_hint = "重新扫码：docker exec -it danmu_capture python bilibili_login.py --qr-file /data/bili_qr.png"
    if "NO_SESSDATA" in result:
        title = "⚠️ B站弹幕采集未登录"
        body = f"容器没有 SESSDATA，弹幕用户名会被打码。\n{cmd_hint}"
    elif "INVALID" in result:
        title = "⚠️ B站弹幕登录已失效"
        body = f"SESSDATA 已过期，弹幕用户名会被打码。\n{cmd_hint}"
    else:
        title = "⚠️ B站弹幕采集检测异常"
        body = f"登录态检测返回：{result[:200]}"

    ok, reports = push(title, body, group="Hermes", level="timeSensitive")
    print(f"登录态: {result}")
    print(f"推送: {'成功' if ok else '失败'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
