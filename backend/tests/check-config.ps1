$ErrorActionPreference = 'Stop'
$backendDir = Split-Path -Parent $PSScriptRoot
. (Join-Path $backendDir 'load-config.ps1')
$temporary = Join-Path $backendDir ('.cache\config-check\' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temporary -Force | Out-Null
@(
    '# Test settings; never a real credential',
    'OPENAI_API_KEY="file-test-key"',
    'PULSR_AI_MODEL="model-test"',
    'SPHEREX_INDEX_DIR="cache with spaces/index"',
    'PULSR_COMMUNITY_DB=.data/community.sqlite3'
) | Set-Content -LiteralPath (Join-Path $temporary '.env')
$env:OPENAI_API_KEY = 'terminal-test-key'
foreach ($name in @('PULSR_AI_MODEL', 'SPHEREX_INDEX_DIR', 'PULSR_COMMUNITY_DB')) {
    [Environment]::SetEnvironmentVariable($name, $null, 'Process')
}
Import-BackendConfig -BackendDir $temporary
if ($env:OPENAI_API_KEY -ne 'terminal-test-key') { throw 'Terminal override was lost' }
if ($env:PULSR_AI_MODEL -ne 'model-test') { throw 'Quoted value was not read' }
if ($env:SPHEREX_INDEX_DIR -ne [IO.Path]::GetFullPath((Join-Path $temporary 'cache with spaces/index'))) { throw 'Relative index path was not resolved' }
if (-not [IO.Path]::IsPathRooted($env:PULSR_COMMUNITY_DB)) { throw 'Database path is not absolute' }
Write-Host 'PASS: private config loading, quoted values, terminal overrides, relative paths.'
