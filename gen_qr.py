import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.1.3', username='root', password='Aa112211.', timeout=8)

# 检查图片文件头
stdin, stdout, stderr = c.exec_command('xxd /usr/share/hassio/share/danmu/qrcode.png | head -3', timeout=10)
print('=== file header ===')
print(stdout.read().decode(errors='replace'))

# 直接生成新的二维码图片，用 PIL 转成标准 PNG
cmd = """docker exec danmu_501 python3 -c "
from bilibili_api import login_v2, sync
import asyncio

async def gen():
    login = login_v2.QrCodeLogin()
    await login.generate_qrcode()
    pic = login.get_qrcode_picture()
    # 用 to_file 保存
    pic.to_file('/data/qrcode_new.png')
    print('saved')
    # 也输出终端 ASCII
    qr = login.get_qrcode_terminal()
    print(qr)

sync(gen())
"
"""
stdin, stdout, stderr = c.exec_command(cmd, timeout=20)
out = stdout.read().decode(errors='replace')
err = stderr.read().decode(errors='replace')
print('=== output ===')
print(out)
if err:
    print('=== stderr ===')
    print(err[:500])

# 检查新二维码
stdin, stdout, stderr = c.exec_command('ls -la /usr/share/hassio/share/danmu/qrcode_new.png 2>&1; xxd /usr/share/hassio/share/danmu/qrcode_new.png | head -3', timeout=10)
print('=== new qrcode ===')
print(stdout.read().decode(errors='replace'))

# 下载到本地
sftp = c.open_sftp()
sftp.get('/usr/share/hassio/share/danmu/qrcode_new.png', r'C:\Project\bilibili-danmu-capture\qrcode_new.png')
sftp.close()
print('downloaded qrcode_new.png')

c.close()
