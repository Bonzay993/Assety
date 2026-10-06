param(
    [ValidateSet('start', 'stop', 'status', 'test')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localRoot = Join-Path $projectRoot '.local'
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$mongoPath = Join-Path $localRoot 'mongodb\bin\mongod.exe'
$statePath = Join-Path $localRoot 'processes.json'
$localUrl = 'http://127.0.0.1:5001'
Set-Location -LiteralPath $projectRoot

function Get-ManagedProcess($Record) {
    if ($null -eq $Record) { return $null }
    $managedProcess = Get-Process -Id $Record.Pid -ErrorAction SilentlyContinue
    if ($managedProcess -and $managedProcess.Path -eq $Record.Exe -and
        $managedProcess.StartTime.ToUniversalTime().Ticks.ToString() -eq $Record.StartedAt) {
        return $managedProcess
    }
    return $null
}

function Get-ProcessRecord($ManagedProcess, $ExpectedPath) {
    return @{
        Pid = $ManagedProcess.Id
        Exe = $ExpectedPath
        StartedAt = $ManagedProcess.StartTime.ToUniversalTime().Ticks.ToString()
    }
}

function Save-State {
    $script:processState | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
}

function Test-Port($Port) {
    $portClient = New-Object Net.Sockets.TcpClient
    try {
        $portClient.Connect('127.0.0.1', $Port)
        return $true
    } catch { return $false }
    finally { $portClient.Dispose() }
}

$processState = @{ Mongo = $null; Flask = $null }
if (Test-Path -LiteralPath $statePath) {
    $savedState = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $processState.Mongo = $savedState.Mongo
    $processState.Flask = $savedState.Flask
}

if ($Action -eq 'stop') {
    foreach ($serviceName in @('Flask', 'Mongo')) {
        $managedProcess = Get-ManagedProcess $processState[$serviceName]
        if ($managedProcess) {
            if ($serviceName -eq 'Flask') {
                # The Windows venv launcher owns a child Python server process.
                & taskkill.exe /PID $managedProcess.Id /T /F | Out-Null
                if ($LASTEXITCODE -ne 0) { throw 'Could not stop the local Flask process tree.' }
            } else {
                $mongoShutdownCode = @'
from pymongo import MongoClient
from pymongo.errors import AutoReconnect
client = MongoClient('mongodb://127.0.0.1:27019', serverSelectionTimeoutMS=3000)
try:
    client.admin.command('shutdown')
except AutoReconnect:
    pass
finally:
    client.close()
'@
                & $pythonPath -c $mongoShutdownCode
                if ($LASTEXITCODE -ne 0) { throw 'Could not shut down local MongoDB.' }
            }
            if (!$managedProcess.WaitForExit(10000)) { throw ($serviceName + ' did not stop within 10 seconds.') }
        }
        $processState[$serviceName] = $null
    }
    if (Test-Path -LiteralPath $localRoot) { Save-State }
    Write-Output 'Local Assety stopped. Test accounts and inventory are retained.'
    exit 0
}

if ($Action -eq 'status') {
    foreach ($serviceName in @('Mongo', 'Flask')) {
        $managedProcess = Get-ManagedProcess $processState[$serviceName]
        Write-Output ($serviceName + ': ' + $(if ($managedProcess) { 'running (PID ' + $managedProcess.Id + ')' } else { 'stopped' }))
    }
    Write-Output $localUrl
    exit 0
}

if (Test-Path -LiteralPath (Join-Path $projectRoot 'env.py')) {
    throw 'env.py can override the isolated database settings. Rename it before using this local launcher.'
}
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $mongoPath)) {
    throw 'Local Python or MongoDB is missing. See LOCAL_TESTING.md for setup.'
}
New-Item -ItemType Directory -Path (Join-Path $localRoot 'data') -Force | Out-Null
$secretPath = Join-Path $localRoot 'secret-key'
if (!(Test-Path -LiteralPath $secretPath)) {
    $secretValue = & $pythonPath -c 'import secrets; print(secrets.token_hex(32))'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local signing key.' }
    Set-Content -LiteralPath $secretPath -Value $secretValue -Encoding ASCII
}
$env:MONGO_URI = 'mongodb://127.0.0.1:27019/assety_dev'
$env:MONGO_DBNAME = 'assety_dev'
$env:ASSETY_TEST_MONGO_URI = 'mongodb://127.0.0.1:27019'
$env:SECRET_KEY = (Get-Content -LiteralPath $secretPath -Raw).Trim()
$env:IP = '127.0.0.1'
$env:PORT = '5001'
$env:FLASK_DEBUG = '0'
$env:SENDGRID_API_KEY = ''
$env:MAIL_DEFAULT_SENDER = ''
$env:DYNO = ''

if (!(Get-ManagedProcess $processState.Mongo)) {
    if (Test-Port 27019) { throw 'Port 27019 is already occupied by another process.' }
    $databasePath = (Join-Path $localRoot 'data') | ConvertTo-Json -Compress
    $mongoConfigPath = Join-Path $localRoot 'mongod.cfg'
    @"
storage:
  dbPath: $databasePath
  wiredTiger:
    engineConfig:
      cacheSizeGB: 0.25
net:
  bindIp: 127.0.0.1
  port: 27019
"@ | Set-Content -LiteralPath $mongoConfigPath -Encoding ASCII
    $mongoProcess = Start-Process -FilePath $mongoPath -ArgumentList @('--config', ('"' + $mongoConfigPath + '"')) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localRoot 'mongo.log') -RedirectStandardError (Join-Path $localRoot 'mongo-error.log')
    $processState.Mongo = Get-ProcessRecord $mongoProcess $mongoPath
    Save-State
}

& $pythonPath -c "from pymongo import MongoClient; c = MongoClient('mongodb://127.0.0.1:27019', serverSelectionTimeoutMS=20000); c.admin.command('ping'); c.close()"
if ($LASTEXITCODE -ne 0) { throw 'Local MongoDB did not become ready. Check .local\mongo.log.' }

if ($Action -eq 'test') {
    & $pythonPath -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & npm.cmd test -- --runInBand
    exit $LASTEXITCODE
}

if (!(Get-ManagedProcess $processState.Flask)) {
    if (Test-Port 5001) { throw 'Port 5001 is already occupied by another process.' }
    $flaskProcess = Start-Process -FilePath $pythonPath -ArgumentList 'app.py' -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $localRoot 'flask.log') -RedirectStandardError (Join-Path $localRoot 'flask-error.log')
    $processState.Flask = Get-ProcessRecord $flaskProcess $pythonPath
    Save-State
}

$appReady = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    try {
        $response = Invoke-WebRequest -Uri $localUrl -UseBasicParsing -TimeoutSec 1
        if ($response.StatusCode -eq 200) { $appReady = $true; break }
    } catch { }
    if (!(Get-ManagedProcess $processState.Flask)) { break }
    Start-Sleep -Milliseconds 500
}
if (!$appReady) { throw 'Local Assety did not become ready. Check .local\flask-error.log.' }
Write-Output ('Assety is ready: ' + $localUrl)
Write-Output 'Database: assety_dev on this computer (127.0.0.1:27019).'
Write-Output 'Create a test account using Sign Up. Email delivery is disabled locally.'
