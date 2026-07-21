#!/usr/bin/env python3
"""B站扫码登录 - 获取 SESSDATA"""
import asyncio
import sys
import os
from bilibili_api import login_v2, sync

async def main():
    qr_file = None
    if len(sys.argv) > 2 and sys.argv[1] == '--qr-file':
        qr_file = sys.argv[2]

    print("正在生成二维码...")
    login = login_v2.QrCodeLogin()
    await login.generate_qrcode()
    pic = login.get_qrcode_picture()

    if qr_file:
        pic.to_file(qr_file)
        print(f"二维码已保存到 {qr_file}")
    else:
        pic.to_file('/tmp/bili_qr.png')
        print("二维码已保存到 /tmp/bili_qr.png")

    print("\n请用手机 B站 APP 扫码（我的 -> 右上角扫一扫）")
    print("等待扫码...")

    while True:
        state = await login.check_state()
        if state == login_v2.QrCodeLoginEvents.DONE:
            print("\n✅ 扫码登录成功！")
            break
        elif state == login_v2.QrCodeLoginEvents.CONF:
            print("📱 已扫码，请在手机上确认登录")
        elif state == login_v2.QrCodeLoginEvents.SCAN:
            print("📱 已扫码，请在手机上确认登录")
        elif state == login_v2.QrCodeLoginEvents.TIMEOUT:
            print("\n❌ 二维码已过期，请重新运行")
            return
        await asyncio.sleep(2)

    cred = login.get_credential()
    sessdata = cred.sessdata

    print(f"\n=== 获取成功 ===")
    print(f"SESSDATA: {sessdata[:20]}...")

    # 写入文件
    output_path = os.path.join(os.environ.get('WORKDIR', '/data'), '.sessdata')
    with open(output_path, 'w') as f:
        f.write(sessdata)
    print(f"\n✅ SESSDATA 已写入 {output_path}")
    print(f"   重启弹幕容器即可生效")

if __name__ == '__main__':
    sync(main())
