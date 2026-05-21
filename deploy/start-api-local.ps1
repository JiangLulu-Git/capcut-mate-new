# CapCut Mate - local LAN debug (video + transition only)

# Use Ethernet IPv4 172.16.94.81 (NOT vEthernet 172.28.128.1)

#

#   cd D:\Skills_project\capcut-mate

#   powershell -ExecutionPolicy Bypass -File .\deploy\start-api-local.ps1



$IP = "172.16.94.81"



$env:DRAFT_URL    = "http://${IP}:30000/openapi/capcut-mate/v1/get_draft"

$env:DOWNLOAD_URL = "http://${IP}:30000/"



# Must match Jianying: Settings -> draft folder

$env:DRAFT_SAVE_PATH = "D:\JianyingPro Drafts"



$jianyingCandidates = @(

    $env:DRAFT_SAVE_PATH,

    "C:\JianyingPro v6.0.1\JianyingPro Drafts",

    "$env:USERPROFILE\Documents\JianyingPro Drafts"

)

if (-not (Test-Path -LiteralPath $env:DRAFT_SAVE_PATH)) {

    $found = $jianyingCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

    if ($found) { $env:DRAFT_SAVE_PATH = $found }

    else { Write-Warning "Draft folder missing: D:\JianyingPro Drafts — create it or fix path in Jianying settings." }

}



$exeRoots = @("C:\JianyingPro v6.0.1", "${env:LOCALAPPDATA}\JianyingPro\Apps")

foreach ($root in $exeRoots) {

    $exe = Join-Path $root "JianyingPro.exe"

    if (Test-Path -LiteralPath $exe) {

        $env:JIANYING_EXE_PATH = $exe

        break

    }

}



$env:ENABLE_APIKEY = "false"

$env:GEN_VIDEO_LOCAL_PATH_FALLBACK = "true"

$env:AUTO_EXPORT_AFTER_UPLOAD = "true"

$env:EXPORT_FRAMERATE_FPS = "25"

# Align draft timeline + export fps to first source clip (set false to force 25fps)

$env:EXPORT_ALIGN_SOURCE_FPS = "true"

# 不依赖 ffmpeg：画布跟随源片、剪映导出 HEVC、HTTP Range 边下边播

$env:EXPORT_CANVAS_FROM_SOURCE = "true"

$env:EXPORT_RESOLUTION = ""

$env:EXPORT_CODEC = "HEVC"

$env:EXPORT_MP4_WEB_OPTIMIZE = "false"

$env:EXPORT_COMPRESS_MODE = "off"
# auto_render 建草稿并发（导出仍串行），最大 5
$env:AUTO_RENDER_MAX_WORKERS = "5"



$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $ProjectRoot "main.py"))) {

    $ProjectRoot = "D:\Skills_project\capcut-mate"

}

Set-Location $ProjectRoot



Write-Host "=== CapCut Mate local ($IP) ==="

Write-Host "DOWNLOAD_URL=$env:DOWNLOAD_URL"

Write-Host "DRAFT_SAVE_PATH=$env:DRAFT_SAVE_PATH"

Write-Host "Docs:  http://${IP}:30000/docs"

Write-Host "Video: http://${IP}:30000/output/draft/OUTPUT.mp4"



if (Get-Command uv -ErrorAction SilentlyContinue) {

    uv run main.py

} else {

    python main.py

}


