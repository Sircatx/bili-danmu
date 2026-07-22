# B站弹幕采集 - 交接文档 (HANDOFF)

> 完整运维手册，记录部署细节、凭据、常见操作，防止后期遗忘。
> 最后更新：2026-07-22

## 一、系统概览

在 Home Assistant 主机上用独立 Docker 容器采集 B站直播弹幕，日志自动推送到 GitHub 私有仓库，通过 HA 仪表盘控制。

```
HA 仪表盘 (开关 + 房间号输入框 + 切换按钮)
   │
   ├─ command_line switch ──SSH──▶ 宿主机 docker start/stop danmu_capture
   │
   └─ script.danmu_switch_room ──SSH──▶ 宿主机 /root/danmu-switch.sh <房间号>
                                          └─ 停旧容器 → 用新 ROOM_ID 重建
   │
   └─ danmu_capture 容器 ──每小时──▶ git push 到 Sircatx/bili-danmu-logs
```

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

## 三、容器与镜像

| 项目 | 值 |
|---|---|
| 容器名 | `danmu_capture`（统一命名，不绑房间号） |
| 镜像 | `danmu:latest`（python:3.12-slim + git + 清华源 deb822 + qrcode[pil]） |
| 数据挂载 | `-v /usr/share/hassio/share/danmu:/data` |
| 重启策略 | `--restart unless-stopped` |
| 当前房间号 | 3780806（默认，可仪表盘切换） |

### 环境变量

| 变量 | 说明 | 默认 |
|---|---|---|
| `ROOM_ID` | 房间号 | 必填 |
| `WORKDIR` | 数据目录 | `/data` |
| `GITHUB_TOKEN` | GitHub Token | - |
| `GITHUB_REPO` | 日志仓库 `Sircatx/bili-danmu-logs` | - |
| `GITHUB_BRANCH` | 分支 | `main` |
| `PUSH_INTERVAL` | 推送间隔（秒） | `3600` |
| `SESSDATA` | B站登录凭据 | 见下 |

> SESSDATA 优先读环境变量，其次读 `/data/.sessdata` 文件（扫码登录写入）。

## 四、日志仓库

| 项目 | 值 |
|---|---|
| 仓库 | `Sircatx/bili-danmu-logs`（私有） |
| 查看 | https://github.com/Sircatx/bili-danmu-logs/tree/main/ |
| 目录结构 | `房间号_<房间号>/<年>/<月>/<年-月-日>.log` |
| 记录格式 | `[时间] 用户名(UID): 弹幕内容`（含弹幕/礼物/上舰） |

> ⚠️ 凭据安全：`.sessdata` 曾误推到日志仓库，已用重建历史强推清除。`danmu.py` 的 `git_setup()` 现在自动写 `/data/.gitignore` 排除 `.sessdata`、`*.png`、`bilibili_login.py`。

## 五、常见操作

### 切换房间
仪表盘填新房间号点"切换"，或 SSH 执行：
```bash
/root/danmu-switch.sh 12345
```

### 扫码登录（获取完整用户名）
默认匿名连接用户名会打码。扫码登录后显示完整用户名：
```bash
docker exec -it danmu_capture python bilibili_login.py --qr-file /data/bili_qr.png
# 二维码保存到 /data/bili_qr.png，可通过 HA www 目录或 SFTP 取出扫码
```
扫码成功后 SESSDATA 自动写入 `/data/.sessdata`，重启容器生效。

### 查看采集状态
```bash
docker logs danmu_capture --tail 20
docker stats danmu_capture --no-stream        # 内存/CPU
docker exec danmu_capture tail -f /data/房间号_<ID>/<年>/<月>/<日>.log
```

### 检查房间是否在直播
房间不开播就没有弹幕（正常现象）。检查：
```bash
docker exec danmu_capture python3 -c "from bilibili_api import live,sync; sync(live.LiveRoom(3780806).get_room_play_info())"
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
| `danmu-switch.sh` | 切换房间脚本（部署到宿主机 /root/） |
| `danmu_login_check.py` | 登录状态检测（部署到 Hermes scripts/，脱敏版在仓库） |
| `Dockerfile` | 镜像构建（清华源 deb822 + git + qrcode[pil]） |
| `requirements.txt` | bilibili-api-python, aiohttp, websocket-client, qrcode[pil] |

## 八、踩坑记录

- **僵尸容器**：切换房间偶尔残留旧容器（如 `danmu_5540720`），白占内存。切换脚本已 `docker rm`，若再现手动 `docker rm -f <名>`。
- **Dockerfile COPY 语法**：`COPY danmu.py bilibili_login.py ./`（结尾必须 `./` 不能 `.`）。
- **清华源**：Debian trixie 用 deb822 格式 `/etc/apt/sources.list.d/debian.sources`，改后 `--no-cache` 重建才生效。
- **QrCodeLoginEvents**：枚举名是 `TIMEOUT` 不是 `EXPIRED`；二维码图片用 `login.get_qrcode_picture()` + `pic.to_file()`。
- **GitHub push 从 HA 主机慢**：TLS 偶尔中断，重试即可；SSH 命令加 nohup 后台执行避免超时。
- **ha CLI 无 --options**：add-on 配置必须走 Supervisor REST API（`http://supervisor/addons/<slug>/options`）。
