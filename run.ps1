param([int]$Port = 8000)
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) { $python = $pythonCommand.Source }
else { $python = 'C:\Users\zoeyt\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
$env:PORT = $Port
& $python (Join-Path $PSScriptRoot 'app\server.py')
