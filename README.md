# Bilibili 直播间弹幕采集

基于 `bilibili-api-python` 的弹幕监控脚本，反爬签名和 cookie 由库自动处理。
**挂云端（免费 · 免绑卡 · 日志发 Gitee）见 `README_deploy.md`。**

## 安装依赖

```powershell
cd C:\Project\bilibili-danmu-capture
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
```

## 运行

```powershell
.\venv\Scripts\python danmu.py 房间号
```

示例：监控 B站官方直播（房间 6）

```powershell
.\venv\Scripts\python danmu.py 6
```

## 输出

- 控制台实时打印弹幕
- 弹幕追加写入 `data/danmu_房间号.log`
- 按 `Ctrl+C` 停止

## 房间号怎么找

打开直播间，URL 里长串数字就是房间号，例如：
`https://live.bilibili.com/6`

房间号 = `6`。

## 自定义

想监听更多事件（礼物、上舰等），在 `danmu.py` 里加 `@room.on("事件名")` 即可。
