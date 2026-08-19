#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描目录，列出发票文件清单。

本脚本不强行解析文件内容（发票识别工作由 Agent 结合文件名与内容完成），
仅负责列出目录内疑似发票文件（PDF / 图片），并做轻量的文件名信息提取作为辅助参考。

用法：
    python scan_invoices.py <目录路径>
"""
import argparse
import os
import re
import sys

# 疑似发票文件的扩展名（PDF + 常见图片格式）
SUPPORTED_EXTS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff",
}

# 日期提取正则：支持 2025-07-19、2025/07/19、20250719、7.19 等常见形式
DATE_PATTERNS = [
    re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})(?!\d)"),
]

# 金额提取正则：支持 ¥258、258元、258.50 等
AMOUNT_PATTERNS = [
    re.compile(r"[¥￥]\s*(\d+(?:\.\d{1,2})?)"),
    re.compile(r"(\d+(?:\.\d{1,2})?)\s*元"),
]


def extract_basic_info(filename):
    """从文件名轻量提取日期 / 金额信息，提取不到返回 None。"""
    date, amount = None, None
    for pat in DATE_PATTERNS:
        m = pat.search(filename)
        if m:
            date = m.group(0)
            break
    for pat in AMOUNT_PATTERNS:
        m = pat.search(filename)
        if m:
            amount = m.group(1)
            break
    return date, amount


def scan_directory(target_dir):
    """扫描目录，返回疑似发票文件清单（含基础信息）。"""
    target_dir = os.path.abspath(target_dir)
    if not os.path.isdir(target_dir):
        print(f"[错误] 目录不存在或不可访问：{target_dir}", file=sys.stderr)
        sys.exit(1)

    files = []
    for entry in sorted(os.scandir(target_dir), key=lambda e: e.name):
        if not entry.is_file():
            continue  # 只处理顶层文件，不递归子目录
        ext = os.path.splitext(entry.name)[1].lower()
        if ext not in SUPPORTED_EXTS:
            continue
        date, amount = extract_basic_info(entry.name)
        files.append({
            "filename": entry.name,
            "path": entry.path,
            "date": date,
            "amount": amount,
        })
    return files


def main():
    parser = argparse.ArgumentParser(description="扫描目录，列出发票文件清单")
    parser.add_argument("target_dir", help="目标目录路径")
    args = parser.parse_args()

    files = scan_directory(args.target_dir)
    print(f"共发现 {len(files)} 个疑似发票文件：")
    for f in files:
        hint = []
        if f["date"]:
            hint.append(f"日期={f['date']}")
        if f["amount"]:
            hint.append(f"金额={f['amount']}")
        suffix = "（" + "，".join(hint) + "）" if hint else ""
        print(f"  {f['filename']}{suffix}")


if __name__ == "__main__":
    main()
