/**
 * 检测并启动本机剪映专业版。
 */

const path = require("path");
const fs = require("fs").promises;
const { execFile } = require("child_process");
const logger = require("./logger");

async function pathExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function jianyingExeCandidates() {
  const home = process.env.USERPROFILE || process.env.HOME || "";
  const localAppData = process.env.LOCALAPPDATA || path.join(home, "AppData", "Local");

  if (process.platform === "win32") {
    return [
      path.join(localAppData, "JianyingPro", "Apps", "JianyingPro.exe"),
      path.join(localAppData, "CapCut", "Apps", "JianyingPro.exe"),
      "C:\\Program Files\\JianyingPro\\JianyingPro.exe",
      "C:\\Program Files (x86)\\JianyingPro\\JianyingPro.exe",
    ];
  }
  if (process.platform === "darwin") {
    return [
      "/Applications/VideoFusion-macOS.app/Contents/MacOS/VideoFusion-macOS",
      "/Applications/JianyingPro.app/Contents/MacOS/JianyingPro",
      path.join(home, "Applications", "JianyingPro.app", "Contents", "MacOS", "JianyingPro"),
    ];
  }
  return [];
}

async function resolveJianyingExecutable() {
  const custom = process.env.JIANYING_EXE_PATH || process.env.CAPCUT_JIANYING_EXE;
  if (custom && (await pathExists(custom))) {
    return custom;
  }
  for (const candidate of jianyingExeCandidates()) {
    if (await pathExists(candidate)) {
      return candidate;
    }
  }
  return null;
}

function launchExecutable(exePath) {
  return new Promise((resolve, reject) => {
    execFile(exePath, [], { windowsHide: true }, (err) => {
      if (err && err.code !== 0) {
        reject(err);
      } else {
        resolve();
      }
    });
  });
}

/**
 * 启动剪映（若未安装则返回 false，不抛错）。
 * @returns {Promise<boolean>}
 */
async function launchJianying() {
  const exe = await resolveJianyingExecutable();
  if (!exe) {
    logger.warn("[jianying] executable not found");
    return false;
  }
  try {
    await launchExecutable(exe);
    logger.info("[jianying] launched: %s", exe);
    return true;
  } catch (e) {
    logger.warn("[jianying] launch failed: %s", e.message);
    return false;
  }
}

module.exports = {
  launchJianying,
  resolveJianyingExecutable,
};
