# 本机局域网调试步骤（首版导出）

> **新机器首次部署**请先看 [NEW-ENV-SETUP.md](./NEW-ENV-SETUP.md)（换 IP、剪映路径、venv、防火墙完整清单）。

适用：服务跑在本机 Windows，同一局域网其它机器调用 API、下载成片。  
本机以太网 IP：**172.16.94.81**（勿用 vEthernet `172.28.128.1`）。

---

## 一、环境准备（一次性）

### 1. Python 与依赖

```powershell
cd D:\Skills_project\capcut-mate
uv sync
uv pip install -e ".[windows]"
```

### 2. 剪映专业版（建议 6.x）

- 安装并打开一次剪映  
- **设置 → 草稿位置** 记下路径（须与下面 `DRAFT_SAVE_PATH` 一致）

### 3. 防火墙（已完成）

已添加规则 `CapCut-Mate-API-30000`，放行 TCP **30000** 入站（专用/域网络）。

验证：

```powershell
Get-NetFirewallRule -DisplayName "CapCut-Mate-API-30000"
```

---

## 二、启动 API

**推荐**（自动设置环境变量）：

```powershell
cd D:\Skills_project\capcut-mate
powershell -ExecutionPolicy Bypass -File .\deploy\start-api-local.ps1
```

或手动：

```powershell
$env:DOWNLOAD_URL = "http://172.16.94.81:30000"
$env:DRAFT_URL    = "http://172.16.94.81:30000/openapi/capcut-mate/v1/get_draft"
$env:DRAFT_SAVE_PATH = "你的剪映草稿根目录"
$env:ENABLE_APIKEY = "false"
$env:GEN_VIDEO_LOCAL_PATH_FALLBACK = "true"
cd D:\Skills_project\capcut-mate
python main.py
```

保持窗口不关。日志应出现 `协作编辑演示页: /demo/`。

---

## 三、连通性自检

| 位置 | 命令/地址 |
|------|-----------|
| 本机 | http://127.0.0.1:30000/docs |
| 本机 | http://172.16.94.81:30000/openapi.json |
| 局域网其它电脑 | `curl http://172.16.94.81:30000/openapi.json` |

能返回 JSON 即可。

---

## 四、首版自动成片（调用方要 downloadable 的 video_url）

### 接口

`POST http://172.16.94.81:30000/openapi/capcut-mate/v1/auto_render`

### 请求示例

```json
{
  "videos": [
    {
      "video_url": "http://可公网或局域网访问的素材/a.mp4",
      "use_full_duration": true
    }
  ],
  "default_transition": "叠化",
  "default_transition_duration": 1000000,
  "wait_export": true,
  "export_timeout_sec": 1200,
  "api_base_url": "http://172.16.94.81:30000"
}
```

说明：

- **素材 `video_url`**：必须是 **跑 API 的本机** 能 HTTP 下载的地址。  
- **`wait_export: true`**：创建草稿 + 转场 + 本机剪映导出，一次返回成片（不传 `captions` 或传 `[]` 即无字幕）。  
- **`api_base_url`**：必须与 `DOWNLOAD_URL` 同主机（`172.16.94.81`），勿用 `127.0.0.1`。

### 成功响应

```json
{
  "export_status": "completed",
  "video_url": "http://172.16.94.81:30000/output/draft/xxxx.mp4",
  "draft_id": "...",
  "draft_url": "..."
}
```

调用方用 `video_url` 直接下载 mp4。

### 导出时注意

- 本机剪映需能被自动化控制（建议前台、版本 6.x）  
- 导出期间勿关 API 窗口  

---

## 五、演示页（可选）

浏览器打开：

http://172.16.94.81:30000/demo/

- **API 地址** 填：`http://172.16.94.81:30000`  
- 当前演示页默认 `wait_export: false`（只建草稿，协作编辑用）  
- **首版导出** 请用上一节 API 或 Postman，设 `wait_export: true`  

---

## 六、协作编辑 B 方案（与首版分开）

首版跑通后再做：

1. 本机安装 **剪映小助手**（`desktop-client\dist\capcut-mate-windows-x64-installer.exe`）  
2. 小助手配置：API `http://172.16.94.81:30000`，草稿目录与剪映一致  
3. `auto_render` 使用 `wait_export: false`  
4. 演示页「编辑」→ 小助手下载 → 本机改 →「完成」回传 → 服务端再导出  

---

## 七、常见问题

| 现象 | 处理 |
|------|------|
| 外机访问不了 30000 | 确认 IP 为 `172.16.94.81`、防火墙规则、API 已启动 |
| `video_url` 仍是 `D:\...` 路径 | 重启 API，确认已设 `DOWNLOAD_URL` 且代码含 `media_url` 转换 |
| 导出 `failed`、时长≤3秒 | 草稿无有效素材，检查视频 URL 是否下载成功 |
| 素材下载失败 | 本机 `curl -I <视频URL>` 是否 200 |

---

## 八、上云（腾讯云）

换服务器时使用 `deploy\start-api.ps1`（公网 IP `129.211.23.199`），步骤类似，剪映与 API 均在云 Windows 上。
