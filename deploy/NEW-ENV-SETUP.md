# 新环境配置步骤（Windows）

每次把项目部署到**新电脑**或**新目录**时，按本清单操作。  
适用：`auto_render` 异步建稿 + 剪映自动导出 + 字幕/转场。

> 下文命令默认项目路径为 `D:\capcut-mate`，IP 为 `172.16.94.161`，请按实际替换。  
> **IP 必须是「启动 API 服务的那台机器」的局域网 IPv4**（运行 `start-api-local.ps1` 的电脑上用 `ipconfig` 查到的以太网地址）。  
> 调用方、浏览器、其它电脑访问时，都填这一地址；**不要**填调用方自己的 IP，也不要填 `127.0.0.1`（除非只在同一台机器本机测）。  
> PowerShell 多行续行用 **反引号 `` ` ``**，不要用 CMD 的 `^`。

---

## 附录 A：完整命令清单（推荐按顺序执行）

### A.1 进入项目

```powershell
cd D:\capcut-mate
```

### A.2 查 IP（在**启动服务的那台机器**上执行）

```powershell
ipconfig
```

选用该机器**以太网** IPv4（例如 `172.16.94.161`），**不要**用 Hyper-V 虚拟网卡 `172.28.x.x`。  
此 IP 将用于：`start-api-local.ps1` 的 `$IP`、`auto_render_test.json` 的 `api_base_url`，以及其它机器访问 API / 下载 mp4。

### A.3 改配置（手动编辑文件）

> `$IP` / `api_base_url` 填 **A.2 在 API 服务器上查到的 IP**，与剪映、Python 是否在同一台无关——通常三者同一台 Windows。

用编辑器打开 `deploy\start-api-local.ps1`，修改：

```powershell
$IP = "172.16.94.161"
$env:DRAFT_SAVE_PATH = "D:\JianyingPro Drafts"
```

同步修改根目录 `auto_render_test.json` 里的：

```json
"api_base_url": "http://172.16.94.161:30000"
```

### A.4 创建虚拟环境并安装依赖（无 uv）

```powershell
cd D:\capcut-mate
Remove-Item -Recurse -Force .venv -ErrorAction SilentlyContinue
python -m venv .venv
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[windows]"
```

有 **uv** 时可用：

```powershell
cd D:\capcut-mate
uv sync
uv pip install -e ".[windows]"
```

### A.5 防火墙放行 30000（管理员 PowerShell，局域网需要）

```powershell
New-NetFirewallRule `
  -DisplayName "CapCut-Mate-API-30000" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 30000 `
  -Action Allow `
  -Profile Private,Domain
```

验证：

```powershell
Get-NetFirewallRule -DisplayName "CapCut-Mate-API-30000"
```

### A.6 启动 API（单独开一个 PowerShell 窗口，保持运行）

```powershell
cd D:\capcut-mate
powershell -ExecutionPolicy Bypass -File .\deploy\start-api-local.ps1
```

### A.7 连通性自检（新开一个 PowerShell 窗口）

在 **API 服务器本机** 可测：

```powershell
curl.exe http://127.0.0.1:30000/openapi.json
```

**同一局域网其它机器** 或正式调用时，须用 **服务器 IP**（不要用 `127.0.0.1`）：

```powershell
curl.exe http://172.16.94.161:30000/openapi.json
```

浏览器打开：

- 本机：http://127.0.0.1:30000/docs  
- 局域网 / 对外：http://172.16.94.161:30000/docs（`172.16.94.161` 换成服务器 IP）

### A.8 打开剪映

手动操作：启动剪映专业版 → 停在**首页草稿列表**（导出前必须）。

---

## 附录 B：测试命令

以下命令在**第二个 PowerShell 窗口**执行（API 窗口保持运行）。

### B.1 激活虚拟环境（每个新窗口先执行）

```powershell
cd D:\capcut-mate
.\.venv\Scripts\Activate.ps1
```

### B.2 仅建草稿（不导出，约 30 秒）

```powershell
python tests/manual_test_draft_only.py
```

### B.3 异步提交 + 自动轮询直到导出完成

先确认 `auto_render_test.json` 中 IP、`wait_export: true` 已改好，然后：

```powershell
python tests/manual_auto_export_poll.py
```

### B.4 手动 curl 提交 auto_render

```powershell
cd D:\capcut-mate
curl.exe -X POST "http://172.16.94.161:30000/openapi/capcut-mate/v1/auto_render" `
  -H "Content-Type: application/json; charset=utf-8" `
  --data-binary "@auto_render_test.json"
```

### B.5 查询异步任务状态（单次）

将 `TASK_ID` 换成上一步返回的 `task_id`：

```powershell
curl.exe -X POST "http://172.16.94.161:30000/openapi/capcut-mate/v1/auto_render_status" `
  -H "Content-Type: application/json" `
  -d "{\"task_id\":\"TASK_ID\"}"
```

PowerShell 写法：

```powershell
$body = @{ task_id = "TASK_ID" } | ConvertTo-Json
Invoke-RestMethod -Method POST `
  -Uri "http://172.16.94.161:30000/openapi/capcut-mate/v1/auto_render_status" `
  -ContentType "application/json" `
  -Body $body | ConvertTo-Json -Depth 5
```

### B.6 自动轮询直到 completed / failed

```powershell
$API = "http://172.16.94.161:30000"
$taskId = "TASK_ID"

while ($true) {
  $resp = Invoke-RestMethod -Method POST `
    -Uri "$API/openapi/capcut-mate/v1/auto_render_status" `
    -ContentType "application/json" `
    -Body "{`"task_id`":`"$taskId`"}"
  $r = if ($resp.data) { $resp.data } else { $resp }
  Write-Host (Get-Date -Format "HH:mm:ss") `
    "status=$($r.export_status) progress=$($r.progress) video=$($r.video_url)"
  if ($r.export_status -in @("completed","failed","skipped")) {
    $r | ConvertTo-Json -Depth 5
    break
  }
  Start-Sleep -Seconds 5
}
```

### B.7 单元测试（不依赖剪映）

```powershell
python tests/test_auto_render_build.py
```

### B.8 退出虚拟环境

```powershell
deactivate
```

---

## 附录 C：排查命令

### C.1 检查草稿是否在磁盘

```powershell
$draftId = "20260521110428df51dd6c"
$savePath = "D:\JianyingPro Drafts"

Test-Path "D:\capcut-mate\output\draft\$draftId\draft_content.json"
Test-Path "$savePath\$draftId\draft_content.json"
```

### C.2 手动把草稿装进剪映目录

```powershell
cd D:\capcut-mate
.\.venv\Scripts\Activate.ps1
python -c @"
import sys; sys.path.insert(0, '.')
import config
from src.service.auto_render import _install_draft_to_jianying
draft_id = '你的draft_id'
print('DRAFT_SAVE_PATH =', config.DRAFT_SAVE_PATH)
print('install =', _install_draft_to_jianying(draft_id))
"@
```

### C.3 查看最近日志

```powershell
Get-Content D:\capcut-mate\logs\capcut-mate.log -Tail 80
```

### C.4 查看字幕在草稿里的位置参数

```powershell
$draftId = "你的draft_id"
Get-Content "D:\JianyingPro Drafts\$draftId\draft_content.json" -Raw |
  ConvertFrom-Json |
  ForEach-Object { $_.tracks } |
  Where-Object { $_.type -eq "text" } |
  ForEach-Object { $_.segments[0].clip.transform.y }
```

---

## 0. 拷贝项目时注意

| 建议 | 说明 |
|------|------|
| ✅ 拷贝源码、`output/`、`config/` | 正常 |
| ❌ **不要**直接沿用旧机器的 `.venv` | Windows 虚拟环境写死旧路径，换机后常无法使用 |
| ✅ 新机器上**重建**虚拟环境 | 见附录 A.4 |

---

## 1. 必改配置（换机器必做）

### 1.1 查本机局域网 IP（在**运行 API 的服务器**上执行）

```powershell
ipconfig
```

使用**以太网** IPv4，**不要**用 Hyper-V 虚拟网卡 `172.28.x.x`。  
**此 IP 是 API 服务所在机器的地址**，不是调用接口的客户端地址。

### 1.2 编辑 `deploy/start-api-local.ps1`

```powershell
$IP = "172.16.94.161"
$env:DRAFT_SAVE_PATH = "D:\JianyingPro Drafts"
```

脚本会自动设置 `DOWNLOAD_URL`、`DRAFT_URL`。

### 1.3 `auto_render` 请求体

```json
"api_base_url": "http://172.16.94.161:30000"
```

须与 **API 服务器** 的 `$IP` 一致（即 `start-api-local.ps1` 所在机器的 IP），否则返回的 `draft_url`、`video_url` 会指向错误主机。

---

## 2. 安装 Python 依赖

需要 **Python 3.11+**。完整命令见 **附录 A.4**。

`.[windows]` 含剪映自动化依赖，**必装**。

---

## 3. 安装剪映专业版

1. 安装剪映专业版（建议 6.x），至少打开一次  
2. **设置 → 草稿位置** 与 `DRAFT_SAVE_PATH` 一致  

---

## 4. 防火墙

完整命令见 **附录 A.5**。仅本机 `127.0.0.1` 访问可跳过。

---

## 5. 启动 API

完整命令见 **附录 A.6**。日志出现 `Uvicorn running on http://0.0.0.0:30000` 即成功。

---

## 6. 连通性自检

完整命令见 **附录 A.7**。

---

## 7. 功能验证

| 场景 | 命令 |
|------|------|
| 仅建草稿 | 附录 B.2 |
| 自动导出+轮询 | 附录 B.3 |
| curl 提交 | 附录 B.4 |
| 查 task 状态 | 附录 B.5 / B.6 |

导出前剪映须在**首页**，导出过程中勿操作键鼠。

---

## 8. `auto_render` 常用参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `async_mode` | `true` | 返回 `task_id`，用 `auto_render_status` 查 |
| `wait_export` | 视场景 | `true` 导出；`false` 只建稿 |
| `font_size` | `15` | 全局字号；单条 caption 可单独设 |
| `caption_bottom_margin_px` | `10` | 自动底字幕位置 |
| `validate_caption_timeline` | `true` | 字幕须覆盖成片全长（微秒） |

示例请求体：根目录 `auto_render_test.json`。

---

## 9. 常见问题

### 9.1 `未找到名为 xxx 的剪映草稿`

排查命令见 **附录 C.1、C.2**；重启剪映并停首页。

### 9.2 剪映里看不到草稿

`DRAFT_SAVE_PATH` 与剪映设置不一致，或需重启剪映。

### 9.3 局域网访问不了

检查 IP、防火墙（A.5）、API 是否在跑（A.6）。

### 9.4 字幕时间校验失败

换视频后重算 `captions` 的 `start`/`end`，参考响应 `timeline_duration_us`。

### 9.5 `JianyingController unavailable`

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[windows]"
```

---

## 10. 新环境速查表

```
□ A.2  在 API 服务器上 ipconfig，记下该机器以太网 IP
□ A.3  改 start-api-local.ps1 + auto_render_test.json（IP = 服务器 IP）
□ A.4  重建 .venv，pip install -e ".[windows]"
□ A.5  防火墙 30000（局域网）
□ A.6  启动 API（独立窗口）
□ A.7  curl /docs 自检
□      剪映打开到首页
□ B.2  或 B.3 跑测试
```

---

## 相关文档

- [auto_render.zh.md](../docs/auto_render.zh.md) — **自动化成片 / 查询状态 API 文档**
- [LOCAL-DEBUG.md](./LOCAL-DEBUG.md) — 局域网调试细节  
- [QUICKSTART-VIDEO-ONLY.md](./QUICKSTART-VIDEO-ONLY.md) — 叠化/转场测试  
- `auto_render_test.json` — 异步导出 + 多字幕示例
