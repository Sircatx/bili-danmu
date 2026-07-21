# 把弹幕采集挂到 Koyeb（免费 · 免绑卡 · 永不休眠）

目标：云端 24/7 抓取某个直播间弹幕，弹幕日志自动 push 到你的 **GitHub 私有仓库**，
换电脑 `git pull` 就能看，容器重启也不丢。

## 为什么是 Koyeb + GitHub

- Koyeb 免费 nano 实例（512MB / 0.1vCPU，部分资料写 256MB）足够弹幕脚本用，
  **免绑卡**（你已注册成功即说明免费档可用），且 **永不休眠**，比 HuggingFace 更适合常驻采集。
- Koyeb 从 **GitHub 仓库**直接拉 Dockerfile 构建部署，所以 GitHub 一举两得：
  既当代码源，又当弹幕日志仓库。
- 弹幕脚本是后台任务，用 Koyeb 的 **Worker 类型**部署，不暴露公网端口，更安全。

## 一、准备 GitHub 仓库（两个，别混）

1. **代码仓库**（给 Koyeb 部署用）
   新建公开或私有仓库，例如 `bili-danmu`。把本项目三个文件放进去：
   `danmu.py` / `Dockerfile` / `requirements.txt`。

2. **日志仓库**（只存弹幕，私有！）
   新建**私有**仓库，例如 `bili-danmu-logs`。弹幕会定时 push 到这里。
   ⚠️ 日志仓库必须和代码仓库分开——否则弹幕每 5 分钟 push 一次会触发 Koyeb 反复重新部署。

3. **生成 GitHub 令牌**（给脚本 push 日志用）
   GitHub → 右上头像 → Settings → Developer settings →
   Personal access tokens → Tokens (classic) → Generate new token：
   - Expiration 按需要选（建议 90 天或 No expiration）
   - 勾选 `repo`（完整仓库读写权限）
   - 生成后**复制令牌**（只显示一次）

## 二、把代码推到代码仓库

```powershell
cd C:\Project\bilibili-danmu-capture
git init -q 2>$null
git remote add origin https://github.com/你的名/bili-danmu.git
git add danmu.py Dockerfile requirements.txt
git commit -m "deploy danmu capture"
git push -u origin main
```
> 首次 push 需输入 GitHub 账号密码；密码处粘贴上面生成的令牌（或 GitHub 已启用的话用 Personal Access Token 登录）。

## 三、在 Koyeb 部署

1. 打开 Koyeb 控制台（app.koyeb.com），首次会提示连接 GitHub，授权访问你的仓库。
2. 点 **Create Web Service**（或 Create Service）→ 选 **GitHub** 部署方式。
3. 选你的代码仓库 `bili-danmu`、分支 `main`。
4. Builder 选 **Dockerfile**（仓库里已有）。
5. **Instance type** 选 **nano**（免费档）。
6. **Service type** 选 **Worker**（后台任务，不暴露公网）。
7. Scaling 设 **Min instances = 1**（保证常驻，不缩到 0）。
8. **Environment variables** 添加：
   | 名称 | 值 | 说明 |
   |---|---|---|
   | `ROOM_ID` | `6` | 要抓的直播间房间号 |
   | `GITHUB_TOKEN` | 你的令牌 | 点 🔒 存为 **Secret**（加密，不在日志显示） |
   | `GITHUB_REPO` | `你的名/bili-danmu-logs` | 第一步建的日志仓库 |
   | `GITHUB_BRANCH` | `main` | 日志仓库默认分支 |
   | `PUSH_INTERVAL` | `300` | 多少秒推送一次（可选，默认 300；想少丢可改 120） |
9. 点 **Deploy**。Koyeb 会自动构建镜像并启动容器。

## 四、看实时 / 看历史

- **实时弹幕**：Koyeb 服务页面 → **Logs** 标签，能看到脚本 `print` 的弹幕流。
- **历史弹幕**：换电脑
  ```powershell
  git clone https://github.com/你的名/bili-danmu-logs.git
  cd bili-danmu-logs
  notepad data/danmu_6.log        # 或 VS Code 打开
  ```
  也可直接在 GitHub 网页打开 `bili-danmu-logs` 仓库的 `data/danmu_房间号.log`。

## 五、改房间 / 重启 / 维护

- 改房间：Koyeb 服务 Settings 里改 `ROOM_ID` 环境变量 → 容器自动重启重连。
- 改代码：本地改完 `git push` 到代码仓 → Koyeb 自动重新部署（Autodeploy）。
- 看推送是否成功：Logs 里搜 `已推送弹幕到 GitHub`；若报 `push 失败` 多为令牌权限/仓库名错。

## 六、注意事项

- Koyeb 免费实例**磁盘是临时的**，容器重启/重建时本地 `data/` 会丢——但弹幕已 push 到 GitHub，
  启动会先 `pull` 续传，所以不丢。
- 若 Koyeb 在两次 push 之间重启，那一个间隔内的弹幕只存本地会丢；把 `PUSH_INTERVAL` 调小可减损。
- 若 Koyeb 提示需要绑卡才能部署，说明免费档在你地区需验证；可退回 HuggingFace Spaces（见旧方案）或 Oracle（绑卡）。
- 弹幕是私人数据，日志仓库务必设**私有**。
