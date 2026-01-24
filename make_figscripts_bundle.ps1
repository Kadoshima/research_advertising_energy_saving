# make_figscripts_bundle.ps1
# Bundle the thesis figure-script index + all referenced scripts/configs into a standalone text file.
#
# Output: repomix-figscripts.txt

param(
  # Optional explicit path to the index markdown (relative to repo root or absolute).
  [string]$IndexPath
)

$ErrorActionPreference = 'Stop'

$basePath = $PSScriptRoot
$outputPath = Join-Path $basePath 'repomix-figscripts.txt'

# Locate thesis directory (contains main.tex).
$thesisDir = Get-ChildItem -LiteralPath $basePath -Directory | Where-Object {
  Test-Path -LiteralPath (Join-Path $_.FullName 'main.tex')
} | Select-Object -First 1
if (-not $thesisDir) {
  throw "Could not locate thesis directory (expected a folder containing main.tex) under: $basePath"
}

function Resolve-IndexPath([string]$candidate) {
  if ([string]::IsNullOrWhiteSpace($candidate)) { return $null }
  if ([System.IO.Path]::IsPathRooted($candidate)) { return $candidate }
  return (Join-Path $basePath ($candidate -replace '/', '\'))
}

if (-not [string]::IsNullOrWhiteSpace($IndexPath)) {
  $IndexPath = Resolve-IndexPath $IndexPath
  if (-not (Test-Path -LiteralPath $IndexPath)) {
    throw "Index markdown not found: $IndexPath"
  }
} else {
  # Auto-detect an index markdown in thesis root (prefer the one with many backticks).
  $candidates = Get-ChildItem -LiteralPath $thesisDir.FullName -File -Filter '*.md' |
    Where-Object { $_.Name -ne 'README.md' -and $_.Name -ne 'WRITING_RULES.md' }
  if (-not $candidates -or $candidates.Count -eq 0) {
    throw "Could not locate index markdown in thesis root: $($thesisDir.FullName)"
  }
  if ($candidates.Count -eq 1) {
    $IndexPath = $candidates[0].FullName
  } else {
    $IndexPath = ($candidates | ForEach-Object {
      $content = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
      [PSCustomObject]@{
        File = $_
        Backticks = ([regex]::Matches($content, '`').Count)
        Length = $_.Length
      }
    } | Sort-Object Backticks, Length -Descending | Select-Object -First 1).File.FullName
  }
}

if (-not (Test-Path -LiteralPath $IndexPath)) {
  throw "Index markdown not found: $IndexPath"
}

$indexRelPath = $IndexPath.Replace($basePath + '\', '')

# Extract backtick-wrapped paths from the index and keep only code/config files.
$indexContent = Get-Content -LiteralPath $IndexPath -Raw -Encoding UTF8
$matches = [regex]::Matches($indexContent, '`([^`]+)`')
$rawPaths = $matches | ForEach-Object { $_.Groups[1].Value.Trim() }
$extraRelPaths = $rawPaths | Where-Object { $_ -match '\.(py|ya?ml)$' }

$uniq = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($p in $extraRelPaths) { [void]$uniq.Add($p) }
$extraRelPathsUniq = $uniq | Sort-Object

Write-Host "Bundling index + $($extraRelPathsUniq.Count) referenced files..."

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

$writer.WriteLine("# Figure Script Bundle for LLM")
$writer.WriteLine("# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
$writer.WriteLine("# Index: $indexRelPath")
$writer.WriteLine("# Files: $($extraRelPathsUniq.Count)")

Write-Separator $writer ($indexRelPath -replace '\\','/')
$writer.WriteLine((Read-TextBestEffort $IndexPath))

$missing = New-Object System.Collections.Generic.List[string]

foreach ($rel in $extraRelPathsUniq) {
  $relNative = $rel -replace '/', '\'
  $full = Join-Path $basePath $relNative
  if (-not (Test-Path -LiteralPath $full)) {
    $missing.Add($rel) | Out-Null
    continue
  }
  Write-Separator $writer $rel
  $writer.WriteLine((Read-TextBestEffort $full))
}

if ($missing.Count -gt 0) {
  Write-Separator $writer 'MISSING_REFERENCES'
  foreach ($m in $missing) { $writer.WriteLine($m) }
}

$writer.Close()

$sizeKB = (Get-Item -LiteralPath $outputPath).Length / 1KB
Write-Host "Output: $(Split-Path -Leaf $outputPath) ($([math]::Round($sizeKB, 1)) KB)"
if ($missing.Count -gt 0) {
  Write-Host "Warning: missing referenced files: $($missing.Count)"
}
Write-Host "Done!"
