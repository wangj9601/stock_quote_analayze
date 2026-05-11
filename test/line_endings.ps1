$p = Join-Path $PSScriptRoot "..\scripts\deploy\deploy.ps1" | Resolve-Path
$bytes = [IO.File]::ReadAllBytes($p)
# find first occurrence of 0x27 0x64 0x6F 0x63 0x73 0x27 ( 'docs' )
$s = [Text.Encoding]::UTF8.GetString($bytes)
$i = $s.IndexOf("'docs'")
if ($i -lt 0) { throw "not found" }
$after = $bytes[($i + 6)..($i + 20)]
Write-Output ("after 'docs' bytes: {0}" -f (($after | ForEach-Object { '{0:X2}' -f $_ }) -join ' '))
