/**
 * 草稿目录自动监听：用户在本机剪映保存后，静默检测「编辑空闲」并回传服务器。
 * 无需用户点击上传按钮。
 */

const path = require("path");
const crypto = require("crypto");
const fs = require("fs").promises;
const fsSync = require("fs");
const os = require("os");
const { execFile } = require("child_process");
const logger = require("./logger");

/** @type {Map<string, object>} */
const activeSessions = new Map();

const DEFAULT_IDLE_SECONDS = 45;
const GRACE_AFTER_DOWNLOAD_MS = 15000;

function apiBaseFromDraftUrl(draftUrl) {
  try {
    const u = new URL(draftUrl);
    const marker = "/v1/";
    const idx = u.pathname.indexOf(marker);
    if (idx >= 0) {
      return `${u.origin}${u.pathname.slice(0, idx + marker.length - 1)}`;
    }
    return `${u.origin}/openapi/capcut-mate/v1`;
  } catch {
    return "";
  }
}

/** draft_content.json 的 SHA-256，用于判断是否真有编辑、避免重复上传 */
async function computeDraftContentHash(draftDir) {
  const filePath = path.join(draftDir, "draft_content.json");
  try {
    const buf = await fs.readFile(filePath);
    return crypto.createHash("sha256").update(buf).digest("hex");
  } catch (e) {
    logger.warn(`[auto-sync] cannot hash draft_content.json: ${e.message}`);
    return null;
  }
}

function zipDraftDirectory(draftDir, zipPath) {
  return new Promise((resolve, reject) => {
    const quote = (s) => s.replace(/'/g, "''");
    if (process.platform === "win32") {
      const cmd = [
        `$ErrorActionPreference='Stop'`,
        `if (Test-Path -LiteralPath '${quote(zipPath)}') { Remove-Item -LiteralPath '${quote(zipPath)}' -Force }`,
        `Compress-Archive -Path '${quote(draftDir)}\\*' -DestinationPath '${quote(zipPath)}' -CompressionLevel Fastest`,
      ].join("; ");
      execFile(
        "powershell.exe",
        ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
        { windowsHide: true, maxBuffer: 64 * 1024 * 1024 },
        (err, _stdout, stderr) => {
          if (err) {
            reject(new Error(stderr || err.message));
          } else {
            resolve();
          }
        }
      );
      return;
    }
    execFile(
      "tar",
      ["-czf", zipPath, "-C", draftDir, "."],
      { maxBuffer: 64 * 1024 * 1024 },
      (err, _stdout, stderr) => {
        if (err) reject(new Error(stderr || err.message));
        else resolve();
      }
    );
  });
}

async function uploadDraftZip({ apiBase, draftId, zipPath }) {
  const buffer = await fs.readFile(zipPath);
  const form = new FormData();
  form.append("draft_id", draftId);
  form.append("file", new Blob([buffer]), `${draftId}.zip`);

  const url = `${apiBase.replace(/\/$/, "")}/upload_draft`;
  const response = await fetch(url, { method: "POST", body: form });
  const text = await response.text();
  let data = {};
  try {
    data = JSON.parse(text);
  } catch {
    data = { raw: text };
  }
  if (!response.ok || (data?.code !== undefined && data.code !== 0)) {
    const msg = data?.message || data?.detail || text || response.statusText;
    throw new Error(`upload_draft HTTP ${response.status}: ${msg}`);
  }
  return data?.data ?? data;
}

function stopDraftAutoSync(draftId) {
  const session = activeSessions.get(draftId);
  if (!session) return;
  if (session.debounceTimer) clearTimeout(session.debounceTimer);
  if (session.pollTimer) clearInterval(session.pollTimer);
  if (session.watcher) {
    try {
      session.watcher.close();
    } catch {
      /* ignore */
    }
  }
  activeSessions.delete(draftId);
  logger.info(`[auto-sync] stopped watch: ${draftId}`);
}

function stopAllDraftAutoSync() {
  for (const draftId of [...activeSessions.keys()]) {
    stopDraftAutoSync(draftId);
  }
}

/**
 * @param {object} opts
 * @param {string} opts.draftId
 * @param {string} opts.draftDir
 * @param {string} opts.draftUrl get_draft 链接
 * @param {number} [opts.idleSeconds]
 * @param {string} [opts.serverApiBase]
 * @param {(entry: object) => void} [opts.onLog]
 */
function startDraftAutoSync(opts) {
  const {
    draftId,
    draftDir,
    draftUrl,
    idleSeconds = DEFAULT_IDLE_SECONDS,
    serverApiBase,
    onLog,
  } = opts;

  if (!draftId || !draftDir || !draftUrl) return;

  stopDraftAutoSync(draftId);

  const apiBase = serverApiBase || apiBaseFromDraftUrl(draftUrl);
  if (!apiBase) {
    logger.warn("[auto-sync] cannot resolve API base from draft URL");
    return;
  }

  const session = {
    draftId,
    draftDir,
    draftUrl,
    apiBase,
    onLog,
    idleMs: Math.max(15, idleSeconds) * 1000,
    graceUntil: Date.now() + GRACE_AFTER_DOWNLOAD_MS,
    baselineContentHash: null,
    lastUploadContentHash: null,
    uploading: false,
    debounceTimer: null,
    watcher: null,
  };

  activeSessions.set(draftId, session);

  const log = (level, message) => {
    logger.info(`[auto-sync] ${message}`);
    if (onLog) onLog({ level, message: `[自动同步] ${message}` });
  };

  const scheduleIdleCheck = () => {
    if (session.debounceTimer) clearTimeout(session.debounceTimer);
    session.debounceTimer = setTimeout(() => {
      void onIdle();
    }, session.idleMs);
  };

  const onActivity = () => {
    if (Date.now() < session.graceUntil) return;
    scheduleIdleCheck();
  };

  const onIdle = async () => {
    if (session.uploading) return;
    if (Date.now() < session.graceUntil) return;

    const contentHash = await computeDraftContentHash(session.draftDir);
    if (!contentHash) return;

    if (session.baselineContentHash === null) {
      session.baselineContentHash = contentHash;
      return;
    }

    if (contentHash === session.baselineContentHash) {
      return;
    }
    if (contentHash === session.lastUploadContentHash) {
      logger.info(
        `[auto-sync] draft ${draftId} content unchanged since last upload, skip`
      );
      return;
    }

    session.uploading = true;
    const zipPath = path.join(
      os.tmpdir(),
      `capcut-mate-upload-${draftId}-${Date.now()}.zip`
    );

    try {
      log("info", `检测到草稿 ${draftId} 已停止修改，正在打包上传…`);
      await zipDraftDirectory(session.draftDir, zipPath);
      const result = await uploadDraftZip({
        apiBase: session.apiBase,
        draftId,
        zipPath,
      });
      session.lastUploadContentHash = contentHash;
      const returnedUrl = result?.draft_url || draftUrl;
      log(
        "success",
        `草稿 ${draftId} 已回传服务器（导出由服务端 upload_draft 自动提交）`
      );
    } catch (e) {
      log("error", `自动上传失败: ${e.message}`);
    } finally {
      session.uploading = false;
      try {
        await fs.unlink(zipPath);
      } catch {
        /* ignore */
      }
      scheduleIdleCheck();
    }
  };

  void (async () => {
    session.baselineContentHash = await computeDraftContentHash(draftDir);

    try {
      session.watcher = fsSync.watch(
        draftDir,
        { recursive: true },
        (_eventType, filename) => {
          if (filename && String(filename).endsWith(".tmp")) return;
          onActivity();
        }
      );
      session.watcher.on("error", (err) => {
        logger.warn(`[auto-sync] watcher error ${draftId}: ${err.message}`);
      });
    } catch (e) {
      logger.warn(`[auto-sync] fs.watch failed, fallback to polling: ${e.message}`);
      session.pollTimer = setInterval(onActivity, 4000);
    }

    log(
      "info",
      `已监听草稿目录，${idleSeconds}s 无保存变更后将自动上传（无需手动操作）`
    );
    scheduleIdleCheck();
  })();
}

module.exports = {
  startDraftAutoSync,
  stopDraftAutoSync,
  stopAllDraftAutoSync,
  apiBaseFromDraftUrl,
  computeDraftContentHash,
  zipDraftDirectory,
  uploadDraftZip,
};
