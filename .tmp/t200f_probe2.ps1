$ErrorActionPreference='Stop'
$rows=7;$cols=9
function Show($label,$file){
  if(-not (Test-Path $file)){ "$label : FILE MISSING $file"; return }
  $j=Get-Content $file -Raw | ConvertFrom-Json
  "=== $label ($file) ==="
  "keys: " + ($j.PSObject.Properties.Name -join ", ")
  if($j.view){ "view: " + ($j.view | ConvertTo-Json -Compress -Depth 3) }
  "tiles dims: $($j.tiles.Count) rows, lens " + (($j.tiles | ForEach-Object {$_.Count}) -join ",")
  foreach($a in @(@(3,5,'D6'),@(3,3,'D4'),@(3,0,'D1'),@(6,4,'G5'))){
    $r=$a[0];$c=$a[1];$n=$a[2]
    $t=$j.tiles[$r][$c]
    "$n -> tiles[r$r][c$c] key=$($t.tileKey) ht=$($t.heightType) bt=$($t.buildableType) col=$($t.col) row=$($t.row)"
  }
  "grid:"
  for($r=0;$r -lt $j.tiles.Count;$r++){
    $line=""
    for($c=0;$c -lt $j.tiles[$r].Count;$c++){ $line += ("{0,-16}" -f $j.tiles[$r][$c].tileKey) }
    "  r$r : $line"
  }
}
Show "C 露托/derived" "data\derived\prts_map_main_01-01.json"
Show "C 露托/derived_f" "data\derived\prts_map_main_01-01_f.json"
Show "E MAA nogap" "D:\__soft\MAA\resource\Arknights-Tile-Pos\main_01-01-obt-main-level_main_01-01.json"
Show "E MAA f" "D:\__soft\MAA\resource\Arknights-Tile-Pos\main_01-01#f#-obt-main-level_main_01-01.json"
