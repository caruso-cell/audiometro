param(
    [string]$Url
)

$logPath = Join-Path $PSScriptRoot 'audiometria_protocol.log'
function Write-ProtocolLog {
    param([string]$Message)
    try {
        $timestamp = (Get-Date).ToString('s')
        Add-Content -Path $logPath -Value "[$timestamp] $Message" -Encoding UTF8
    } catch { }
}

Write-ProtocolLog("Avvio protocol handler. URL ricevuto: {0}" -f $Url)

$exePath = Join-Path $PSScriptRoot 'Audiometro.exe'
Write-ProtocolLog("Percorso eseguibile atteso: {0}" -f $exePath)
if (-not (Test-Path -LiteralPath $exePath)) {
    Write-ProtocolLog("ERRORE: eseguibile non trovato")
    exit 1
}

function Add-ArgumentsFromPair {
    param(
        [System.Collections.Generic.List[string]]$Collector,
        [string]$Key,
        [string]$Value
    )
    if ([string]::IsNullOrWhiteSpace($Key)) { return }
    $normalized = $Key.Trim().TrimStart('-')
    if ([string]::IsNullOrWhiteSpace($normalized)) { return }
    $Collector.Add("--$normalized")
    if ($Value) {
        $Collector.Add($Value)
    }
}

$arguments = [System.Collections.Generic.List[string]]::new()

if (-not $Url) {
    Write-ProtocolLog("Avvio eseguibile senza argomenti")
    Start-Process -FilePath $exePath -WorkingDirectory $PSScriptRoot
    exit 0
}

try {
    $uri = [Uri]::new($Url)
} catch {
    $uri = $null
}

if ($uri) {
    if ($uri.Host -and $uri.Host -ne 'localhost') {
        Write-ProtocolLog("Host ignorato nel protocollo: {0}" -f $uri.Host)
    }

    $query = $uri.Query.TrimStart('?')
    if ($query) {
        foreach ($pair in $query -split '&') {
            if (-not $pair) { continue }
            $kv = $pair -split '=', 2
            $key = [Uri]::UnescapeDataString($kv[0])
            $value = if ($kv.Count -gt 1) { [Uri]::UnescapeDataString($kv[1]) } else { '' }
            Add-ArgumentsFromPair -Collector $arguments -Key $key -Value $value
        }
    }

    $path = $uri.AbsolutePath.Trim('/')
    if ($path) {
        foreach ($segment in $path -split '/') {
            if (-not $segment) { continue }
            $decoded = [Uri]::UnescapeDataString($segment)
            if ($decoded.Contains('=')) {
                $kv = $decoded -split '=', 2
                Add-ArgumentsFromPair -Collector $arguments -Key $kv[0] -Value ($kv[1])
            }
        }
    }

    $fragment = $uri.Fragment.TrimStart('#')
    if ($fragment) {
        foreach ($piece in $fragment -split '&') {
            if (-not $piece) { continue }
            $decoded = [Uri]::UnescapeDataString($piece)
            if ($decoded.Contains('=')) {
                $kv = $decoded -split '=', 2
                Add-ArgumentsFromPair -Collector $arguments -Key $kv[0] -Value ($kv[1])
            }
        }
    }
} else {
    $decodedUrl = [Uri]::UnescapeDataString($Url)
    foreach ($piece in $decodedUrl -split '\s+') {
        if (-not $piece) { continue }
        if ($piece.Contains('=')) {
            $kv = $piece -split '=', 2
            Add-ArgumentsFromPair -Collector $arguments -Key $kv[0] -Value ($kv[1])
        }
    }
}

if ($arguments.Count -eq 0) {
    Write-ProtocolLog("Avvio eseguibile senza argomenti")
    Start-Process -FilePath $exePath -WorkingDirectory $PSScriptRoot
} else {
    Write-ProtocolLog("Avvio eseguibile con argomenti: {0}" -f ($arguments -join ' '))
    Start-Process -FilePath $exePath -ArgumentList $arguments -WorkingDirectory $PSScriptRoot
}
