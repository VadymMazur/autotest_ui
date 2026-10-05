# Generate the scenario report with readable tables and all bundled Allure plugins.
$ErrorActionPreference = 'Stop'
$suiteRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$resultsPath = Join-Path $suiteRoot 'allure-results\e2e-lead-001'
$reportPath = [IO.Path]::GetFullPath((Join-Path $suiteRoot 'allure-report\e2e-lead-001'))
if (-not $reportPath.StartsWith($suiteRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The generated report must stay inside the suite directory.'
}
if (-not (Test-Path -LiteralPath $resultsPath)) {
    throw 'Run the E2E test with --alluredir=allure-results/e2e-lead-001 first.'
}

$allureCommand = Get-Command allure -ErrorAction Stop
$commandDirectory = Split-Path $allureCommand.Source -Parent
$candidates = @(
    (Join-Path $commandDirectory 'node_modules\allure-commandline\dist'),
    (Join-Path $commandDirectory '..'),
    $env:ALLURE_HOME
)
$distribution = $candidates | Where-Object {
    $_ -and (Test-Path -LiteralPath (Join-Path $_ 'config\allure.yml'))
} | Select-Object -First 1
if (-not $distribution) {
    throw 'Cannot locate the Allure distribution. Install allure-commandline or set ALLURE_HOME.'
}

# The installed Windows launcher clears APP_HOME before Java starts. Supply it
# for this command so Behaviors/Packages data is generated, then restore it.
$previousAppHome = [Environment]::GetEnvironmentVariable('APP_HOME', 'Process')
try {
    $env:APP_HOME = (Resolve-Path -LiteralPath $distribution).Path
    & $allureCommand.Source generate $resultsPath --clean -o $reportPath
    if ($LASTEXITCODE -ne 0) {
        throw "Allure generation failed with exit code $LASTEXITCODE."
    }
} finally {
    [Environment]::SetEnvironmentVariable('APP_HOME', $previousAppHome, 'Process')
}

# Keep the standard report; only style our description tables to fit its pane.
$css = @'
.description__text { overflow-wrap: anywhere; }
.description__text table {
  width: 100%; table-layout: fixed; border-collapse: collapse; margin: 14px 0 24px;
}
.description__text th, .description__text td {
  text-align: left; vertical-align: top; padding: 8px 10px;
  border: 1px solid #d8dee6; overflow-wrap: anywhere; line-height: 1.45;
}
.description__text th { background: #eef3f7; }
.description__text tbody tr:nth-child(even) { background: #f8fafc; }
.description__text table:first-of-type th:first-child { width: 75%; }
.description__text h3 { margin-top: 26px; }
'@
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $reportPath 'crm-report.css'), $css, $utf8)
$indexPath = Join-Path $reportPath 'index.html'
$html = [IO.File]::ReadAllText($indexPath)
$html = $html.Replace('</head>', '<link rel="stylesheet" href="crm-report.css"></head>')
[IO.File]::WriteAllText($indexPath, $html, $utf8)
foreach ($required in @('widgets\behaviors.json', 'data\behaviors.json', 'data\packages.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $reportPath $required))) {
        throw "Allure did not generate $required. Check the distribution's plugins."
    }
}
Write-Host "Ready: $reportPath"
