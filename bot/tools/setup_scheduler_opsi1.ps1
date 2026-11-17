# setup_scheduler_opsi1.ps1: opsi1 daily 09:00 settle kemarin, scan baru, simulate, bet LIVE
# Jalankan sekali di PC target (no admin): powershell -ExecutionPolicy Bypass -File ".\setup_scheduler_opsi1.ps1"
# Portable: auto-detect repo root (clone bisa 1xbet atau 1rxrbrertr), handle py/python

$ErrorActionPreference = "Stop"
$ToolsDir = $PSScriptRoot
if (-not $ToolsDir) { $ToolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path }
$BotDir  = Split-Path $ToolsDir -Parent
$RepoRoot = Split-Path $BotDir -Parent
# RepoRoot = folder yang berisi bot/ (1xbet atau 1rxrbrertr)
$Runner  = Join-Path $ToolsDir "runner.py"

if (-not (Test-Path $Runner)) { Write-Error "Runner tidak ketemu: $Runner"; exit 1 }

# cari python launcher: py -> python -> python3 (pakai full path biar Task Scheduler tidak 0x80070002)
$PyExe = $null
$PyExePath = $null
foreach ($c in @("py","python","python3")) {
  try { $cmd = Get-Command $c -ErrorAction Stop; $PyExe = $c; $PyExePath = $cmd.Source; break } catch {}
}
if (-not $PyExePath) { Write-Error "Python tidak ketemu (py/python). Install Python 3.10+ dulu."; exit 1 }
Write-Host "Python : $PyExe -> $PyExePath"
Write-Host "Runner : $Runner"
Write-Host "RepoRoot : $RepoRoot  (WD untuk task)"

# UserId untuk S4U — butuh DOMAIN\user, bukan user saja
$UserId = $null
try { $UserId = (whoami) } catch {}
if (-not $UserId -or $UserId -notmatch "\\") {
  if ($env:USERDOMAIN -and $env:USERNAME) { $UserId = "$env:USERDOMAIN\$env:USERNAME" }
  elseif ($env:USERNAME) { $UserId = "$env:USERNAME" }
}
Write-Host "UserId : $UserId"

$Tasks = @(
  @{ Name="1xbet-daily-0900"; At="09:00"; Job="daily --live"; Desc="1xbet daily 09:00 settle kemarin->scan->simulate->bet LIVE 1000/match" }
)

foreach ($t in $Tasks) {
  try { Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue } catch {}
  $action    = New-ScheduledTaskAction -Execute $PyExePath -Argument "`"$Runner`" --job $($t.Job)" -WorkingDirectory $RepoRoot
  $trigger   = New-ScheduledTaskTrigger -Daily -At $t.At
  $settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15)
  # S4U = jalan tanpa password, tetap jalan walau tidak login. Fallback ke Interactive jika S4U ditolak
  try {
    $principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType S4U -RunLevel Limited
    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $t.Desc | Out-Null
  } catch {
    Write-Host "  S4U gagal untuk $($t.Name): $($_.Exception.Message) -> coba Interactive"
    $principal2 = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger -Principal $principal2 -Settings $settings -Description $t.Desc | Out-Null
  }
  Write-Host "  created $($t.Name) $($t.At) --job $($t.Job)"
}

Write-Host "`n=== Verify ==="
Get-ScheduledTask -TaskName "1xbet*" | Format-Table TaskName,State -AutoSize
Get-ScheduledTask -TaskName "1xbet*" | Get-ScheduledTaskInfo | Format-Table TaskName,LastRunTime,NextRunTime -AutoSize
Write-Host "`nTest manual: Start-ScheduledTask -TaskName 1xbet-daily-0900"
Write-Host "Test dry (tanpa bet): py `"$Runner`" --job daily"
Write-Host "Log: $RepoRoot\bot\data\runner.log  |  Ledger bet: $RepoRoot\bot\data\bets.jsonl"
Write-Host "Hapus semua: Get-ScheduledTask -TaskName '1xbet*' | Unregister-ScheduledTask -Confirm:`$false"
