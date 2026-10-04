# t077_insert_registry.ps1 -- insert the T-077 row after the T-076 row.
# Preserves the file's original encoding (BOM presence) and uses CRLF.
$ErrorActionPreference = 'Stop'

$registry = 'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
$rowFile  = 'C:\Users\23922\Documents\ds_harness\ak\.tmp\t077_registry_row.md'

# --- detect BOM ---
$bytes = [System.IO.File]::ReadAllBytes($registry)
$hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$body   = if ($hasBom) { $bytes[3..($bytes.Length - 1)] } else { $bytes }
$text   = [System.Text.Encoding]::UTF8.GetString($body)
Write-Output "BOM present: $hasBom ; CRLF count: $(([regex]::Matches($text, "`r`n")).Count) ; bare-LF count: $(([regex]::Matches($text, "(?<!`r)`n")).Count)"

# --- idempotence guard ---
if ($text -match '\|\s*T-077\s*\|') {
    Write-Output 'T-077 row already present -- nothing to do.'
    exit 0
}

$lines = $text -split "`r`n", -1
Write-Output "total split lines: $($lines.Count)"

# locate the T-076 row (last one, if duplicated)
$idx = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\|\s*T-076\s*\|') { $idx = $i }
}
if ($idx -lt 0) { throw 'T-076 row not found; aborting without modification.' }
Write-Output "T-076 row at 0-based index $idx (file line $($idx + 1))"

$row = ([System.IO.File]::ReadAllText($rowFile, [System.Text.Encoding]::UTF8)).TrimEnd("`r", "`n")
if ($row -notmatch '^\|\s*T-077\s*\|') { throw 'row file does not start with the T-077 table cell.' }

$out = New-Object System.Collections.Generic.List[string]
$out.AddRange([string[]]$lines[0..$idx])
$out.Add($row)
if ($idx + 1 -lt $lines.Count) { $out.AddRange([string[]]$lines[($idx + 1)..($lines.Count - 1)]) }

$newText = [string]::Join("`r`n", $out)
$enc = New-Object System.Text.UTF8Encoding($hasBom)
[System.IO.File]::WriteAllText($registry, $newText, $enc)
Write-Output "WROTE. new line count: $((($newText -split "`r`n").Count))"
