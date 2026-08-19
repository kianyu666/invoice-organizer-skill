#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
执行备份 + 批量重命名发票文件。

读取字段 JSON（结构：[{filename, type, date, amount, person, is_ticket}]），
对每张文件：
  1. 在文件所在目录下「备份」子文件夹生成 _备份_ 前缀副本；
  2. 按规则重命名：
       普通发票 -> 【发票】类别-日期-金额-人员
       替票     -> 【替票】类别-日期-金额-人员
  3. 重名冲突自动追加 _2 / _3 ... 后缀。
无法归类（字段缺失）或文件不存在的记录跳过并打印警告，不中断整体。

用法：
    python rename_invoices.py <目录路径> <字段.json>
"""
import argparse
import json
import os
import re
import shutil
import sys

BACKUP_DIR_NAME = "备份"      # 备份子文件夹名
BACKUP_PREFIX = "_备份_"      # 备份副本前缀
REQUIRED_FIELDS = ("filename", "type", "date", "amount", "person")


def normalize_time_separators(date_str):
    """将日期字符串末尾的时间分隔符统一为冒号格式（如 14.30.52 -> 14:30:52）。"""
    return re.sub(r"(\d{2})[._-](\d{2})[._-](\d{2})$", r"\1:\2:\3", date_str)


def sanitize_for_windows(name):
    """Windows 文件名不允许 <>:\"/\\|?* 等字符，替换为安全字符 '-'。

    规格要求日期含时间时使用冒号格式（如 14:30:52），该格式在 Linux/macOS
    下可直接使用；Windows 文件系统不允许冒号，此处自动降级替换并打印提示。
    """
    if os.name != "nt":
        return name
    cleaned = re.sub(r'[<>:"/\\|?*]', "-", name)
    # 清理控制字符
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32)
    return cleaned


def build_target_name(record, ext):
    """根据记录与扩展名构造目标文件名。"""
    prefix = "【替票】" if record.get("is_ticket") else "【发票】"
    # 替票也可能体现在 type 字段（如「替票-火车票」）
    if not record.get("is_ticket") and "替票" in str(record["type"]):
        prefix = "【替票】"
    date_str = normalize_time_separators(str(record["date"]))
    return f"{prefix}{record['type']}-{date_str}-{record['amount']}-{record['person']}{ext}"


def backup_file(src_path):
    """在文件所在目录下「备份」子文件夹生成 _备份_ 前缀副本。"""
    src_dir = os.path.dirname(src_path)
    backup_dir = os.path.join(src_dir, BACKUP_DIR_NAME)
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, BACKUP_PREFIX + os.path.basename(src_path))
    if os.path.exists(backup_path):
        print(f"  [提示] 备份副本已存在，跳过复制：{os.path.basename(backup_path)}")
        return backup_path
    shutil.copy2(src_path, backup_path)
    return backup_path


def unique_path(path):
    """若目标路径已存在，追加 _2 / _3 ... 后缀直至不冲突。"""
    if not os.path.exists(path):
        return path
    dir_name, base = os.path.split(path)
    stem, ext = os.path.splitext(base)
    idx = 2
    while True:
        candidate = os.path.join(dir_name, f"{stem}_{idx}{ext}")
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def rename_one(src_path, record):
    """对单个文件执行备份 + 重命名，返回 (状态, 说明)。"""
    src_dir = os.path.dirname(src_path)
    src_name = os.path.basename(src_path)

    # 检查必填字段，缺失则无法归类，跳过
    missing = [f for f in REQUIRED_FIELDS if not record.get(f)]
    if missing:
        return "skip", f"[警告] 字段缺失（{', '.join(missing)}），保留原文件：{src_name}"

    ext = os.path.splitext(src_name)[1] or ".pdf"
    target_name = build_target_name(record, ext)

    # Windows 下将冒号等非法字符替换为安全字符（自动降级）
    sanitized = sanitize_for_windows(target_name)
    if sanitized != target_name:
        print(f"  [提示] 目标名含 Windows 非法字符，已替换为安全字符：{target_name} -> {sanitized}")
        target_name = sanitized

    # 已是规范命名则跳过
    if src_name == target_name:
        return "skip", f"[提示] 已是规范命名，跳过：{src_name}"

    # 备份
    backup_path = backup_file(src_path)
    print(f"  [备份] {src_name} -> {os.path.relpath(backup_path, src_dir)}")

    # 重命名（自动处理重名冲突）
    target_path = unique_path(os.path.join(src_dir, target_name))
    os.rename(src_path, target_path)
    return "ok", f"[完成] {src_name} -> {os.path.basename(target_path)}"


def main():
    parser = argparse.ArgumentParser(description="执行备份 + 批量重命名发票文件")
    parser.add_argument("target_dir", help="目录路径")
    parser.add_argument("fields_json", help="字段 JSON 文件路径")
    args = parser.parse_args()

    target_dir = os.path.abspath(args.target_dir)
    if not os.path.isdir(target_dir):
        print(f"[错误] 目录不存在：{target_dir}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.fields_json):
        print(f"[错误] 字段 JSON 文件不存在：{args.fields_json}", file=sys.stderr)
        sys.exit(1)

    with open(args.fields_json, "r", encoding="utf-8") as fp:
        try:
            records = json.load(fp)
        except json.JSONDecodeError as e:
            print(f"[错误] 字段 JSON 解析失败：{e}", file=sys.stderr)
            sys.exit(1)
    if not isinstance(records, list):
        print("[错误] 字段 JSON 顶层必须是数组", file=sys.stderr)
        sys.exit(1)

    ok_count = skip_count = 0
    for record in records:
        src_name = record.get("filename")
        if not src_name:
            print("  [警告] 记录缺少 filename 字段，跳过")
            skip_count += 1
            continue
        src_path = os.path.join(target_dir, src_name)
        if not os.path.isfile(src_path):
            print(f"  [警告] 文件不存在，跳过：{src_name}")
            skip_count += 1
            continue
        status, msg = rename_one(src_path, record)
        print(f"  {msg}")
        if status == "ok":
            ok_count += 1
        else:
            skip_count += 1

    print(f"\n处理完成：成功 {ok_count}，跳过 {skip_count}")


if __name__ == "__main__":
    main()
