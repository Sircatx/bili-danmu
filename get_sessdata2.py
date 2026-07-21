import win32file, win32con, os, sqlite3, tempfile, base64, json, subprocess
from Crypto.Cipher import AES

src = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Default', 'Network', 'Cookies')
dst = os.path.join(tempfile.gettempdir(), 'edge_cookies_ok')

# win32 API 共享读模式打开（绕过 Edge 锁）
handle = win32file.CreateFile(
    src, win32con.GENERIC_READ,
    win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
    None, win32con.OPEN_EXISTING, 0, None
)
data = win32file.ReadFile(handle, os.path.getsize(src) or 1048576)[1]
win32file.CloseHandle(handle)
with open(dst, 'wb') as f:
    f.write(data)
print(f'Copied {len(data)} bytes')

# 读 cookie
conn = sqlite3.connect(dst)
cur = conn.cursor()
cur.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%bilibili%' AND name='SESSDATA'")
rows = cur.fetchall()
print(f'Found {len(rows)} SESSDATA rows')
conn.close()

if not rows:
    print('No SESSDATA found - not logged in?')
else:
    # 解密 master key from Local State
    ls_path = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Local State')
    with open(ls_path, 'r', encoding='utf-8') as f:
        ls = json.load(f)
    enc_key = base64.b64decode(ls['os_crypt']['encrypted_key'])
    if enc_key[:5] == b'DPAPI':
        enc_key = enc_key[5:]

    # DPAPI 解密 master key
    enc_key_path = os.path.join(tempfile.gettempdir(), 'enc_key.bin')
    with open(enc_key_path, 'wb') as f:
        f.write(enc_key)

    ps_script = (
        '$b=[IO.File]::ReadAllBytes("' + enc_key_path.replace('\\', '/') + '");'
        '[Convert]::ToBase64String([Security.Cryptography.ProtectedData]::Unprotect($b,$null,"CurrentUser"))'
    )
    r = subprocess.run(['powershell', '-Command', ps_script], capture_output=True, timeout=10)
    master_key = base64.b64decode(r.stdout.strip())
    print(f'Master key decrypted, len={len(master_key)}')

    for row in rows:
        enc = row[2]
        if enc[:3] == b'v10':
            nonce = enc[3:15]
            tag = enc[-16:]
            cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
            sessdata = cipher.decrypt_and_verify(enc[15:-16], tag).decode()
            print(f'SESSDATA={sessdata}')

    os.unlink(enc_key_path)

os.unlink(dst)
