# Skill 同步安装器

功能：从公司技能平台 API 获取技能列表，下载 zip 并解压到 `.cursor/skills/` 或 `.trae/skills/`。

## 公司技能平台地址

| 用途 | 地址 |
|------|------|
| **GitLab 项目（源码 / 安装本同步器）** | http://172.16.98.121:8800/aiproj/company_skill_manager |
| **技能 API（`install.py --api`）** | http://172.16.99.202:8051/api/skills |

> `8800` 是 GitLab，不能直接当 `--api` 使用；拉取技能 zip 须用已部署的 **8051** 服务根地址 + `/api/skills`。

### 安装同步器（首次）

```powershell
npx --registry http://172.16.94.38:18002/ install-skill-sync -p D:\Skills_project\capcut-mate\.cursor
```

默认从 GitLab 项目 `aiproj/company_skill_manager` 拉取 `skill-sync-installer` 目录。

## API 响应规范

全站 JSON 接口统一 `{code:1, message, data}`，详见项目 `docs/api_response.zh.md`。

## 拉取技能（在项目根目录）

```powershell
cd D:\Skills_project\capcut-mate

# 安装全部技能
python .cursor\skill-sync-installer\install.py --api http://172.16.99.202:8051/api/skills --all

# 只安装 API 接口规范
python .cursor\skill-sync-installer\install.py --api http://172.16.99.202:8051/api/skills --ids api-standardizer --force
```

可选参数：

- `--api` 技能列表 API（默认 `http://localhost:8051/api/skills`）
- `--project` 项目根目录（默认当前目录）
- `--all` 安装全部技能
- `--ids` 逗号分隔的技能 ID，如 `api-standardizer,skill-sync-installer`
- `--force` 覆盖已存在技能
