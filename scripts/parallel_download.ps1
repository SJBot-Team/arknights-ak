# parallel_download.ps1 — 6 路并行 1MB 分块下载（Start-ThreadJob）
$url = "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/battle/buff_template_data.json"
$total = 27090165
$chunk = 1048576
$dir = "C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata\parts"
$final = "C:\Users\23922\Documents\ds_harness\ak\_raw\gamedata\buff_template_data.json"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$nChunks = [Math]::Ceiling($total / $chunk)

$jobs = @()
for ($w = 0; $w -lt 6; $w++) {
  $jobs += Start-ThreadJob -ArgumentList $w, $nChunks, $chunk, $total, $url, $dir -ScriptBlock {
    param($w, $nChunks, $chunk, $total, $url, $dir)
    $done = 0
    for ($i = $w; $i -lt $nChunks; $i += 6) {
      $start = $i * $chunk
      $end = [Math]::Min($start + $chunk - 1, $total - 1)
      $out = Join-Path $dir ("part.{0:D4}" -f $i)
      if (Test-Path $out) { continue }
      $saved = 0
      for ($try = 0; $try -lt 10 -and $saved -lt ($end - $start + 1); $try++) {
        $tmp = "$out.tmp"
        curl.exe -s --max-time 150 -r "$start-$end" $url -o $tmp
        if ($LASTEXITCODE -eq 0 -and (Test-Path $tmp)) {
          $sz = (Get-Item $tmp).Length
          if ($sz -gt $saved) {
            if ($saved -eq 0) { Move-Item $tmp $out -Force }
            else {
              $fs = [System.IO.File]::Open($out, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
              $in = [System.IO.File]::OpenRead($tmp)
              $in.CopyTo($fs); $fs.Close(); $in.Close()
              Remove-Item $tmp -Force
            }
            $saved = (Get-Item $out).Length
          }
        }
        if ($saved -lt ($end - $start + 1)) { Start-Sleep -Milliseconds 1000 }
      }
      if ($saved -ge ($end - $start + 1)) { $done++ }
    }
    "worker $w done, chunks: $done"
  }
}
$last = -1
while ($jobs | Where-Object { $_.State -eq "Running" }) {
  Start-Sleep -Seconds 8
  $have = (Get-ChildItem $dir -Filter "part.*" -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
  if ($have -ne $last) { Write-Output ("progress: {0} / {1}" -f $have, $total); $last = $have }
}
$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job

Write-Output "concatenating..."
[System.IO.File]::WriteAllBytes($final, [byte[]]@())
$missing = @()
for ($i = 0; $i -lt $nChunks; $i++) {
  $p = Join-Path $dir ("part.{0:D4}" -f $i)
  if (Test-Path $p) {
    $fs = [System.IO.File]::Open($final, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
    $in = [System.IO.File]::OpenRead($p)
    $in.CopyTo($fs); $fs.Close(); $in.Close()
  } else { $missing += $i }
}
if ($missing.Count) { Write-Output ("MISSING PARTS: " + ($missing -join ",")) }
Write-Output ("FINAL SIZE: {0} (target {1})" -f (Get-Item $final).Length, $total)
