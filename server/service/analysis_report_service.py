"""
经营分析报告服务 —— 从 AI 对话输出中提取结构化数据，保存到数据库

支持 Markdown 格式的经营分析报告解析：
- 核心财务概览（合同营收、采购支出）
- 现金流深度分析（月度预测、关键节点）
- 财务风险提示（应收账款、应付账款、成本结构）
- 经营优化建议（分类建议）
- 总结
"""
import logging
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from server.models.analysis_report import AnalysisReport
from server.service.project_profit_service import ProjectProfitService

logger = logging.getLogger(__name__)

# ─── 金额模式：¥123,456元、123,456元、12,345、+79,130 ───
_MONEY_RE = r"[¥￥]?\s*([+-]?[\d,]+\.?\d*)\s*(?:元|万)?"
_PCT_RE  = r"([\d,]+\.?\d*)\s*%"


def _parse_number(raw: str) -> Optional[float]:
    """将匹配到的数字字符串转为 float"""
    if not raw:
        return None
    raw = raw.replace(",", "").replace("+", "").strip()
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_money(text: str) -> Optional[float]:
    """从文本中提取第一个金额"""
    m = re.search(_MONEY_RE, text)
    return _parse_number(m.group(1)) if m else None



def _find_section(text: str, heading: str) -> str:
    """提取某个 ## 标题下的全部内容，直到下一个同级或上级标题"""
    # 用正则匹配 ## heading 到下一个 ## 或 # 或文本末尾
    pattern = rf"##\s+{re.escape(heading)}[\s\S]*?(?=\n##\s|\n#\s|\Z)"
    m = re.search(pattern, text)
    return m.group(0) if m else ""


def _find_subsection(text: str, heading: str) -> str:
    """提取 ### 子标题下的内容"""
    pattern = rf"###\s+{re.escape(heading)}[\s\S]*?(?=\n###\s|\n##\s|\n#\s|\Z)"
    m = re.search(pattern, text)
    return m.group(0) if m else ""


def _extract_list_items(text: str) -> list[str]:
    """提取 Markdown 列表项（以 - 或 * 或数字. 开头）"""
    items = []
    for line in text.split("\n"):
        stripped = line.strip()
        # 匹配无序列表或有序列表
        m = re.match(r"^[-*]\s+(.+?)$", stripped)
        if not m:
            m = re.match(r"^\d+[\.\)]\s+(.+?)$", stripped)
        if m:
            item = m.group(1).strip()
            # 去掉内联的 ** 加粗标记
            item = re.sub(r"\*\*(.+?)\*\*", r"\1", item)
            items.append(item)
    return items


def _extract_table_rows(text: str) -> list[dict]:
    """解析 Markdown 表格，返回 [{col1: val, col2: val}, ...]"""
    lines = text.strip().split("\n")
    # 找表头行和分隔行
    header_idx = -1
    sep_idx = -1
    for i, line in enumerate(lines):
        if "|" in line:
            if re.search(r"[-]{3,}", line):
                sep_idx = i
            elif header_idx == -1:
                header_idx = i

    if header_idx == -1 or sep_idx == -1 or sep_idx != header_idx + 1:
        return []

    headers = [h.strip() for h in lines[header_idx].split("|") if h.strip()]
    rows = []
    for line in lines[sep_idx + 1:]:
        if "|" not in line:
            break
        cells = [c.strip() for c in line.split("|") if c.strip() is not None]
        # 去掉空串
        cells = [c for c in line.split("|")]
        cells = [c.strip() for c in cells if c.strip()]
        if len(cells) >= len(headers):
            row = {}
            for j, h in enumerate(headers):
                if j < len(cells):
                    row[h] = re.sub(r"\*\*(.+?)\*\*", r"\1", cells[j])
            if row:
                rows.append(row)
    return rows


# ══════════════════════════════════════════════════════════════
#  主提取函数
# ══════════════════════════════════════════════════════════════

def extract_from_text(text: str) -> dict:
    """从 AI 输出的 Markdown 经营分析报告中提取完整结构化数据"""
    result: dict[str, Any] = {}

    # ── 1. 提取标题 ──
    result["report_title"] = _extract_title(text)

    # ── 2. 核心财务概览 ──
    overview = _find_section(text, "核心财务概览") or _find_section(text, "一、核心财务概览")
    result["financial_overview"] = _parse_overview(overview)

    # ── 3. 合同与营收 ──
    contract_section = _find_subsection(text, "合同与营收") or _find_subsection(text, "合同与营收情况")
    result["contract_revenue"] = _parse_contract_revenue(contract_section, text)

    # ── 4. 采购与支出 ──
    purchase_section = _find_subsection(text, "采购与支出") or _find_subsection(text, "采购与支出结构")
    result["purchase_expense"] = _parse_purchase(purchase_section, text)

    # ── 5. 现金流分析 ──
    cashflow = _find_section(text, "现金流深度分析") or _find_section(text, "二、现金流深度分析")
    result["cashflow_analysis"] = _parse_cashflow(cashflow)

    # ── 6. 财务风险 ──
    risk = _find_section(text, "财务风险") or _find_section(text, "三、财务风险提示")
    result["risk_analysis"] = _parse_risks(risk)

    # ── 7. 经营建议 ──
    suggestions = _find_section(text, "经营优化建议") or _find_section(text, "四、经营优化建议")
    result["suggestions"] = _parse_suggestions(suggestions)

    # ── 8. 总结 ──
    summary = _find_section(text, "总结") or _find_section(text, "五、总结")
    result["conclusion"] = _parse_conclusion(summary)

    return result


# ══════════════════════════════════════════════════════════════
#  各模块解析
# ══════════════════════════════════════════════════════════════

def _extract_title(text: str) -> str:
    """提取 # 标题"""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # 取第一行非空行
    for line in text.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("```"):
            return line[:80]
    return "经营分析报告"


def _parse_overview(section: str) -> dict:
    """解析核心财务概览"""
    result: dict[str, Any] = {}

    # 在概览中直接提取关键金额
    result["total_contract_amount"] = _find_value(section, r"总合同金额.*?" + _MONEY_RE)
    result["completed_collection"] = _find_value(section, r"已完成收款.*?" + _MONEY_RE)
    result["pending_collection"] = _find_value(section, r"待收回.*?" + _MONEY_RE)
    result["collection_ratio"] = _find_value(section, r"(?:占比|已完成).*?" + _PCT_RE)

    return _strip_nones(result)


def _parse_contract_revenue(subsection: str, full_text: str) -> dict:
    """解析合同与营收情况"""
    text = subsection if subsection else full_text
    result: dict[str, Any] = {}

    result["total_contract_amount"] = _find_value(text, r"总合同金额.*?" + _MONEY_RE)
    result["completed_collection"] = _find_value(text, r"已完成收款.*?" + _MONEY_RE)
    result["pending_collection"] = _find_value(text, r"待收回.*?" + _MONEY_RE)
    result["pending_ratio"] = _find_value(text, r"(?:待收|未收).*?(?:占比).*?" + _PCT_RE)

    # 主要项目
    projects = []
    project_items = _extract_list_items(text)
    for item in project_items:
        proj = {}
        # 匹配 "X客户XXX：金额元" 格式
        m = re.search(r"([A-Za-z\d]+客户.+?)[：:](.+)", item)
        if m:
            proj["name"] = m.group(1).strip()
            proj["detail"] = m.group(2).strip()
            proj["amount"] = _parse_money(item)
            projects.append(proj)
    if projects:
        result["projects"] = projects

    return _strip_nones(result)


def _parse_purchase(subsection: str, full_text: str) -> dict:
    """解析采购与支出结构"""
    text = subsection if subsection else full_text
    result: dict[str, Any] = {}

    result["total_purchase_amount"] = _find_value(text, r"(?:采购总支出|总采购).*?" + _MONEY_RE)

    # 主要采购类别
    categories = []
    cat_items = _extract_list_items(text)
    for item in cat_items:
        cat = {}
        m = re.search(r"(.+?)[：:].*?" + _MONEY_RE, item)
        if m:
            cat["name"] = m.group(1).strip()
            cat["amount"] = _parse_money(item)
            pct_m = re.search(_PCT_RE, item)
            if pct_m:
                cat["ratio"] = _parse_number(pct_m.group(1))
            categories.append(cat)
    if categories:
        result["categories"] = categories

    # 付款节奏
    rhythm_items = _extract_list_items(text)
    result["payment_rhythm"] = [r for r in rhythm_items if re.search(r"月.*支付|月.*待支付", r)]

    return _strip_nones(result)


def _parse_cashflow(section: str) -> dict:
    """解析现金流深度分析"""
    result: dict[str, Any] = {}

    # ── 月度预测表格 ──
    forecast = _find_subsection(section, "月度现金流预测") or _find_subsection(section, "月度现金流预测")
    table_rows = _extract_table_rows(forecast)
    monthly: dict[str, Any] = {}
    for row in table_rows:
        for key in row:
            if "收入" in key or "总收入" in key:
                monthly["income"] = _parse_money(row.get("金额（元）", "") or row.get(list(row.keys())[1], ""))
            elif "支出" in key or "总支出" in key:
                monthly["expense"] = _parse_money(row.get("金额（元）", "") or row.get(list(row.keys())[1], ""))
            elif "初始余额" in key or "月初余额" in key or "5月底" in key:
                monthly["start_balance"] = _parse_money(row.get("金额（元）", "") or row.get(list(row.keys())[1], ""))
            elif "预计余额" in key or "月底余额" in key or "期末余额" in key:
                monthly["end_balance"] = _parse_money(row.get("金额（元）", "") or row.get(list(row.keys())[1], ""))
            elif "净现金" in key or "净流入" in key:
                monthly["net_cashflow"] = _parse_money(row.get("金额（元）", "") or row.get(list(row.keys())[1], ""))
    if monthly:
        result["monthly_forecast"] = _strip_nones(monthly)

    # ── 也尝试从文本中直接提取 ──
    result["start_balance"] = _find_value(section, r"(?:初始余额|月初余额|5月底.*?余额).*?" + _MONEY_RE)
    result["expected_income"] = _find_value(section, r"(?:预计总收入|预计收入|6月预计.*?收入).*?" + _MONEY_RE)
    result["expected_expense"] = _find_value(section, r"(?:预计总支出|预计支出|6月预计.*?支出).*?" + _MONEY_RE)
    result["end_balance"] = _find_value(section, r"(?:月底预计余额|预计余额|期末余额|6月底.*?余额).*?" + _MONEY_RE)
    result["net_cashflow"] = _find_value(section, r"(?:净现金流入|净流入|净现金流).*?" + _MONEY_RE)
    result["growth_rate"] = _find_value(section, r"(?:增长|较月初).*?" + _PCT_RE)

    # ── 关键现金流节点 ──
    key_dates = _find_subsection(section, "关键现金流节点") or _find_subsection(section, "关键现金流节点")
    if key_dates:
        date_items = _extract_list_items(key_dates)
        events = []
        for item in date_items:
            m = re.search(r"(\d+月\d+日)[：:]?(.+)", item)
            if m:
                events.append({
                    "date": m.group(1),
                    "description": m.group(2).strip(),
                    "amount": _parse_money(item),
                })
        if events:
            result["key_dates"] = events

    return _strip_nones(result)


def _parse_risks(section: str) -> dict:
    """解析财务风险提示"""
    result: dict[str, Any] = {}
    risks = []

    # 解析每个 ### 子风险
    for sub_name in ["应收账款风险", "应付账款压力", "成本结构风险", "现金流风险"]:
        sub = _find_subsection(section, sub_name)
        if sub:
            items = _extract_list_items(sub)
            risk = {
                "category": sub_name,
                "items": items,
            }
            # 提取金额
            for item in items:
                amt = _parse_money(item)
                if amt:
                    risk.setdefault("amounts", []).append(amt)
                    risk.setdefault("amount_descs", []).append(item[:60])
            risks.append(risk)

    if risks:
        result["risk_categories"] = risks

    # 同时保留扁平的风险列表
    all_risk_items = _extract_list_items(section)
    if all_risk_items:
        result["all_risks"] = all_risk_items

    return _strip_nones(result)


def _parse_suggestions(section: str) -> dict:
    """解析经营优化建议"""
    result: dict[str, Any] = {}
    categories = []

    for sub_name in ["应收账款管理", "应付账款优化", "现金流管理", "合同管理", "成本控制"]:
        sub = _find_subsection(section, sub_name)
        if sub:
            items = _extract_list_items(sub)
            categories.append({
                "category": sub_name,
                "items": items,
            })

    if categories:
        result["suggestion_categories"] = categories

    # 扁平列表
    all_items = _extract_list_items(section)
    if all_items:
        result["all_suggestions"] = all_items

    return _strip_nones(result)


def _parse_conclusion(section: str) -> dict:
    """解析总结"""
    if not section:
        return {}
    result: dict[str, Any] = {}
    # 提取总结中的关键数据
    result["text"] = section.strip()
    result["net_cashflow"] = _find_value(section, r"(?:净现金流入|净流入).*?" + _MONEY_RE)
    result["end_balance"] = _find_value(section, r"(?:余额|将达到).*?" + _MONEY_RE)
    return _strip_nones(result)


# ══════════════════════════════════════════════════════════════
#  工具函数
# ══════════════════════════════════════════════════════════════

def _find_value(text: str, pattern: str) -> Optional[float]:
    """在文本中按 pattern 搜索，返回第一个捕获组的数字"""
    m = re.search(pattern, text)
    if m:
        return _parse_number(m.group(1))
    return None


def _strip_nones(d: dict) -> dict:
    """递归移除值为 None 或空列表/空字典的键"""
    if not isinstance(d, dict):
        return d
    result = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            v = _strip_nones(v)
            if not v:
                continue
        if isinstance(v, list):
            v = [_strip_nones(x) if isinstance(x, dict) else x for x in v]
            v = [x for x in v if x is not None and x != {}]
            if not v:
                continue
        result[k] = v
    return result


def _generate_title(text: str) -> str:
    """从文本开头截取标题"""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()[:100]
    first_line = text.strip().split("\n")[0][:80].strip()
    return first_line if first_line else "经营分析报告"


# ══════════════════════════════════════════════════════════════
#  对外接口
# ══════════════════════════════════════════════════════════════

def _inject_realtime_cost_data(db: Session, extracted: dict) -> dict:
    """从数据库获取真实的采购成本、人工成本、行政费用等，注入到 extracted_data 的 purchase_expense 中。
    
    这确保"采购与支出"显示的是数据库中真实数据，而非从 AI 文本中不可靠地解析。
    """
    if not extracted:
        return extracted

    svc = ProjectProfitService(db)
    cost = svc._calc_cost_structure()
    summary = svc._calc_summary_cards()

    # 构建真实的采购与支出 categories（和项目成本利润分析一致的数据源）
    real_categories = []
    for cat in cost.get("categories", []):
        if cat.get("value", 0) > 0:
            real_categories.append({
                "name": cat["name"],
                "amount": cat["value"],
                "ratio": cat["percent"],
            })

    # 如果数据库有成本数据，覆盖 AI 提取的 purchase_expense
    if real_categories:
        extracted["purchase_expense"] = {
            "total_purchase_amount": summary.get("purchase_cost"),
            "total_cost": summary.get("total_cost"),
            "labor_cost": summary.get("labor_cost"),
            "office_cost": summary.get("office_cost"),
            "tax_cost": summary.get("tax_cost"),
            "logistics_cost": summary.get("logistics_cost"),
            "categories": real_categories,
            "data_source": "database",  # 标记数据来源
        }

    # 同时用真实合同数据补充 financial_overview 和 contract_revenue
    if not extracted.get("financial_overview") or not extracted["financial_overview"].get("total_contract_amount"):
        extracted["financial_overview"] = extracted.get("financial_overview") or {}
        extracted["financial_overview"]["total_contract_amount"] = summary.get("total_contract")
        extracted["financial_overview"]["completed_collection"] = summary.get("total_received")
        extracted["financial_overview"]["pending_collection"] = summary.get("total_unreceived")

    if not extracted.get("contract_revenue") or not extracted["contract_revenue"].get("total_contract_amount"):
        extracted["contract_revenue"] = extracted.get("contract_revenue") or {}
        extracted["contract_revenue"]["total_contract_amount"] = summary.get("total_contract")
        extracted["contract_revenue"]["completed_collection"] = summary.get("total_received")
        extracted["contract_revenue"]["pending_collection"] = summary.get("total_unreceived")

    return extracted


def _is_valid_report(extracted: dict) -> bool:
    """检查提取的数据是否包含足够的有效财务信息，以判断是否为经营分析报告"""
    if not extracted:
        return False

    # 统计有效字段数（嵌套也算）
    def _count_valid(obj) -> int:
        if isinstance(obj, dict):
            return sum(_count_valid(v) for v in obj.values())
        if isinstance(obj, list):
            return sum(_count_valid(v) for v in obj)
        return 1 if obj is not None else 0

    valid_count = _count_valid(extracted)
    logger.info("[analysis_report] 提取到有效字段数: %d", valid_count)

    # 至少需要 5 个有效字段才认为是经营分析报告
    # （一个真正的经营分析报告通常有 20+ 个字段）
    return valid_count >= 5


def save_report(db: Session, ai_text: str) -> Optional[AnalysisReport]:
    """从 AI 对话文本中提取并保存经营分析报告（仅保留最新一份）
    
    如果 AI 输出不包含足够的财务分析数据，则不会覆盖已有报告，
    返回 None 表示未保存。
    """
    extracted = extract_from_text(ai_text)

    if not _is_valid_report(extracted):
        logger.info("[analysis_report] 提取数据不足，跳过保存（非经营分析报告）")
        return None

    # 注入数据库中真实的采购/成本数据，覆盖 AI 文本提取的不可靠数据
    extracted = _inject_realtime_cost_data(db, extracted)

    title = _generate_title(ai_text)

    # 删除所有旧报告，只保留最新一份
    db.query(AnalysisReport).delete()

    report = AnalysisReport(
        title=title,
        content_raw=ai_text,
        extracted_data=extracted,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    logger.info("[analysis_report] 保存报告成功, id=%d, title=%s, 提取字段数=%d",
                report.id, title, len(extracted))
    return report


def get_latest_report(db: Session) -> Optional[dict]:
    """获取最新一份分析报告"""
    report = (
        db.query(AnalysisReport)
        .order_by(AnalysisReport.created_at.desc())
        .first()
    )
    if not report:
        return None

    # 注入实时成本数据（数据库中的采购/成本可能比报告保存时更新）
    extracted = _inject_realtime_cost_data(db, report.extracted_data or {})

    return {
        "id": report.id,
        "title": report.title,
        "content_raw": report.content_raw,
        "extracted_data": extracted,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


