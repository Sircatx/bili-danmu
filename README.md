# B站弹幕采集

基于 Docker 的 B站直播弹幕自动采集工具，部署在 Home Assistant 上，通过 HA 仪表盘控制。

> 📋 完整运维手册（凭据、部署细节、常见操作、踩坑记录）见 [HANDOFF.md](HANDOFF.md)。


## 功能

- 实时采集 B站直播弹幕（含弹幕、礼物、上舰）
- 弹幕日志自动推送到 GitHub 私有仓库
- HA 仪表盘：开关控制启停 + 输入房间号一键切换
- 扫码登录获取完整用户名（可选）
- 每小时自动推送一次

## HA 仪表盘

侧边栏 **B站弹幕** 仪表盘：

- **弹幕采集控制** 开关 — 启停采集
- **房间号** 输入框 + **切换** 按钮 — 填新房间号点切换即可换直播间（默认房间号 `3780806`）
- **使用说明** — 含日志查看链接

## 架构

```
HA 仪表盘 (switch + input_text + button)
   │
   ├─ command_line switch ──SSH──▶ 宿主机 docker start/stop danmu_capture
   │
   └─ script.danmu_switch_room ──SSH──▶ 宿主机 /root/danmu-switch.sh <房间号>
                                          └─ 停旧容器 → 用新 ROOM_ID 重建
```

容器统一命名 `danmu_capture`，房间号通过 `ROOM_ID` 环境变量传入，切换房间不改容器名。

## 查看弹幕日志

[bili-danmu-logs](https://github.com/Sircatx/bili-danmu-logs/tree/main/)

目录结构: `房间号_<房间号>/<年>/<月>/<年-月-日>.log`

## 扫码登录（获取完整用户名）

默认匿名连接，用户名会打码。扫码登录后显示完整用户名：

```bash
docker exec -it danmu_capture python bilibili_login.py --qr-file /data/bili_qr.png
```

扫码成功后 SESSDATA 自动写入 `/data/.sessdata`，重启容器生效。
`.sessdata` 已在 `.gitignore` 中，不会被推送到 GitHub。

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `ROOM_ID` | B站直播间房间号 | 必填 |
| `WORKDIR` | 数据目录 | `/data` |
| `GITHUB_TOKEN` | GitHub Token（推送日志） | - |
| `GITHUB_REPO` | 日志仓库 | - |
| `GITHUB_BRANCH` | 分支 | `main` |
| `PUSH_INTERVAL` | 推送间隔（秒） | `300` |
| `SESSDATA` | B站登录凭据（环境变量） | - |

> SESSDATA 优先从环境变量读取，其次从 `$WORKDIR/.sessdata` 文件读取（扫码登录自动写入）。

## 部署

```bash
docker build -t danmu:latest .

docker run -d \
  --name danmu_capture \
  --restart unless-stopped \
  -e ROOM_ID=3780806 \
  -e GITHUB_TOKEN=your_token \
  -e GITHUB_REPO=user/repo \
  -e PUSH_INTERVAL=3600 \
  -v /usr/share/hassio/share/danmu:/data \
  danmu:latest
```

切换房间脚本 `danmu-switch.sh` 部署到宿主机 `/root/`，由 HA 的 script 调用。

## 登录状态监控

`danmu_login_check.py` 定期检测 SESSDATA 是否有效，失效时推送提醒重新扫码。

- **检测方式**：SSH 到 HA 主机，在容器内用 SESSDATA 调 B站接口 `check_valid()`
- **触发推送**：`INVALID`（凭据过期）/ `NO_SESSDATA`（无凭据）/ 容器连不上
- **静默逻辑**：登录有效时不打扰，仅失效时推送（适合 no_agent cron）
- **推送通道**：部署到 Hermes scripts 目录时用 `push_lib.push()`（Bark + 回逍双通道，失败重试 3 次）

配置（环境变量）：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `HA_HOST` | HA 主机 IP | `192.168.1.3` |
| `HA_USER` | SSH 用户 | `root` |
| `HA_PASS` | SSH 密码 | 必填 |
| `CONTAINER` | 容器名 | `danmu_capture` |

建议用 cron 每天检查一次（如 `0 10 * * *`）。
