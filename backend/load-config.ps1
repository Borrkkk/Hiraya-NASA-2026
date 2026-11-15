function Import-BackendConfig {
    param([string]$BackendDir)
    $path = Join-Path $BackendDir '.env'
    if (-not (Test-Path -LiteralPath $path)) {
        Copy-Item -LiteralPath (Join-Path $BackendDir '.env.example') -Destination $path
    }
    $allowed = @('OPENAI_API_KEY', 'PULSR_AI_MODEL', 'SPHEREX_INDEX_DIR', 'SPHEREX_IMAGE_SOURCE', 'PULSR_COMMUNITY_DB')
    $lineNumber = 0
    foreach ($line in [IO.File]::ReadAllLines($path)) {
        $lineNumber++
        if ($line.Trim().Length -eq 0 -or $line.TrimStart().StartsWith('#')) { continue }
        if ($line -notmatch '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$') {
            throw "Invalid .env syntax on line $lineNumber. Use NAME=value."
        }
        $name = $Matches[1]
        $value = $Matches[2]
        if ($allowed -notcontains $name) { throw "Unsupported setting on .env line $lineNumber." }
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length-2)
        }
        # Explicit terminal settings take precedence. Do not execute .env text.
        if ($value -and -not [Environment]::GetEnvironmentVariable($name, 'Process')) {
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
    foreach ($name in @('SPHEREX_INDEX_DIR', 'PULSR_COMMUNITY_DB')) {
        $value = [Environment]::GetEnvironmentVariable($name, 'Process')
        if ($value -and -not [IO.Path]::IsPathRooted($value)) {
            [Environment]::SetEnvironmentVariable($name, [IO.Path]::GetFullPath((Join-Path $BackendDir $value)), 'Process')
        }
    }
}
