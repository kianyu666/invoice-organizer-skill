# invoice-organizer-skill

可安装、可复用的 Agent Skill 包，用于「发票批量整理」任务：扫描识别、备份、按规则重命名、生成统计表、报销核对。

## 项目简介
- `SKILL.md`：技能主文件，含 YAML frontmatter 与完整工作流指令，供 Agent 按步骤执行。
- `scripts/`：三个可选自动化脚本，加速整理流程（见「使用示例」）。
- 覆盖普通发票与替票：替票作为独立类型参与统计，不并入普通发票。
- 支持增量追加：后续新增发票按同一规则整理并追加进统计表。

## 目录结构
```
invoice-organizer-skill/
├── SKILL.md                 # 技能主文件（YAML frontmatter + Markdown 指令）
├── README.md                # 安装与使用说明
├── scripts/
│   ├── scan_invoices.py     # 扫描目录，列出发票文件并尝试提取基础信息
│   ├── rename_invoices.py   # 执行备份 + 批量重命名（读入字段 JSON）
│   └── build_stats.py       # 生成 Excel 统计表（openpyxl，SUMIF 动态合计）
└── .gitignore               # 忽略 __pycache__、*.xlsx 输出等
```

## 安装方式
1. 将 `invoice-organizer-skill` 整个文件夹放入 Agent 的 skills 目录。
2. 在 Agent 的配置中指定（或确认）`skills` 目录路径指向该 skills 目录。
3. 重启 Agent 或刷新技能列表，使 `invoice-organizer` 技能生效。

## 依赖安装
- Python 3.9+；
- 扫描与重命名脚本仅使用标准库，无需额外依赖；
- 统计脚本需要 `openpyxl`：

```bash
pip install openpyxl
```

## 使用示例
将发票文件放入一个目录（如 `D:\发票\2025-07`），依次执行：

```bash
# 1. 扫描识别：列出疑似发票文件清单
python scripts/scan_invoices.py "D:\发票\2025-07"

# 2. 重命名：读入字段 JSON（由 Agent 识别后生成），自动备份 + 重命名
python scripts/rename_invoices.py "D:\发票\2025-07" fields.json

# 3. 统计：生成 Excel 统计表（类型统计 + 发票明细，SUMIF 动态合计）
python scripts/build_stats.py "D:\发票\2025-07" detail.json "D:\发票\2025-07\发票统计.xlsx"
```

字段 JSON 结构：
```json
[
  {"filename": "20250719-车票.pdf", "type": "火车票", "date": "2025-07-19 14:30:52", "amount": 258, "person": "刘宇", "is_ticket": false}
]
```

重命名规则：
- 普通发票 → `【发票】类别-日期-金额-人员`
- 替票（`is_ticket: true` 或文件名含「替票」）→ `【替票】类别-日期-金额-人员`
- 重名冲突自动追加 `_2` 后缀；日期含时间时使用冒号格式（如 `14:30:52`）

统计表说明：
- 「类型统计」Sheet：按类别统计数量与金额合计，替票为独立类型；金额合计使用 SUMIF 公式动态引用「发票明细」Sheet。
- 「发票明细」Sheet：逐张列出类型、文件名、日期、金额、人员。

## 说明与限制
- 脚本以健壮性优先：文件不存在、字段缺失、金额非法时打印明确错误并跳过，不中断整体。
- 扫描脚本不强行解析 PDF / 图片内容，发票识别工作由 Agent 结合文件名与内容完成。
- 合并 PDF（含多张发票）、无法归类的文件保留原目录不动，需人工处理。
