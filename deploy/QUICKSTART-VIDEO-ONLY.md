# 仅视频 + 转场（auto_render）快速启动

当前测试范围：**多段视频拼接 + 段间转场 + 导出成片 URL**，不含字幕、不含小助手。

本机 API 地址：**http://172.16.94.81:30000**（以太网 IPv4，勿用 172.28.128.1）。

---

## 1. 一次性准备

```powershell
cd D:\Skills_project\capcut-mate
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[windows]"
```

（若已安装 [uv](https://github.com/astral-sh/uv)，也可用 `uv sync` 与 `uv pip install -e ".[windows]"`。）

- 安装 **剪映 6.x**，在设置里确认 **草稿位置**
- 防火墙已放行 **TCP 30000**（规则名 `CapCut-Mate-API-30000`）

---

## 2. 启动服务

```powershell
cd D:\Skills_project\capcut-mate
powershell -ExecutionPolicy Bypass -File .\deploy\start-api-local.ps1
```

看到 `Uvicorn running on http://0.0.0.0:30000` 即成功，**不要关窗口**。

自检：浏览器打开 http://172.16.94.81:30000/docs

---

## 3. 调用 auto_render（默认异步，不阻塞 HTTP）

**POST** `http://172.16.94.81:30000/openapi/capcut-mate/v1/auto_render`

默认 `async_mode: true`：接口**立即返回** `task_id`，后台建草稿；`wait_export: true` 时导出走 `gen_video` 队列（剪映导出仍全局串行，但不再占满 HTTP 连接）。

**POST** `http://172.16.94.81:30000/openapi/capcut-mate/v1/auto_render_status`

```json
{ "task_id": "上一步返回的 task_id" }
```

轮询直至 `export_status` 为 `completed` / `failed` / `skipped`。

**建草稿并发**（默认 5，上限 5，与剪映导出无关）：启动前可设  
`$env:AUTO_RENDER_MAX_WORKERS = "5"`（勿超过 5）。

同步阻塞（旧行为）：请求里加 `"async_mode": false`。

### 两段视频 + 段间叠化 1 秒（推荐测试）

```json
{
  "videos": [
    {
      "video_url": "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4",
      "use_full_duration": true
    },
    {
      "video_url": "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4",
      "use_full_duration": true
    }
  ],
  "default_transition": "叠化",
  "default_transition_duration": 1000000,
  "wait_export": true,
  "export_timeout_sec": 1800,
  "api_base_url": "http://172.16.94.81:30000"
}
```

（两段可换成你的 `a.mp4` / `b.mp4`；第一段末尾自动叠化，最后一段无转场。）

- `video_url`：本机必须能 HTTP 下载  
- 转场名须为剪映支持的名称（如「叠化」「3D空间」等）  
- 不传 `captions` 或 `"captions": []`：无字幕  

### 成功响应

```json
{
  "export_status": "completed",
  "video_url": "http://172.16.94.81:30000/output/draft/xxxx.mp4",
  "draft_id": "...",
  "message": "自动化成片完成"
}
```

`video_url` 给调用方直接下载。

---

## 4. PowerShell 一键请求示例

```powershell
$demo = "https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-360p.mp4"
$body = @{
  videos = @(
    @{ video_url = $demo; use_full_duration = $true },
    @{ video_url = $demo; use_full_duration = $true }
  )
  default_transition = "叠化"
  default_transition_duration = 1000000
  wait_export = $true
  export_timeout_sec = 1800
  api_base_url = "http://172.16.94.81:30000"
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post `
  -Uri "http://172.16.94.81:30000/openapi/capcut-mate/v1/auto_render" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

---

## 5. 仅测建草稿、不导出（快）

```json
"wait_export": false
```

返回 `export_status: "skipped"`，不打开剪映导出。

---

## 6. 浏览器边下边播（直接用 video_url）

`auto_render` 返回的 **`video_url` 就是播放地址**：

```html
<video src="返回的 video_url" controls playsinline preload="metadata"></video>
```

默认策略（**无需 ffmpeg**）：

- 画布宽高 = 第一段源视频尺寸
- 剪映导出 **HEVC（H.265）**，同画质下体积更小、下载更快
- `/output/draft/*.mp4` 支持 **HTTP Range（206）** + 缓存头

`deploy/start-api-local.ps1` 已设置：`EXPORT_CODEC=HEVC`、`EXPORT_CANVAS_FROM_SOURCE=true`、`EXPORT_MP4_WEB_OPTIMIZE=false`。

## 7. 叠化转场卡顿测试（与启动分开，另开终端）

先保持第 2 节 API 窗口运行，再开一个新 PowerShell：

```powershell
cd D:\Skills_project\capcut-mate
powershell -ExecutionPolicy Bypass -File .\deploy\test-dissolve-transition.ps1
```

仅校验时间轴重叠是否正确（不导出、较快）。

要**导出成片**并用 ffmpeg 检测**转场开始后前几秒**是否画面冻结（卡顿），需剪映在首页且已安装 ffmpeg：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\test-dissolve-transition.ps1 -Export
```

叠化 5 秒：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\test-dissolve-transition.ps1 -Export -TransitionDurationSec 5
```

---

## 8. 导出失败时

- 剪映是否 6.x、是否能在首页手动导出  
- `DRAFT_SAVE_PATH` 是否与剪映草稿目录一致  
- 日志：`logs\capcut-mate.log`
