# make_repomix_mab.ps1
# - Bundle MAB/Safe-UCB offline study docs + scripts + result READMEs into mab.txt
# - Excludes CSV/YAML/figures (only .md + .py)

$ErrorActionPreference = 'Stop'

$basePath = $PSScriptRoot
$output = Join-Path $basePath 'mab.txt'

$files = New-Object System.Collections.Generic.List[System.IO.FileInfo]

function Add-File([string]$path) {
  if (Test-Path -LiteralPath $path) {
    $files.Add((Get-Item -LiteralPath $path))
  }
}

function Add-Glob([string]$path, [string]$pattern) {
  if (Test-Path -LiteralPath $path) {
    Get-ChildItem -LiteralPath $path -Recurse -File -Filter $pattern | ForEach-Object { $files.Add($_) }
  }
}

# Core docs (ordered)
Add-File (Join-Path $basePath 'docs\フェーズ2\Phase2_MVP仕様書_2026-01-21.md')
Add-File (Join-Path $basePath 'docs\metrics_definition.md')
Add-Glob (Join-Path $basePath 'docs\フェーズ2\phase2_bandit_offline_studies_2026-01-24') '*.md'

# Scripts (MAB offline eval)
Add-Glob (Join-Path $basePath 'scripts\phase2_offline_eval') '*.py'

# Results: v01-v04 (plus v04b), and latest v05 READMEs / md summaries
$resultDirs = @(
  'results\phase2_offline_studies_2026-01-24_v01',
  'results\phase2_offline_studies_2026-01-25_v02',
  'results\phase2_offline_studies_2026-01-25_v03',
  'results\phase2_offline_studies_2026-01-25_v04',
  'results\phase2_offline_studies_2026-01-25_v04b',
  'results\phase2_offline_studies_2026-01-26_v04',
  'results\phase2_offline_studies_2026-01-26_v05'
)
foreach ($d in $resultDirs) {
  Add-Glob (Join-Path $basePath $d) '*.md'
}

# Gate C outputs (READMEs)
Add-Glob (Join-Path $basePath 'results\phase2_gatec_candidates_2026-01-26_v01') '*.md'
Add-Glob (Join-Path $basePath 'results\phase2_gatec_sweep_m_2026-01-26_v02') '*.md'

# De-duplicate while preserving order
$seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$uniq = New-Object System.Collections.Generic.List[System.IO.FileInfo]
foreach ($f in $files) {
  $key = $f.FullName
  if (-not $seen.Contains($key)) {
    [void]$seen.Add($key)
    $uniq.Add($f)
  }
}

Write-Host "Bundling $($uniq.Count) files..."

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$writer = New-Object System.IO.StreamWriter($output, $false, $utf8NoBom)

$writer.WriteLine("# Repository Summary for MAB Offline Studies")
$writer.WriteLine("# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$writer.WriteLine("# Scope: Phase2 MAB docs + scripts + result READMEs (no CSV/YAML/figures)")
$writer.WriteLine("# Files: $($uniq.Count)")
$writer.WriteLine("")

foreach ($f in $uniq) {
  $rel = $f.FullName.Replace($basePath + '\', '')
  $writer.WriteLine("================================================================================")
  $writer.WriteLine("File: $rel")
  $writer.WriteLine("================================================================================")
  try {
    $content = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
    $writer.WriteLine($content)
  } catch {
    $content = Get-Content -LiteralPath $f.FullName -Raw
    $writer.WriteLine($content)
  }
  $writer.WriteLine("")
}

$writer.Close()

$size = (Get-Item -LiteralPath $output).Length / 1KB
Write-Host "Output: mab.txt ($([math]::Round($size, 1)) KB)"
Write-Host "Done!"
