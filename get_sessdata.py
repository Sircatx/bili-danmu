import subprocess, sqlite3, os, tempfile

# 1. 用 PowerShell 复制锁定的 cookie 文件
ps_copy = r'''
$src = Join-Path $env:LOCALAPPDATA "Microsoft\Edge\User Data\Default\Network\Cookies"
$dst = Join-Path $env:TEMP "edge_cookies_copy"
Copy-Item $src $dst -Force
Write-Output $dst
'''
result = subprocess.run(['powershell', '-Command', ps_copy], capture_output=True, text=True, timeout=10)
tmp_path = result.stdout.strip()
print(f'Copied to: {tmp_path}')
print(f'Exists: {os.path.exists(tmp_path)}')

# 2. 读 cookie 数据库
conn = sqlite3.connect(tmp_path)
cur = conn.cursor()
cur.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%bilibili%' AND name='SESSDATA'")
rows = cur.fetchall()
print(f'Found {len(rows)} SESSDATA rows')
conn.close()

for r in rows:
    enc = r[2]
    print(f'host={r[0]} enc_len={len(enc)} first_bytes={enc[:3].hex() if enc else "none"}')
    if enc[:3] == b'v10':
        print('  -> AES-GCM encrypted (need Edge master key from Local State)')
    else:
        print('  -> trying DPAPI...')

# 3. 读 Local State 获取 master key
local_state_path = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'Edge', 'User Data', 'Local State')
print(f'\nLocal State exists: {os.path.exists(local_state_path)}')

# 复制 Local State 也可能有锁，但通常不锁
import json
with open(local_state_path, 'r', encoding='utf-8') as f:
    local_state = json.load(f)

encrypted_key_b64 = local_state.get('os_crypt', {}).get('encrypted_key', '')
print(f'encrypted_key present: {bool(encrypted_key_b64)}')

if encrypted_key_b64:
    import base64
    encrypted_key = base64.b64decode(encrypted_key_b64)
    # 去掉前5字节 "DPAPI" 前缀
    if encrypted_key[:5] == b'DPAPI':
        encrypted_key = encrypted_key[5:]
    print(f'Key prefix stripped, len={len(encrypted_key)}')
    
    # 用 DPAPI 解密 master key
    enc_key_path = os.path.join(tempfile.gettempdir(), 'enc_key.bin')
    with open(enc_key_path, 'wb') as f:
        f.write(encrypted_key)
    
    ps_dec_key = r'''
$bytes = [System.IO.File]::ReadAllBytes("''' + enc_key_path.replace('\\', '/') + r'''")
$plain = [System.Security.Cryptography.ProtectedData]::Unprotect($bytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)
[System.Convert]::ToBase64String($plain)
'''
    r2 = subprocess.run(['powershell', '-Command', ps_dec_key], capture_output=True, text=True, timeout=10)
    if r2.returncode == 0 and r2.stdout.strip():
        master_key = base64.b64decode(r2.stdout.strip())
        print(f'Master key decrypted, len={len(master_key)}')
        
        # 用 master key 解密 cookie
        from Crypto.Cipher import AES
        
        for r in rows:
            enc = r[2]
            if enc[:3] == b'v10':
                nonce = enc[3:15]  # 12 bytes
                ciphertext = enc[15:-16]  # 去掉 tag
                tag = enc[-16:]  # 16 bytes GCM tag
                
                cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
                try:
                    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
                    sessdata = plaintext.decode('utf-8')
                    print(f'\n=== SESSDATA FOUND ===')
                    print(f'host={r[0]}')
                    print(f'SESSDATA={sessdata}')
                except Exception as e:
                    print(f'  decrypt failed: {e}')
    else:
        print(f'DPAPI key decrypt failed: {r2.stderr[:200]}')

# 清理
try:
    os.unlink(tmp_path)
    os.unlink(enc_key_path)
except:
    pass
