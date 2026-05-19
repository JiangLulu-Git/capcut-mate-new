/**
 * capcut-mate:// 协议：下载草稿 / 回传草稿 / 打开剪映。
 *
 * download: capcut-mate://download?draft_url=...&open_jianying=1
 * upload:   capcut-mate://upload?draft_id=...&draft_url=...
 */

const path = require("path");
const { getDraftUrls, downloadFiles, ensureAutoDetectedDraftPathInConfig } = require("./download");
const { zipDraftDirectory, uploadDraftZip, apiBaseFromDraftUrl } = require("./draftAutoSync");
const { launchJianying } = require("./jianyingLauncher");
const logger = require("./logger");

const PROTOCOL = "capcut-mate";

function parseProtocolRequest(raw) {
  if (!raw || typeof raw !== "string") return null;
  const trimmed = raw.trim();
  if (!trimmed.startsWith(`${PROTOCOL}://`)) return null;
  try {
    const u = new URL(trimmed);
    const action = (u.hostname || u.pathname.replace(/^\//, "") || "download").toLowerCase();
    return {
      action,
      draftUrl:
        u.searchParams.get("draft_url") ||
        u.searchParams.get("url") ||
        null,
      draftId: u.searchParams.get("draft_id") || null,
      openJianying: u.searchParams.get("open_jianying") === "1",
    };
  } catch {
    return null;
  }
}

function parseDraftUrlFromArgv(argv) {
  if (!argv || !argv.length) return null;
  for (const arg of argv) {
    if (typeof arg !== "string") continue;
    if (arg.startsWith("--draft-url=")) {
      return decodeURIComponent(arg.slice("--draft-url=".length));
    }
    const req = parseProtocolRequest(arg);
    if (req?.draftUrl) return req.draftUrl;
  }
  return null;
}

function parseProtocolUrl(raw) {
  return parseProtocolRequest(raw)?.draftUrl || null;
}

function extractDraftId(draftUrl) {
  try {
    const u = new URL(draftUrl);
    return u.searchParams.get("draft_id");
  } catch {
    const query = draftUrl.includes("?") ? draftUrl.split("?")[1] : "";
    return new URLSearchParams(query).get("draft_id");
  }
}

async function downloadDraftFromUrl(draftUrl, parentWindow, options = {}) {
  const openJianying = options.openJianying === true;
  const targetId = extractDraftId(draftUrl);
  if (!targetId) {
    throw new Error("draft_url 中缺少 draft_id");
  }

  logger.info("[launcher] download draft: %s (open_jianying=%s)", targetId, openJianying);
  const jsonData = await getDraftUrls(draftUrl, parentWindow);
  if (jsonData?.code !== 0 || !jsonData?.files) {
    throw new Error("获取草稿文件列表失败");
  }

  const matchedFiles = jsonData.files.filter((fileUrl) => fileUrl.includes(targetId));
  if (!matchedFiles.length) {
    throw new Error("未找到包含 draft_id 的文件");
  }

  const result = await downloadFiles(
    {
      sourceUrl: draftUrl,
      remoteFileUrls: matchedFiles,
      targetId,
      openJianying,
    },
    parentWindow
  );

  if (openJianying) {
    await launchJianying();
  }

  return result;
}

async function uploadLocalDraft(draftId, draftUrl, parentWindow) {
  if (!draftId) {
    throw new Error("缺少 draft_id");
  }

  const config = await ensureAutoDetectedDraftPathInConfig();
  const baseDir = config?.targetDirectory || config?.draftPath;
  if (!baseDir) {
    throw new Error("未配置剪映草稿目录，请在小助手中设置（须与剪映「草稿位置」一致）");
  }

  const draftDir = path.join(baseDir, draftId);
  try {
    await require("fs").promises.access(path.join(draftDir, "draft_content.json"));
  } catch {
    throw new Error(`本机未找到草稿目录: ${draftDir}`);
  }

  const apiBase =
    config.serverApiBase || (draftUrl ? apiBaseFromDraftUrl(draftUrl) : "");
  if (!apiBase) {
    throw new Error("无法解析 API 地址，请在小助手中配置 serverApiBase");
  }

  const os = require("os");
  const zipPath = path.join(os.tmpdir(), `capcut-mate-upload-${draftId}-${Date.now()}.zip`);

  logger.info("[launcher] upload local draft: %s", draftId);
  try {
    await zipDraftDirectory(draftDir, zipPath);
    const result = await uploadDraftZip({
      apiBase,
      draftId,
      zipPath,
    });
    return {
      success: true,
      draft_url: result?.draft_url || draftUrl,
      message: "草稿已回传服务器",
    };
  } finally {
    try {
      await require("fs").promises.unlink(zipPath);
    } catch {
      /* ignore */
    }
  }
}

async function handleProtocolRequest(raw, parentWindow) {
  const req = parseProtocolRequest(raw);
  if (!req) return null;

  if (req.action === "upload") {
    const draftId = req.draftId || (req.draftUrl ? extractDraftId(req.draftUrl) : null);
    return uploadLocalDraft(draftId, req.draftUrl, parentWindow);
  }

  if (req.action === "download" || req.draftUrl) {
    if (!req.draftUrl) {
      throw new Error("download 协议缺少 draft_url");
    }
    return downloadDraftFromUrl(req.draftUrl, parentWindow, {
      openJianying: req.openJianying,
    });
  }

  throw new Error(`未知协议动作: ${req.action}`);
}

module.exports = {
  PROTOCOL,
  parseProtocolRequest,
  parseProtocolUrl,
  parseDraftUrlFromArgv,
  extractDraftId,
  downloadDraftFromUrl,
  uploadLocalDraft,
  handleProtocolRequest,
};
