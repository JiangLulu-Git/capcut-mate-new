"""本地测试剪映导出码率 UI 自动化。

前置：Windows + 剪映专业版已打开并在首页；已安装 capcut-mate[windows] 依赖。

用法（项目根目录）:

  # 1) 只打开导出面板并设置码率，不点「导出」（便于肉眼确认 UI）
  set EXPORT_BITRATE_KBPS=1000
  set EXPORT_BITRATE_TYPE=VBR
  python tests/manual_test_export_bitrate.py --dry-run 你的草稿名称

  # 2) 完整导出（会真的导出并移动文件）
  python tests/manual_test_export_bitrate.py 你的草稿名称

  # 3) 导出后用 ffprobe 看码率（需 ffprobe 在 PATH）
  python tests/manual_test_export_bitrate.py 你的草稿名称 --verify

  # 4) 码率控件找不到时，打印导出面板控件树
  python tests/manual_test_export_bitrate.py --inspect

草稿名称 = 剪映首页卡片上的名字，通常与 draft_id 一致。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("ENABLE_APIKEY", "false")

import config  # noqa: E402


def _resolve_bitrate_kbps() -> int:
    raw = os.getenv("EXPORT_BITRATE_KBPS", str(getattr(config, "EXPORT_BITRATE_KBPS", 0)))
    return int(raw) if str(raw).isdigit() else 0


def _resolve_bitrate_type() -> str:
    return (
        os.getenv("EXPORT_BITRATE_TYPE", getattr(config, "EXPORT_BITRATE_TYPE", "VBR"))
        or "VBR"
    ).strip().upper()


def _resolve_mode_label() -> str:
    return (
        os.getenv(
            "EXPORT_BITRATE_MODE_UI_LABEL",
            getattr(config, "EXPORT_BITRATE_MODE_UI_LABEL", "自定义"),
        )
        or "自定义"
    ).strip()


def _dump_export_controls() -> int:
    if sys.platform != "win32":
        print("仅支持 Windows", file=sys.stderr)
        return 1
    try:
        import uiautomation as uia
    except ImportError:
        print("缺少 uiautomation，请 pip install capcut-mate[windows]", file=sys.stderr)
        return 1

    from src.pyJianYingDraft.jianying_controller import ControlFinder, JianyingController

    ctrl = JianyingController()
    print("请手动打开任意草稿并点击「导出」，进入导出设置页后按 Enter…")
    input()
    ctrl.get_window()
    if ctrl.app_status != "pre_export":
        print(f"当前不在导出页，app_status={ctrl.app_status}", file=sys.stderr)
        return 1

    setting_group = ctrl.app.GroupControl(
        searchDepth=1,
        Compare=ControlFinder.class_name_matcher("PanelSettingsGroup_QMLTYPE"),
    )
    if not setting_group.Exists(0):
        print("未找到 PanelSettingsGroup_QMLTYPE", file=sys.stderr)
        return 1

    def walk(node, depth: int = 0, limit: int = 80) -> None:
        if depth > limit:
            return
        indent = "  " * depth
        try:
            name = node.Name or ""
            cls = node.ClassName or ""
            desc = node.GetPropertyValue(30159) or ""
            print(f"{indent}{cls} name={name!r} desc={desc!r}")
        except Exception as exc:
            print(f"{indent}<error: {exc}>")
            return
        for child in node.GetChildren():
            walk(child, depth + 1, limit)

    print("\n=== 导出设置面板控件树（找码率相关 desc）===\n")
    walk(setting_group, 0, 6)
    return 0


def _probe_video_bitrate_kbps(mp4_path: Path) -> float | None:
    ffprobe = os.getenv("FFPROBE_PATH", "ffprobe")
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=bit_rate",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(mp4_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        bps = float(proc.stdout.strip())
        return bps / 1000.0
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
        print(f"ffprobe 失败: {exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="本地测试剪映导出码率设置")
    parser.add_argument("draft_name", nargs="?", help="剪映首页显示的草稿名称")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只设置码率，不点击最终导出",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="打印导出面板控件树（需手动先打开导出页）",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="导出完成后用 ffprobe 检查视频码率",
    )
    args = parser.parse_args()

    if args.inspect:
        return _dump_export_controls()

    if not args.draft_name:
        parser.error("请提供草稿名称，或使用 --inspect")

    if sys.platform != "win32":
        print("仅支持 Windows", file=sys.stderr)
        return 1

    kbps = _resolve_bitrate_kbps()
    if kbps <= 0:
        print(
            "请先设置 EXPORT_BITRATE_KBPS，例如: set EXPORT_BITRATE_KBPS=1000",
            file=sys.stderr,
        )
        return 1

    bitrate_type = _resolve_bitrate_type()
    mode_label = _resolve_mode_label()
    print(f"码率配置: {kbps} Kbps, type={bitrate_type}, mode={mode_label!r}")
    print(f"DRAFT_SAVE_PATH={config.DRAFT_SAVE_PATH}")

    try:
        from src.pyJianYingDraft.jianying_controller import JianyingController
    except ImportError as exc:
        print(f"无法加载 JianyingController: {exc}", file=sys.stderr)
        return 1

    ctrl = JianyingController()
    ctrl.get_window()
    if ctrl.app_status == "edit":
        print("当前已在编辑页，跳过回首页/重新打开草稿")
    else:
        ctrl.switch_to_home()
        ctrl.find_and_click_draft(args.draft_name)
    ctrl.click_export_button()
    ctrl.get_window()

    if ctrl.app_status != "pre_export" or ctrl.app_sub_status != "export_start":
        print(
            f"未能进入导出设置页: status={ctrl.app_status} sub={ctrl.app_sub_status}",
            file=sys.stderr,
        )
        return 1

    ctrl.set_export_bitrate(
        kbps,
        mode_label=mode_label,
        bitrate_type=bitrate_type,
    )

    if args.dry_run:
        print("\n[dry-run] 码率已尝试写入剪映面板，请目视确认后关闭导出窗口。")
        print("若数值/ VBR 未生效，请运行: python tests/manual_test_export_bitrate.py --inspect")
        return 0

    out_dir = PROJECT_ROOT / "output" / "draft"
    out_dir.mkdir(parents=True, exist_ok=True)
    outfile = out_dir / f"bitrate_test_{int(time.time())}.mp4"

    print(f"\n开始导出 -> {outfile}")
    ctrl.set_export_resolution(None)
    ctrl.set_export_framerate(None)
    ctrl.click_final_export_button()
    ctrl.get_window()
    ctrl.wait_for_export_completion(timeout=1200)
    original_path = ctrl.get_original_export_path()
    ctrl.move_exported_file(original_path, str(outfile))
    ctrl.return_to_home()

    print(f"导出完成: {outfile} ({outfile.stat().st_size // 1024} KB)")

    if args.verify:
        actual = _probe_video_bitrate_kbps(outfile)
        if actual is not None:
            print(f"ffprobe 平均视频码率: {actual:.0f} Kbps（目标 {kbps} Kbps，VBR 会有波动）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
