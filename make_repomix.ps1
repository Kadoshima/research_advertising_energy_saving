# make_repomix.ps1 - Create repomix-like output for thesis files
# Proper UTF-8 handling
$output = 'repomix-thesis.txt'
$basePath = 'C:\Users\tp240\Documents\Research\research_advertising_energy_saving'

# Collect all files
$allFiles = New-Object System.Collections.ArrayList

# Find thesis directory dynamically (folder containing 'main.tex')
$thesisDir = Get-ChildItem -Path $basePath -Directory | Where-Object {
    Test-Path (Join-Path $_.FullName 'main.tex')
} | Select-Object -First 1

if ($thesisDir) {
    Write-Host "Found thesis dir: $($thesisDir.Name)"
    Get-ChildItem -LiteralPath $thesisDir.FullName -Filter '*.tex' -Recurse | ForEach-Object { [void]$allFiles.Add($_) }
    Get-ChildItem -LiteralPath $thesisDir.FullName -Filter '*.sty' -Recurse | ForEach-Object { [void]$allFiles.Add($_) }
}

# Phase 2 scripts
$scriptsPath = Join-Path $basePath 'scripts\phase2_offline_eval'
if (Test-Path $scriptsPath) {
    Get-ChildItem -LiteralPath $scriptsPath -Filter '*.py' -Recurse | ForEach-Object { [void]$allFiles.Add($_) }
    Get-ChildItem -LiteralPath $scriptsPath -Filter '*.yaml' -Recurse | ForEach-Object { [void]$allFiles.Add($_) }
}

# Results summary
$resultsPath = Join-Path $basePath 'results\phase2_offline_eval'
if (Test-Path $resultsPath) {
    Get-ChildItem -LiteralPath $resultsPath -Filter '*.csv' | ForEach-Object { [void]$allFiles.Add($_) }
}

Write-Host "Found $($allFiles.Count) files total (thesis + phase2 scripts only)"

# Create output - use StreamWriter for proper UTF-8 without BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$writer = New-Object System.IO.StreamWriter((Join-Path $basePath $output), $false, $utf8NoBom)

$header = @"
# Repository Summary for LLM
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# Scope: Thesis (.tex/.sty) + Phase2 scripts (.py/.yaml) + Phase2 results (.csv)
# Files: $($allFiles.Count)

"@
$writer.WriteLine($header)

foreach ($f in $allFiles) {
    $rel = $f.FullName.Replace($basePath + '\', '')
    $separator = "`n================================================================================`nFile: $rel`n================================================================================"
    $writer.WriteLine($separator)

    try {
        # Try UTF-8 first
        $content = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
        if ($content) {
            $writer.WriteLine($content)
        }
    } catch {
        # Fallback to default encoding
        $content = Get-Content -LiteralPath $f.FullName -Raw
        if ($content) {
            $writer.WriteLine($content)
        }
    }
}

$writer.Close()

$size = (Get-Item (Join-Path $basePath $output)).Length / 1KB
Write-Host "Output: $output ($([math]::Round($size, 1)) KB)"
Write-Host "Done!"
