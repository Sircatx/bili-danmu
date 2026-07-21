#!/usr/bin/env python3
"""
B站扫码登录 - 获取 SESSDATA

用法：
  python bilibili_login.py              # 生成二维码，终端显示
  python bilibili_login.py --qr-file qrcode.png  # 保存二维码图片

扫码成功后自动写入 /data/.sessdata（容器内）或 ./sessdata.txt（本地）
"""
import asyncio
import sys
import os
import qrcode
from bilibili_api import login_v2, sync

async def main():
    qr_file = None
    if len(sys.argv) > 2 and sys.argv[1] == '--qr-file':
        qr_file = sys.argv[2]

    print("正在生成二维码...")
    login = login_v2.QrCodeLogin()
    await login.generate_qrcode()

    # 获取二维码图片
    pic = login.get_qrcode_picture()

    if qr_file:
        # 保存到文件
        with open(qr_file, 'wb') as f:
            f.write(pic.get_bytes())
        print(f"\n二维码已保存到 {qr_file}")
        print(f"请用手机 B站 APP 扫码：{os.path.abspath(qr_file)}")
    else:
        # 保存到文件并用终端显示
        qr_path = '/tmp/bili_qrcode.png'
        with open(qr_path, 'wb') as f:
            f.write(pic.get_bytes())
        print(f"\n二维码图片已保存到 {qr_path}")

        # 终端显示 ASCII 二维码
        terminal_qr = login.get_qrcode_terminal()
        print("\n请用手机 B站 APP 扫描以下二维码：\n")
        print(terminal_qr)

    print("\n等待扫码...")
    print("（手机 B站 APP -> 我的 -> 右上角扫一扫）")

    # 轮询等待扫码
    while True:
        state = await login.check_state()
        if state == login_v2.QrCodeLoginEvents.DONE:
            print("\n✅ 扫码登录成功！")
            break
        elif state == login_v2.QrCodeLoginEvents.SCAN:
            print("📱 已扫码，请在手机上确认登录")
        elif state == login_v2.QrCodeLoginEvents.EXPIRED:
            print("\n❌ 二维码已过期，请重新运行")
            return
        await asyncio.sleep(2)

    # 获取凭据
    credential = login.get_credential()
    sessdata = credential.sessdata
    bili_jct = credential.bili_jct
    dedeuserid = credential.dedeuserid

    print(f"\n=== 获取到的凭据 ===")
    print(f"SESSDATA: {sessdata}")
    print(f"bili_jct: {bili_jct}")
    print(f"DedeUserID: {dedeuserid}")

    # 写入文件
    output_path = os.environ.get('SESSDATA_FILE', '/data/.sessdata' if os.path.isdir('/data') else 'sessdata.txt')
    with open(output_path, 'w') as f:
        f.write(sessdata)
    print(f"\n✅ SESSDATA 已写入 {output_path}")
    print(f"   重启弹幕容器即可生效（已配置 SESSDATA 环境变量读取）")

if __name__ == '__main__':
    sync(main())
