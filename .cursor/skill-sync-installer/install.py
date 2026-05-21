#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
技能同步安装器：
从当前服务 /api/skills 拉取技能列表，下载 zip 并解压到 .cursor/skills 或 .trae/skills。
"""

import argparse
import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from urllib.parse import urljoin


DEFAULT_API = "http://localhost:8051/api/skills"


def find_project_root(start_path: str) -> str:
    """向上查找包含 .cursor 或 .trae 的目录，未找到则使用传入目录。"""
    cur = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(cur, ".cursor")) or os.path.isdir(os.path.join(cur, ".trae")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(start_path)
        cur = parent


def detect_ide_dir(project_root: str) -> str:
    """检测 IDE 目录并返回 skills 目标目录。"""
    cursor_dir = os.path.join(project_root, ".cursor")
    trae_dir = os.path.join(project_root, ".trae")
    if os.path.isdir(cursor_dir):
        return os.path.join(cursor_dir, "skills")
    if os.path.isdir(trae_dir):
        return os.path.join(trae_dir, "skills")
    raise RuntimeError("未检测到 .cursor 或 .trae，请确认项目根目录。")


def fetch_skill_list(api_url: str, headers=None):
    req = urllib.request.Request(api_url, headers=headers or {})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if isinstance(data, dict):
        if "data" in data:
            return data["data"]
        if "skills" in data:
            return data["skills"]
    return data or []


def load_requirements(req_path: str):
    if not os.path.exists(req_path):
        return {}
    with open(req_path, "r", encoding="utf-8") as f:
        return json.load(f)


def select_skills(all_skills, reqs, ids, install_all):
    if install_all:
        return all_skills
    if ids:
        id_set = set(ids)
        return [s for s in all_skills if s.get("id") in id_set]
    req_ids = reqs.get("ids") or []
    if req_ids:
        id_set = set(req_ids)
        return [s for s in all_skills if s.get("id") in id_set]
    req_tags = reqs.get("tags") or []
    if req_tags:
        tag_set = set(req_tags)
        return [s for s in all_skills if tag_set.intersection(set(s.get("tags") or []))]
    return all_skills


def safe_extract(zip_path: str, target_dir: str):
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            if ".." in member or member.startswith("/"):
                raise RuntimeError("压缩包路径不安全")
        zf.extractall(target_dir)


def get_download_url(api_url: str, skill: dict):
    base = api_url.rsplit("/api/skills", 1)[0]
    file_path = skill.get("filePath") or f"assets/{skill.get('fileName')}"
    return urljoin(base + "/", file_path)


def download_file(url: str, dest_path: str, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f:
        f.write(resp.read())


def install_skill(skill, target_dir, api_url, headers=None, force=False):
    skill_id = skill.get("id")
    if not skill_id:
        return f"跳过无 id 的技能: {skill}"
    dest = os.path.join(target_dir, skill_id)
    if os.path.exists(dest):
        if not force:
            return f"已存在，跳过: {skill_id}"
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)

    url = get_download_url(api_url, skill)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, f"{skill_id}.zip")
        download_file(url, zip_path, headers=headers)
        extract_dir = os.path.join(tmp, "extract")
        os.makedirs(extract_dir, exist_ok=True)
        safe_extract(zip_path, extract_dir)
        # 若只有一个顶级目录，直接内容迁移
        entries = [e for e in os.listdir(extract_dir) if not e.startswith("__MACOSX")]
        if len(entries) == 1 and os.path.isdir(os.path.join(extract_dir, entries[0])):
            src = os.path.join(extract_dir, entries[0])
        else:
            src = extract_dir
        for name in os.listdir(src):
            shutil.move(os.path.join(src, name), os.path.join(dest, name))
    return f"已安装: {skill_id}"


def load_user_id(skill_md_path: str):
    if not os.path.exists(skill_md_path):
        return None
    with open(skill_md_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("UserId:"):
                return line.split("UserId:", 1)[1].strip() or None
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API, help="技能列表 API 地址")
    parser.add_argument("--project", default=os.getcwd(), help="项目根目录")
    parser.add_argument("--ids", default="", help="逗号分隔的技能ID")
    parser.add_argument("--all", action="store_true", help="安装全部技能")
    parser.add_argument("--force", action="store_true", help="覆盖已存在技能")
    args = parser.parse_args()

    project_root = find_project_root(args.project)
    skills_dir = detect_ide_dir(project_root)
    os.makedirs(skills_dir, exist_ok=True)

    reqs = load_requirements(os.path.join(os.path.dirname(__file__), "requirements.json"))
    ids = [i.strip() for i in args.ids.split(",") if i.strip()]

    user_id = load_user_id(os.path.join(os.path.dirname(__file__), "SKILL.md"))
    headers = {"X-User-Id": user_id} if user_id else {}

    all_skills = fetch_skill_list(args.api, headers=headers)
    selected = select_skills(all_skills, reqs, ids, args.all)
    if not selected:
        print("未匹配到任何技能")
        return

    for s in selected:
        try:
            print(install_skill(s, skills_dir, args.api, headers=headers, force=args.force))
        except Exception as e:
            print(f"安装失败 {s.get('id')}: {e}")


if __name__ == "__main__":
    main()

