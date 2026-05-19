# CapCut Mate - 腾讯云轻量服务器启动脚本

# 公网 IP: 129.211.23.199

# 剪映 v6.0.1 目录: C:\JianyingPro v6.0.1

# 用法（管理员 PowerShell）:

#   cd D:\capcut-mate

#   powershell -ExecutionPolicy Bypass -File .\deploy\start-api.ps1



$IP = "129.211.23.199"

$JianyingRoot = "C:\JianyingPro v6.0.1"



$env:DRAFT_URL    = "http://${IP}:30000/openapi/capcut-mate/v1/get_draft"

$env:DOWNLOAD_URL = "http://${IP}:30000/"



# 剪映草稿根目录：其下为 {draft_id}\draft_content.json

# 须在剪映「设置 → 草稿位置」中设为同一路径（若不同，以剪映里显示的为准并改此行）

$env:DRAFT_SAVE_PATH = Join-Path $JianyingRoot "JianyingPro Drafts"



# v6.0.1 绿色版常见 exe 位置（按顺序检测）

$exeCandidates = @(

    (Join-Path $JianyingRoot "JianyingPro.exe"),

    (Join-Path $JianyingRoot "剪映专业版.exe"),

    (Join-Path $JianyingRoot "bin\JianyingPro.exe"),

    (Join-Path $JianyingRoot "CapCut\JianyingPro.exe")

)

$jianyingExe = $null

foreach ($p in $exeCandidates) {

    if (Test-Path -LiteralPath $p) {

        $jianyingExe = $p

        break

    }

}

if ($jianyingExe) {

    $env:JIANYING_EXE_PATH = $jianyingExe

} else {

    Write-Warning "未找到剪映 exe，请检查 $JianyingRoot 下文件名，并手动设置 JIANYING_EXE_PATH"

    $env:JIANYING_EXE_PATH = (Join-Path $JianyingRoot "JianyingPro.exe")

}



$env:ENABLE_APIKEY = "false"

$env:GEN_VIDEO_LOCAL_PATH_FALLBACK = "true"

$env:AUTO_EXPORT_AFTER_UPLOAD = "true"

$env:EXPORT_FRAMERATE_FPS = "25"

# 演示页「下载剪映小助手」链接（安装包放到 static\local_edit\releases\ 后取消下一行注释）
# $env:MATE_INSTALL_URL = "http://${IP}:30000/demo/releases/capcut-mate-windows-x64-installer.exe"

# 有腾讯云 COS 时取消注释并填写

# $env:COS_SECRET_ID  = ""

# $env:COS_SECRET_KEY = ""

# $env:COS_BUCKET_NAME = ""

# $env:COS_REGION      = "ap-guangzhou"



$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $ProjectRoot "main.py"))) {

    $ProjectRoot = "D:\capcut-mate"

}

Set-Location $ProjectRoot

Write-Host "项目目录: $ProjectRoot"

Write-Host "剪映目录: $JianyingRoot"

Write-Host "JIANYING_EXE_PATH=$env:JIANYING_EXE_PATH"

Write-Host "DRAFT_SAVE_PATH=$env:DRAFT_SAVE_PATH"

Write-Host "DRAFT_URL=$env:DRAFT_URL"

Write-Host "演示页: http://${IP}:30000/demo/"

Write-Host "API 文档: http://${IP}:30000/docs"

if (-not (Test-Path -LiteralPath $env:DRAFT_SAVE_PATH)) {

    Write-Warning "草稿目录尚不存在: $($env:DRAFT_SAVE_PATH) — 请先在剪映里设置草稿位置或手动创建"

}

uv run main.py

