/**

 * 剪映协作编辑 — 任务列表 + 小助手协议 + 导出预览

 */



const DEMO_VIDEOS =

  "https://teststatic.xuesee.net/sfs/coursedesignpc/qq.mp4";



const STORAGE_KEY = "capcut_mate_local_edit_records";
const SETUP_HIDDEN_KEY = "capcut_mate_setup_hidden";



const $ = (id) => document.getElementById(id);



function log(msg) {

  const el = $("log");

  const line = `[${new Date().toLocaleTimeString()}] ${msg}\n`;

  el.textContent = line + el.textContent;

}



function apiV1() {

  return `${$("apiBase").value.replace(/\/$/, "")}/openapi/capcut-mate/v1`;

}



function unwrap(json) {

  if (json.code !== undefined && json.code !== 1) {

    throw new Error(json.message || `错误码 ${json.code}`);

  }

  if (json.data !== undefined && json.data !== null) {

    return json.data;

  }

  return json;

}



async function apiPost(path, body) {

  const res = await fetch(`${apiV1()}${path}`, {

    method: "POST",

    headers: { "Content-Type": "application/json", Accept: "application/json" },

    body: JSON.stringify(body),

  });

  const json = await res.json();

  return unwrap(json);

}



async function apiGet(path) {

  const res = await fetch(`${apiV1()}${path}`, {

    headers: { Accept: "application/json" },

  });

  const json = await res.json();

  return unwrap(json);

}



function loadRecords() {

  try {

    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");

  } catch {

    return [];

  }

}



function saveRecords(records) {

  localStorage.setItem(STORAGE_KEY, JSON.stringify(records));

}



function updateRecord(draftId, patch) {

  const records = loadRecords();

  const idx = records.findIndex((r) => r.draftId === draftId);

  if (idx >= 0) {

    records[idx] = { ...records[idx], ...patch, updatedAt: Date.now() };

    saveRecords(records);

  }

}



function parseVideoUrls(text) {

  return text

    .split("\n")

    .map((l) => l.trim())

    .filter(Boolean);

}



function statusLabel(record) {

  const map = {

    draft: "草稿已生成",

    editing: "编辑中",

    uploading: "回传中",

    exporting: "导出中",

    completed: "已完成",

    failed: "失败",

  };

  return map[record.status] || record.status || "未知";

}



function resolvePlayableUrl(videoUrl) {

  if (!videoUrl) return "";

  if (/^https?:\/\//i.test(videoUrl)) return videoUrl;

  const apiBase = $("apiBase").value.replace(/\/$/, "");

  const normalized = videoUrl.replace(/\\/g, "/");

  const outputIdx = normalized.toLowerCase().indexOf("/output/");

  if (outputIdx >= 0) {

    return `${apiBase}${normalized.slice(outputIdx)}`;

  }

  if (normalized.startsWith("output/")) {

    return `${apiBase}/${normalized}`;

  }

  return videoUrl;

}



function getMateInstallUrl() {
  const v = $("mateInstallUrl").value.trim();
  return v && v !== "#" ? v : "";
}

function showMateInstallReminder(extra = "") {
  const installUrl = getMateInstallUrl();
  let msg =
    "未检测到剪映小助手。\n\n" +
    "本机首次使用请先：\n" +
    "1. 安装「剪映小助手」并允许 capcut-mate:// 协议\n" +
    "2. 安装本机剪映，并在小助手配置中心填写 API 与草稿目录\n" +
    "3. 再点击「编辑」/「完成」\n";
  if (installUrl) {
    msg += `\n安装包：${installUrl}`;
  } else {
    msg += "\n（管理员未配置安装包链接，请联系获取 capcut-mate-windows-x64-installer.exe）";
  }
  if (extra) msg += `\n\n${extra}`;
  alert(msg);
  if (installUrl) window.open(installUrl, "_blank");
  const card = $("setupCard");
  if (card) {
    card.hidden = false;
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function openMateUrl(url, fallbackDraftUrl, actionLabel) {
  let hidden = false;
  const onBlur = () => {
    hidden = true;
  };
  window.addEventListener("blur", onBlur);
  log(`唤起小助手（${actionLabel}）…`);
  window.location.href = url;
  setTimeout(() => {
    window.removeEventListener("blur", onBlur);
    if (!hidden) {
      log("未检测到小助手响应，请安装剪映小助手");
      if (fallbackDraftUrl && confirm("是否复制 draft_url 到剪贴板（手动处理）？")) {
        navigator.clipboard.writeText(fallbackDraftUrl);
      }
      showMateInstallReminder();
    }
  }, 2500);
}

async function loadClientSetup() {
  try {
    const data = await apiGet("/client_setup");
    const stepsEl = $("setupSteps");
    if (stepsEl && data.setup_steps?.length) {
      stepsEl.innerHTML = data.setup_steps
        .map((s) => `<li>${escapeHtml(s)}</li>`)
        .join("");
    }
    if (data.mate_install_url) {
      $("mateInstallUrl").value = data.mate_install_url;
      const dl = $("btnMateDownload");
      if (dl) {
        dl.href = data.mate_install_url;
        dl.hidden = false;
      }
    }
  } catch (e) {
    log(`加载本机配置说明失败: ${e.message}`);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function testMateInstalled() {
  let hidden = false;
  const onBlur = () => {
    hidden = true;
  };
  window.addEventListener("blur", onBlur);
  log("检测剪映小助手…");
  window.location.href = "capcut-mate://download?draft_url=test";
  setTimeout(() => {
    window.removeEventListener("blur", onBlur);
    if (hidden) {
      log("已检测到小助手（窗口已切换）");
      alert("已检测到剪映小助手，可正常使用「编辑」「完成」。");
    } else {
      log("未检测到小助手");
      showMateInstallReminder("检测用协议已触发，若未弹出小助手说明尚未安装或未注册协议。");
    }
  }, 2000);
}



async function pollUploadDone(draftId, baselineTs, maxSec = 120) {

  const start = Date.now();

  while (Date.now() - start < maxSec * 1000) {

    const prep = await apiGet(

      `/prepare_local_edit?draft_id=${encodeURIComponent(draftId)}`

    );

    if ((prep.content_updated_at || 0) > baselineTs + 0.5) {

      return prep;

    }

    await new Promise((r) => setTimeout(r, 2000));

  }

  throw new Error("等待草稿回传超时，请确认小助手已安装并在本机完成上传");

}



async function pollExport(draftUrl, onProgress) {

  const maxSec = 1200;

  const start = Date.now();

  while (Date.now() - start < maxSec * 1000) {

    const st = await apiPost("/gen_video_status", { draft_url: draftUrl });

    if (onProgress) onProgress(st);

    if (st.status === "completed") return st;

    if (st.status === "failed") {

      throw new Error(st.error_message || "导出失败");

    }

    await new Promise((r) => setTimeout(r, 5000));

  }

  throw new Error("导出超时");

}



function renderRecords() {

  const records = loadRecords();

  const list = $("recordList");

  list.innerHTML = "";

  $("emptyHint").hidden = records.length > 0;



  records.forEach((rec) => {

    const li = document.createElement("li");

    li.className = "record-item";

    const title = rec.title || rec.draftId.slice(0, 8);

    li.innerHTML = `

      <div class="record-main">

        <strong>${title}</strong>

        <span class="record-status status-${rec.status}">${statusLabel(rec)}</span>

        <span class="record-time">${new Date(rec.createdAt).toLocaleString()}</span>

      </div>

      <div class="record-actions">

        <button type="button" class="btn small btn-edit" data-id="${rec.draftId}">编辑</button>

        <button type="button" class="btn small btn-finish" data-id="${rec.draftId}">完成</button>

        <button type="button" class="btn small btn-preview" data-id="${rec.draftId}">预览</button>

      </div>

    `;

    list.appendChild(li);

  });



  list.querySelectorAll(".btn-edit").forEach((btn) => {

    btn.addEventListener("click", () => onEdit(btn.dataset.id));

  });

  list.querySelectorAll(".btn-finish").forEach((btn) => {

    btn.addEventListener("click", () => onFinish(btn.dataset.id));

  });

  list.querySelectorAll(".btn-preview").forEach((btn) => {

    btn.addEventListener("click", () => onPreview(btn.dataset.id));

  });

}



async function onEdit(draftId) {

  const records = loadRecords();

  const rec = records.find((r) => r.draftId === draftId);

  if (!rec?.mateOpenUrl) {

    alert("缺少 mate_open_url");

    return;

  }

  updateRecord(draftId, { status: "editing" });

  renderRecords();

  openMateUrl(rec.mateOpenUrl, rec.draftUrl, "下载并打开剪映");

}



async function onFinish(draftId) {

  const records = loadRecords();

  const rec = records.find((r) => r.draftId === draftId);

  if (!rec) return;



  updateRecord(draftId, { status: "uploading" });

  renderRecords();



  try {

    let baselineTs = rec.contentUpdatedAt || 0;

    if (!rec.mateUploadUrl) {

      const prep = await apiGet(

        `/prepare_local_edit?draft_id=${encodeURIComponent(draftId)}`

      );

      baselineTs = prep.content_updated_at || baselineTs;

      updateRecord(draftId, {

        mateUploadUrl: prep.mate_upload_url,

        contentUpdatedAt: baselineTs,

      });

      rec.mateUploadUrl = prep.mate_upload_url;

    }



    log(`任务 ${draftId.slice(0, 8)}：唤起小助手回传草稿…`);

    openMateUrl(rec.mateUploadUrl, rec.draftUrl, "回传草稿");



    log("等待服务器收到回传…");

    const prep = await pollUploadDone(draftId, baselineTs);

    const draftUrl = prep.draft_url || rec.draftUrl;



    updateRecord(draftId, {

      status: "exporting",

      draftUrl,

      contentUpdatedAt: prep.content_updated_at,

    });

    renderRecords();



    log("服务端已自动提交导出，等待进度…");



    const st = await pollExport(draftUrl, (progress) => {

      log(`导出进度: ${progress.status} ${progress.progress}%`);

    });



    const playable = resolvePlayableUrl(st.video_url);

    updateRecord(draftId, {

      status: "completed",

      videoUrl: st.video_url,

      playableUrl: playable,

    });

    renderRecords();

    onPreview(draftId);

    log("导出完成");

  } catch (e) {

    updateRecord(draftId, { status: "failed", errorMessage: e.message });

    renderRecords();

    log(`错误: ${e.message}`);

    alert(e.message);

  }

}



function onPreview(draftId) {

  const rec = loadRecords().find((r) => r.draftId === draftId);

  if (!rec?.videoUrl && !rec?.playableUrl) {

    alert("尚无成片，请先完成导出");

    return;

  }

  const src = rec.playableUrl || resolvePlayableUrl(rec.videoUrl);

  $("previewCard").hidden = false;

  $("previewMeta").textContent = `任务 ${rec.draftId}`;

  $("previewUrl").textContent = rec.videoUrl;

  const video = $("previewVideo");

  video.src = src;

  video.load();

  log(`预览: ${src}`);

}



$("videoUrls").value = DEMO_VIDEOS;



$("btnCreate").addEventListener("click", async () => {

  $("btnCreate").disabled = true;

  try {

    const urls = parseVideoUrls($("videoUrls").value);

    if (!urls.length) {

      alert("请至少填写一个视频 URL");

      return;

    }



    const transitionName = $("transition").value.trim();

    const videos = urls.map((video_url) => ({

      video_url,

      use_full_duration: true,

      ...(transitionName ? { transition: transitionName } : {}),

    }));



    log("正在创建草稿…");

    const data = await apiPost("/auto_render", {

      videos,

      wait_export: false,

      api_base_url: $("apiBase").value.replace(/\/$/, ""),

    });



    const prep = await apiGet(

      `/prepare_local_edit?draft_id=${encodeURIComponent(data.draft_id)}`

    );



    const record = {

      draftId: data.draft_id,

      draftUrl: prep.draft_url || data.draft_url,

      mateOpenUrl: prep.mate_open_url,

      mateUploadUrl: prep.mate_upload_url,

      contentUpdatedAt: prep.content_updated_at || 0,

      title: `任务 ${data.draft_id.slice(0, 8)}`,

      status: "draft",

      videoUrl: "",

      playableUrl: "",

      createdAt: Date.now(),

      updatedAt: Date.now(),

    };



    const records = loadRecords();

    records.unshift(record);

    saveRecords(records);

    renderRecords();

    log(`草稿已创建: ${record.draftId}`);

  } catch (e) {

    log(`错误: ${e.message}`);

    alert(e.message);

  } finally {

    $("btnCreate").disabled = false;

  }

});



$("btnClearLog").addEventListener("click", () => {

  $("log").textContent = "";

});



renderRecords();

if (localStorage.getItem(SETUP_HIDDEN_KEY) === "1") {
  const card = $("setupCard");
  if (card) card.hidden = true;
}

$("btnHideSetup")?.addEventListener("click", () => {
  const card = $("setupCard");
  if (card) card.hidden = true;
  localStorage.setItem(SETUP_HIDDEN_KEY, "1");
});

$("btnTestMate")?.addEventListener("click", testMateInstalled);

loadClientSetup();

log("演示页就绪。访问 /demo/ ，API 默认 http://127.0.0.1:30000");


