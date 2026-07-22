# B站弹幕采集

基于 Docker 的 B站直播弹幕自动采集工具，由 **systemd 托管**部署在 Home Assistant 主机上，弹幕日志自动推送到 **Gitee 私有仓库**，通过 HA 仪表盘控制。

> 📋 完整运维手册（凭据、部署细节、常见操作、踩坑记录）见 [HANDOFF.md](HANDOFF.md)。

## 功能

- 实时采集 B站直播弹幕（含弹幕、礼物、上舰）
- 弹幕日志自动推送到 **Gitee 私有仓库**（国内直连，不依赖电脑代理，电脑关机也能推）
- HA 仪表盘：开关控制启停 + 输入房间号一键切换
- 扫码登录获取完整用户名（可选）
- 每小时自动推送一次
- 时间戳为**北京时间**（UTC+8），每天一个日志文件

## HA 仪表盘

侧边栏 **B站弹幕** 仪表盘：

- **弹幕采集控制** 开关 — 启停采集（对接 systemd 服务，状态实时反映）
- **房间号** 输入框 + **切换** 按钮 — 填新房间号点切换即可换直播间
- **使用说明** — 含 Gitee 日志查看链接

## 架构

```
HA 仪表盘 (switch + input_text + button)
   │
   ├─ command_line switch ──SSH──▶ 宿主机 systemctl start/stop danmu.service
   │        state = systemctl is-active danmu.service（value=="active"）
   │
   └─ script.danmu_switch_room ──SSH──▶ 宿主机 改 danmu.service 的 DANMU_ROOM
   │                                     → daemon-reload → systemctl restart
   │
   └─ systemd danmu.service（容器 danmu_5540720）──每小时──▶ git push 到 Gitee
```

采集由 **systemd 服务 `danmu.service`** 托管（开机自启 + `Restart=always`），容器名固定 `danmu_5540720`，房间号通过服务里的 `DANMU_ROOM` 环境变量传入。

## 查看弹幕日志

[bili-danmu-logs @ Gitee](https://gitee.com/sircatx/bili-danmu-logs/tree/main/)

- 目录结构：`房间号_<房间号>/<年>/<月>/<年-月-日>.log`（每天一个文件）
- 记录格式：`[北京时间] 用户名(UID): 弹幕内容`

## 扫码登录（获取完整用户名）

默认匿名连接，用户名会打码。扫码登录后显示完整用户名：

```bash
docker exec -it danmu_5540720 python bilibili_login.py --qr-file /data/bili_qr.png
```

扫码成功后 SESSDATA 自动写入 `/data/.sessdata`，重启服务生效。
`.sessdata` 已在 `.gitignore` 中，不会被推送到远程仓库。

## 环境变量

| 变量 | 说明 | 值 |
|---|---|---|
| `ROOM_ID` | B站直播间房间号（由 systemd 的 `DANMU_ROOM` 传入） | 必填 |
| `TZ` | 时区 | `Asia/Shanghai`（UTC+8） |
| `WORKDIR` | 数据目录 | `/data` |
| `GITHUB_TOKEN` | 推送令牌（变量名沿用，实为 Gitee token） | - |
| `GITHUB_REPO` | 日志仓库 | `sircatx/bili-danmu-logs` |
| `GITHUB_BRANCH` | 分支 | `main` |
| `GIT_HOST` | 托管平台（`gitee.com` / `github.com`） | `gitee.com` |
| `GIT_USER` | Gitee 用户名（URL 鉴权用） | `sircatx` |
| `PUSH_INTERVAL` | 推送间隔（秒） | `3600`（1小时） |
| `SESSDATA` | B站登录凭据（环境变量） | - |

> - SESSDATA 优先从环境变量读取，其次从 `$WORKDIR/.sessdata` 文件读取（扫码登录自动写入）。
> - `github_remote()` 按 `GIT_HOST` 自动选 URL 鉴权格式：Gitee 用 `用户名:令牌@`，GitHub 用 `x-access-token:令牌@`。

## 部署（systemd）

1. 构建镜像（Dockerfile 含 git + tzdata + 清华源）：

```bash
cd /opt/danmu && docker build -t danmu:latest .
```

2. 凭据环境文件 `/opt/danmu/gitee.env`（权限 600）：

```ini
GITHUB_TOKEN=<gitee_token>
GITHUB_REPO=sircatx/bili-danmu-logs
GITHUB_BRANCH=main
GIT_HOST=gitee.com
GIT_USER=sircatx
PUSH_INTERVAL=3600
```

3. systemd 服务 `/etc/systemd/system/danmu.service`（节选）：

```ini
[Service]
Restart=always
RestartSec=10
Environment=DANMU_ROOM=3282568
EnvironmentFile=/opt/danmu/gitee.env
ExecStartPre=-/usr/bin/docker rm -f danmu_5540720
ExecStart=/usr/bin/docker run --rm --name danmu_5540720 \
  -e ROOM_ID=${DANMU_ROOM} -e TZ=Asia/Shanghai -e WORKDIR=/data \
  -e GITHUB_TOKEN=${GITHUB_TOKEN} -e GITHUB_REPO=${GITHUB_REPO} \
  -e GITHUB_BRANCH=${GITHUB_BRANCH} -e GIT_HOST=${GIT_HOST} \
  -e GIT_USER=${GIT_USER} -e PUSH_INTERVAL=${PUSH_INTERVAL} \
  -v /usr/share/hassio/share/danmu:/data danmu:latest
```

4. 启用：

```bash
systemctl daemon-reload && systemctl enable --now danmu.service
```

### 切换房间

```bash
sed -i 's/DANMU_ROOM=.*/DANMU_ROOM=12345/' /etc/systemd/system/danmu.service
systemctl daemon-reload && systemctl restart danmu.service
```

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
| `CONTAINER` | 容器名 | `danmu_5540720` |

建议用 cron 每天检查一次（如 `0 10 * * *`）。
