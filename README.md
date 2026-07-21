# B站弹幕采集

基于 Docker 的 B站直播弹幕自动采集工具，部署在 Home Assistant 上。

## 功能

- 实时采集 B站直播弹幕
- 弹幕日志自动推送到 GitHub 私有仓库
- HA 开关控制采集启停
- 扫码登录获取完整用户名（可选）
- 每小时自动推送一次

## 使用

### HA 仪表盘

在 Home Assistant 侧边栏 **B站弹幕** 仪表盘中：
- 开关控制弹幕采集的启停
- 查看使用说明和弹幕日志链接

### 查看弹幕日志

[查看弹幕日志](https://github.com/Sircatx/bili-danmu-logs/tree/main/)

目录结构: `房间号/年/月/年-月-日.log`

### 扫码登录（获取完整用户名）

默认匿名连接，用户名会打码。扫码登录后显示完整用户名：

```bash
docker exec -it danmu_501 python bilibili_login.py --qr-file /data/bili_qr.png
```

扫码成功后 SESSDATA 自动写入 `/data/.sessdata`，重启容器生效。

### 环境变量

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
docker run -d \
  --name danmu_501 \
  --restart unless-stopped \
  -e ROOM_ID=501 \
  -e GITHUB_TOKEN=your_token \
  -e GITHUB_REPO=user/repo \
  -e PUSH_INTERVAL=3600 \
  -v /path/to/data:/data \
  danmu:latest
```
