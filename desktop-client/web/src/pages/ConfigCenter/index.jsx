import { useEffect, useState, useCallback } from "react";
import electronService from "../../services/electronService";

import "./index.less";
import { toast } from "react-toastify";

const defaultConfig = {
  targetDirectory: "",
  autoUploadEnabled: false,
  autoUploadIdleSeconds: 45,
  serverApiBase: "",
};

const ConfigCenter = () => {
  const [config, setConfig] = useState(defaultConfig);

  const loadConfig = async () => {
    try {
      const configData = await electronService.getConfigData();
      setConfig({ ...defaultConfig, ...(configData || {}) });
    } catch (error) {
      console.error("加载配置失败:", error);
    }
  };

  const persistConfig = useCallback(async (partial) => {
    try {
      const next = await electronService.saveAppConfig(partial);
      setConfig({ ...defaultConfig, ...next });
    } catch (error) {
      toast.error("保存配置失败");
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, []);

  const handleSelectPath = async () => {
    try {
      const { success, targetDir } = await electronService.updateDraftPath();
      if (success) {
        await persistConfig({ targetDirectory: targetDir });
      }
    } catch (error) {
      toast.error("选择路径失败:", error);
    }
  };

  return (
    <div className="set-page">
      <div className="container">
        <div className="card">
          <div className="card-body">
            <div className="section-title">剪映路径设置</div>
            <div className="setting-path-input-group flex item-center">
              <label className="setting-path-label">当前路径：</label>
              <input
                type="text"
                className="setting-draft-path-input"
                placeholder="请选择草稿保存路径"
                value={config.targetDirectory || ""}
                readOnly
                onClick={handleSelectPath}
              />
              <button className="btn btn-small" onClick={handleSelectPath}>
                选择...
              </button>
            </div>
            <p className="settings-hint">
              设置剪映软件的草稿路径以导入草稿至剪映
            </p>
          </div>
        </div>

        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-body">
            <div className="section-title">自动回传（无需点击上传）</div>
            <label className="flex item-center" style={{ gap: 8, marginBottom: 12 }}>
              <input
                type="checkbox"
                checked={config.autoUploadEnabled === true}
                onChange={(e) =>
                  persistConfig({ autoUploadEnabled: e.target.checked })
                }
              />
              下载完成后监听草稿目录，停止保存一段时间后自动上传到服务器
            </label>
            <div
              className="setting-path-input-group flex item-center"
              style={{ marginBottom: 8 }}
            >
              <label className="setting-path-label">空闲秒数：</label>
              <input
                type="number"
                min={15}
                max={600}
                className="setting-draft-path-input"
                style={{ maxWidth: 120 }}
                value={config.autoUploadIdleSeconds ?? 45}
                onBlur={(e) =>
                  persistConfig({
                    autoUploadIdleSeconds: Number(e.target.value) || 45,
                  })
                }
                onChange={(e) =>
                  setConfig({
                    ...config,
                    autoUploadIdleSeconds: Number(e.target.value) || 45,
                  })
                }
              />
            </div>
            <div
              className="setting-path-input-group flex item-center"
              style={{ marginBottom: 8 }}
            >
              <label className="setting-path-label">API 地址：</label>
              <input
                type="text"
                className="setting-draft-path-input"
                placeholder="留空则从草稿链接自动解析"
                value={config.serverApiBase || ""}
                onBlur={(e) =>
                  persistConfig({ serverApiBase: e.target.value.trim() })
                }
                onChange={(e) =>
                  setConfig({ ...config, serverApiBase: e.target.value })
                }
              />
            </div>
            <p className="settings-hint">
              用户在本机剪映编辑并保存后，小助手可自动回传草稿；导出由服务端在收到 upload_draft 后自动提交。
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfigCenter;
