# make_repomix_with_figscripts.ps1
# - Regenerate repomix-thesis.txt (via make_repomix.ps1)
# - Append the figure-script index + all referenced scripts/configs into one file
#
# Output: repomix-thesis-with-figscripts.txt

$ErrorActionPreference = 'Stop'

$basePath = $PSScriptRoot
$repomixPath = Join-Path $basePath 'repomix-thesis.txt'
$outputPath = Join-Path $basePath 'repomix-thesis-with-figscripts.txt'

if (-not (Test-Path -LiteralPath (Join-Path $basePath 'make_repomix.ps1'))) {
  throw "Missing make_repomix.ps1 in: $basePath"
}

Write-Host "Regenerating repomix-thesis.txt..."
& (Join-Path $basePath 'make_repomix.ps1')

if (-not (Test-Path -LiteralPath $repomixPath)) {
  throw "repomix-thesis.txt was not generated: $repomixPath"
}

# Locate the thesis directory (contains main.tex), then pick the index markdown in its root.
$thesisDir = Get-ChildItem -LiteralPath $basePath -Directory | Where-Object {
  Test-Path -LiteralPath (Join-Path $_.FullName 'main.tex')
} | Select-Object -First 1
if (-not $thesisDir) {
  throw "Could not locate thesis directory (expected a folder containing main.tex) under: $basePath"
}

$indexFile = Get-ChildItem -LiteralPath $thesisDir.FullName -File -Filter '*.md' |
  Where-Object { $_.Name -ne 'README.md' -and $_.Name -ne 'WRITING_RULES.md' } |
  Select-Object -First 1
if (-not $indexFile) {
  throw "Could not locate figure-script index markdown in thesis root: $($thesisDir.FullName)"
}
$indexPath = $indexFile.FullName
$indexRelPath = $indexPath.Replace($basePath + '\', '')

# Extract backtick-wrapped paths from the index and keep only code/config files.
$indexContent = Get-Content -LiteralPath $indexPath -Raw -Encoding UTF8
$matches = [regex]::Matches($indexContent, '`([^`]+)`')
$rawPaths = $matches | ForEach-Object { $_.Groups[1].Value.Trim() }
$extraRelPaths = $rawPaths | Where-Object { $_ -match '\.(py|ya?ml)$' }

$uniq = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($p in $extraRelPaths) { [void]$uniq.Add($p) }
$extraRelPathsUniq = $uniq | Sort-Object

Write-Host "Bundling repomix + index + $($extraRelPathsUniq.Count) referenced files..."

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$writer = New-Object System.IO.StreamWriter($outputPath, $false, $utf8NoBom)

function Write-Separator([System.IO.StreamWriter]$w, [string]$rel) {
  $w.WriteLine("")
  $w.WriteLine("================================================================================")
  $w.WriteLine("File: $rel")
  $w.WriteLine("================================================================================")
}

function Read-TextBestEffort([string]$path) {
  try {
    return [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
  } catch {
    return Get-Content -LiteralPath $path -Raw
  }
}

$writer.WriteLine("# Repository Summary for LLM")
$writer.WriteLine("# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$writer.WriteLine("# Scope: repomix-thesis.txt + figure-script index + referenced scripts/configs")
$writer.WriteLine("# Extra files: $($extraRelPathsUniq.Count)")

Write-Separator $writer 'repomix-thesis.txt'
$writer.WriteLine((Read-TextBestEffort $repomixPath))

Write-Separator $writer ($indexRelPath -replace '\\','/')
$writer.WriteLine((Read-TextBestEffort $indexPath))

foreach ($rel in $extraRelPathsUniq) {
  $relNative = $rel -replace '/', '\'
  $full = Join-Path $basePath $relNative
  if (-not (Test-Path -LiteralPath $full)) {
    Write-Warning "Missing referenced file: $rel"
    continue
  }
  Write-Separator $writer $rel
  $writer.WriteLine((Read-TextBestEffort $full))
}

$writer.Close()

$sizeKB = (Get-Item -LiteralPath $outputPath).Length / 1KB
Write-Host "Output: $(Split-Path -Leaf $outputPath) ($([math]::Round($sizeKB, 1)) KB)"
Write-Host "Done!"
