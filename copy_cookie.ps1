$src = Join-Path $env:LOCALAPPDATA "Microsoft\Edge\User Data\Default\Network\Cookies"
$dst = Join-Path $env:TEMP "edge_cookies_ok"

# 用 .NET FileStream 共享读写模式打开（绕过 Edge 锁）
$fs = [System.IO.File]::Open($src, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
$ms = New-Object System.IO.MemoryStream
$fs.CopyTo($ms)
[System.IO.File]::WriteAllBytes($dst, $ms.ToArray())
$fs.Close()
Write-Output "Copied $($ms.Length) bytes"

# 读 cookie SQLite
$conn = New-Object System.Data.SQLite.SQLiteConnection
# 没有 SQLite assembly，用 python 读
