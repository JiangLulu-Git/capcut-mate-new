# 叠化转场测试（单独运行，需另开终端已启动 API）

#

#   cd D:\Skills_project\capcut-mate

#   powershell -ExecutionPolicy Bypass -File .\deploy\test-dissolve-transition.ps1

#

# 导出成片并检测转场前几秒是否卡顿（需剪映在首页 + ffmpeg）:

#   powershell -ExecutionPolicy Bypass -File .\deploy\test-dissolve-transition.ps1 -Export

#

# 叠化 5 秒:

#   powershell -ExecutionPolicy Bypass -File .\deploy\test-dissolve-transition.ps1 -Export -TransitionDurationSec 5



param(

    [switch]$Export,

    [double]$TransitionDurationSec = 1.0

)



$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $ProjectRoot "main.py"))) {

    $ProjectRoot = "D:\Skills_project\capcut-mate"

}

Set-Location $ProjectRoot



$env:ENABLE_APIKEY = "false"

$env:SMOKE_API_BASE = "http://127.0.0.1:30000"



$argsList = @("tests\smoke_dissolve_transition_stutter.py", "--transition-duration-sec", "$TransitionDurationSec")

if ($Export) { $argsList += "--export" }



if (Get-Command uv -ErrorAction SilentlyContinue) {

    & uv run @argsList

} else {

    & python @argsList

}

exit $LASTEXITCODE


