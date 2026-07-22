# B站弹幕采集 - 交接文档 (HANDOFF)

> 完整运维手册，记录部署细节、凭据、常见操作，防止后期遗忘。
> 最后更新：2026-07-23（重大架构变更：docker手动容器 → systemd服务；GitHub → Gitee；容器时区 UTC → UTC+8）

## 一、系统概览

在 Home Assistant 主机上用 **systemd 托管的 Docker 容器**采集 B站直播弹幕，日志自动推送到 **Gitee 私有仓库**（国内直连，不依赖电脑代理，电脑关机也能推），通过 HA 仪表盘控制。

```
HA 仪表盘 (开关 + 房间号输入框 + 切换按钮)
   │
   ├─ command_line switch ──SSH──▶ 宿主机 systemctl start/stop danmu.service
   │        state = systemctl is-active danmu.service（value=="active"）
   │
   └─ script.danmu_switch_room ──SSH──▶ 宿主机 改 danmu.service 的 DANMU_ROOM
   │                                     → daemon-reload → systemctl restart
   │
   └─ systemd danmu.service（容器 danmu_capture）──每小时──▶ git push 到 Gitee sircatx/bili-danmu-logs
```

> ⚠️ **2026-07-23 架构迁移要点**（旧文档描述的 `danmu_capture` 手动容器 / GitHub / danmu-switch.sh 均已废弃）：
> - 采集不再用手动 `docker run`，改由 **systemd 服务 `danmu.service`** 托管（开机自启 + `Restart=always`），容器名固定 `danmu_capture`。
> - 日志仓从 GitHub 迁到 **Gitee**（`sircatx/bili-danmu-logs`），HA 盒子直连 Gitee，**电脑关机/代理没开都能推**。代码仓 `bili-danmu` 仍在 GitHub（推代码需电脑走代理）。
> - 容器加 `TZ=Asia/Shanghai`，弹幕时间戳/文件名日期改用北京时间（旧的 UTC 历史日志已 +8h 修正）。

## 二、主机与凭据

| 项目 | 值 |
|---|---|
| HA 主机 IP | `192.168.1.3` |
| 系统 SSH | `root` / `Aa112211.`（注意结尾有点） |
| HA 网络模式 | host（容器内可 `ssh root@127.0.0.1`） |
| 架构 | aarch64（ophub Armbian） |
| 总内存 | 1.8 GiB（HA 自身约用 480-500 MiB，弹幕采集约 62 MiB） |

> ⚠️ SSH 用 paramiko（execute_code），不要用 terminal 工具的 ssh（HA 主机握手慢会超时）。

### Terminal & SSH 加载项（HA 官方 add-on）

| 项目 | 值 |
|---|---|
| Add-on slug | `core_ssh` |
| 版本 | 10.3.0 |
| 登录用户 | `root` |
| 密码 | `0216....` |
| 开机自启 | 已开启（boot: auto） |
| 外部端口转发 | 关闭（tcp_forwarding: false，仅走 HA 网页 Web Terminal / Ingress） |

安装/配置方法（通过 hassio_cli 容器的 ha CLI + Supervisor API）：
```bash
# 安装
docker exec hassio_cli ha apps install core_ssh
# 设置密码（ha CLI 无 --options，必须走 Supervisor REST API）
docker exec hassio_cli sh -c 'curl -s -X POST \
  -H "Authorization: Bearer $SUPERVISOR_TOKEN" -H "Content-Type: application/json" \
  -d "{\"options\": {\"password\": \"0216....\", \"authorized_keys\": [], \"apks\": [], \"server\": {\"tcp_forwarding\": false}}}" \
  http://supervisor/addons/core_ssh/options'
# 启动 / 重启
docker exec hassio_cli ha apps restart core_ssh
```

## 三、容器与镜像（systemd 托管）

| 项目 | 值 |
|---|---|
| **托管方式** | **systemd 服务 `danmu.service`**（`/etc/systemd/system/danmu.service`），开机自启 + `Restart=always` |
| 容器名 | `danmu_capture`（中性名，与房间号无关；换房间不改容器名） |
| 镜像 | `danmu:latest`（python:3.11-slim + git + ca-certificates + tzdata + 清华源） |
| 镜像源码 | `/opt/danmu/`（Dockerfile + danmu.py），改后 `cd /opt/danmu && docker build -t danmu:latest .` |
| 数据挂载 | `-v /usr/share/hassio/share/danmu:/data` |
| 当前房间号 | 3282568（改 `danmu.service` 的 `DANMU_ROOM=` 切换） |
| 凭据环境文件 | `/opt/danmu/gitee.env`（权限 600，仅 root 可读；含 GITHUB_TOKEN 等） |

### systemd 服务操作
```bash
systemctl status danmu.service        # 状态
systemctl restart danmu.service       # 重启
journalctl -u danmu.service -n 30     # 日志
# 改房间号：改 DANMU_ROOM 后必须 daemon-reload + restart
sed -i 's/DANMU_ROOM=.*/DANMU_ROOM=12345/' /etc/systemd/system/danmu.service
systemctl daemon-reload && systemctl restart danmu.service
```

### 环境变量（在 /opt/danmu/gitee.env + danmu.service）

| 变量 | 说明 | 值 |
|---|---|---|
| `DANMU_ROOM` | 房间号（在 danmu.service 里） | 3282568 |
| `ROOM_ID` | 容器内房间号（由 DANMU_ROOM 传入） | - |
| `TZ` | 时区 | `Asia/Shanghai`（UTC+8）|
| `WORKDIR` | 数据目录 | `/data` |
| `GITHUB_TOKEN` | Gitee 令牌（变量名沿用，实为 Gitee token） | 见 gitee.env |
| `GITHUB_REPO` | 日志仓库 | `sircatx/bili-danmu-logs` |
| `GITHUB_BRANCH` | 分支 | `main` |
| `GIT_HOST` | 托管平台 | `gitee.com` |
| `GIT_USER` | Gitee 用户名（URL 鉴权用） | `sircatx` |
| `PUSH_INTERVAL` | 推送间隔（秒） | `3600`（1小时）|
| `SESSDATA` | B站登录凭据 | 见下 |

> SESSDATA 优先读环境变量，其次读 `/data/.sessdata` 文件（扫码登录写入）。
> danmu.py 的 `github_remote()` 按 `GIT_HOST` 自动选 URL 格式：Gitee 用 `用户名:令牌@`，GitHub 用 `x-access-token:令牌@`。

## 四、日志仓库

| 项目 | 值 |
|---|---|
| 仓库 | **Gitee** `sircatx/bili-danmu-logs`（私有） |
| 查看 | https://gitee.com/sircatx/bili-danmu-logs/tree/main/ |
| 目录结构 | `房间号_<房间号>/<年>/<月>/<年-月-日>.log` |
| 记录格式 | `[北京时间] 用户名(UID): 弹幕内容`（含弹幕/礼物/上舰） |
| 推送频率 | 每 1 小时（`PUSH_INTERVAL=3600`） |

> ✅ **为什么用 Gitee**：GitHub 被墙，从 HA 盒子推需走电脑代理中继（`clash-lan-proxy.py`），**电脑一关机就推不上**。Gitee 国内直连，HA 盒子独立推送，彻底摆脱对电脑的依赖。
> ⚠️ 凭据安全：`.sessdata` 曾误推日志仓，已强推清除。`git_setup()` 自动写 `/data/.gitignore` 排除 `.sessdata`、`*.png`、`bilibili_login.py`、`_tz_backup_*/`。

## 五、常见操作

### 切换房间
仪表盘填新房间号点"切换"，或 SSH 执行：
```bash
sed -i 's/DANMU_ROOM=.*/DANMU_ROOM=12345/' /etc/systemd/system/danmu.service
systemctl daemon-reload && systemctl restart danmu.service
```

### 扫码登录（获取完整用户名）
默认匿名连接用户名会打码。扫码登录后显示完整用户名：
```bash
docker exec -it danmu_capture python bilibili_login.py --qr-file /data/bili_qr.png
```
扫码成功后 SESSDATA 自动写入 `/data/.sessdata`，重启服务生效。

### 查看采集状态
```bash
systemctl status danmu.service
docker logs danmu_capture --tail 20
docker stats danmu_capture --no-stream        # 内存/CPU
```

### 检查房间是否在直播
房间不开播就没有弹幕（正常现象）。检查：
```bash
docker exec danmu_capture python3 -c "from bilibili_api import live,sync; sync(live.LiveRoom(3282568).get_room_play_info())"
# live_status: 0=未开播 1=直播中 2=轮播
```

## 六、登录状态监控

`danmu_login_check.py`（部署在 Hermes scripts 目录）每天检测 SESSDATA 有效性，失效双通道推送（Bark + 回逍）。

- Cron：每天 10:00（no_agent 模式，有效时静默）
- 触发推送：`INVALID`（过期）/ `NO_SESSDATA`（无凭据）/ 容器连不上
- 推送内容带重新扫码命令

## 七、文件清单

| 文件 | 说明 |
|---|---|
| `danmu.py` | 采集主脚本（SESSDATA 环境变量→文件回退、三层目录、定时 push） |
| `bilibili_login.py` | 扫码登录（login_v2.QrCodeLogin），写 `/data/.sessdata` |
| `danmu-switch.sh` | ⚠️ 已废弃（旧 docker 架构）。切房间改用 systemd 的 DANMU_ROOM |
| `danmu_login_check.py` | 登录状态检测（部署到 Hermes scripts/，脱敏版在仓库） |
| `Dockerfile` | 镜像构建（清华源 deb822 + git + qrcode[pil]） |
| `requirements.txt` | bilibili-api-python, aiohttp, websocket-client, qrcode[pil] |

## 八、踩坑记录

- **储存模式仪表盘只在 Core 启动读一次磁盘**：直接改 `.storage/lovelace.<name>` 磁盘文件前端看不到（内存是旧的），要用 WS API `lovelace/config/save`（`url_path=<dashboard>`）写内存，立即生效。
- **HA 控制指向旧容器全失效**：迁 systemd 后，开关/切房间脚本原本指向已不存在的 `danmu_capture`，导致开关显示 off、按钮无效。改 configuration.yaml 的 command_line/shell_command 全部指向 `systemctl ... danmu.service`（state 用 `is-active`，value_template `== "active"`）；command_line 平台改动需**重启 Core** 才生效（不支持热重载）。
- **容器默认 UTC 时区**：弹幕时间戳/文件名日期慢 8 小时。修复：docker run 加 `-e TZ=Asia/Shanghai` + Dockerfile 装 `tzdata`。历史 UTC 日志用脚本 +8h 修正并按日期重新归档（跨天的并入次日文件、排序）。
- **新建 Gitee 仓库中文描述乱码**：`curl -d` 传中文编码坏。用 Python `urllib` form-urlencode(utf-8) PATCH `repos/{owner}/{repo}` 修 description。
- **镜像缺 git 崩溃**：重建镜像若 Dockerfile 没装 git，`git_setup()` 报 `FileNotFoundError: 'git'`。Dockerfile 必须 `apt-get install git`。
- **GitHub push 依赖电脑代理**：HA 盒子推 GitHub 需 `clash-lan-proxy.py` 中继（192.168.1.4:7898），电脑关机就断。已迁 Gitee 解决。代码仓推 GitHub 用 `git -c http.proxy=http://127.0.0.1:7897 push`（MSYS bash 默认不走代理）。
- **僵尸容器**：切换房间偶尔残留旧容器。systemd 的 `ExecStartPre=-docker rm -f` 已自动清理。
- **QrCodeLoginEvents**：枚举名是 `TIMEOUT` 不是 `EXPIRED`；二维码用 `login.get_qrcode_picture()` + `pic.to_file()`。
- **ha CLI 无 --options**：add-on 配置走 Supervisor REST API（`http://supervisor/addons/<slug>/options`）。
