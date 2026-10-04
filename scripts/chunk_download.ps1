# chunk_download.ps1 — 分块断点续传下载（接受部分块，自动推进）
param(
  [string]$Url = "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/battle/buff_template_data.json",
  [string]$OutFile = "C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata\buff_template_data.json",
  [long]$Total = 27090165,
  [int]$ChunkKB = 512
)
$chunk = $ChunkKB * 1024
$tmp = "$OutFile.chunk"
$done = 0
if (Test-Path $OutFile) { $done = (Get-Item $OutFile).Length }
Write-Output ("chunked download start: {0} / {1} bytes" -f $done, $Total)
$stall = 0
while ($done -lt $Total -and $stall -lt 30) {
  $end = [Math]::Min($done + $chunk - 1, $Total - 1)
  curl.exe -s --max-time 90 -r "$done-$end" $Url -o $tmp
  if ($LASTEXITCODE -eq 0 -and (Test-Path $tmp)) {
    $sz = (Get-Item $tmp).Length
    if ($sz -gt 0) {
      $out = [System.IO.File]::Open($OutFile, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
      $in = [System.IO.File]::OpenRead($tmp)
      $in.CopyTo($out)
      $out.Close(); $in.Close()
      $done += $sz
      $stall = 0
      if ($done % (4 * $chunk) -lt $chunk) { Write-Output ("progress: {0} / {1}" -f $done, $Total) }
      continue
    }
  }
  $stall++
  Write-Output ("chunk at {0} failed ({1}), stall={2}" -f $done, $LASTEXITCODE, $stall)
  Start-Sleep -Seconds 2
}
Write-Output ("FINAL: {0} bytes (target {1})" -f $done, $Total)
if ($done -ge $Total) { Write-Output "DOWNLOAD COMPLETE" }
