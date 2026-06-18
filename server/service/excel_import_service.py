"""
Excel 解析入库服务 - 将解析出的 Model 对象批量写入数据库。

用法:
    from server.service.excel_import_service import import_excel_to_db
    result = import_excel_to_db(file_path, db_session)
"""

import logging
import os
import tempfile
from typing import Any

import openpyxl
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.models import (
    PurchaseOrder,
    SaleContract,
    PurchaseContract,
    ProjectProgress,
    Logistics,
    LarborCost,
    OfficeExpense,
    TaxExpense,
    CashFlow,
    BankTransaction,
)
from server.service.excel_parser import ExcelParser

logger = logging.getLogger(__name__)


# 财务报告必须包含的 sheet 名称（至少匹配这些中的大部分才算财务报告）
_REQUIRED_SHEETS = [
    "01采购报告",
    "02客户合同",
    "03供应商合同",
    "04生产跟进",
    "05发货物流",
    "06人员工资社保",
    "07房租水电",
    "08财务税费",
    "09付款开票",
    "10银行流水",
    "11现金流预判",
]

# 最少匹配的 sheet 数量（允许缺少个别 sheet）
_MIN_MATCHED_SHEETS = 3

# 最少入库数据总条数
_MIN_TOTAL_ROWS = 5


def _is_financial_report(file_path: str) -> tuple[bool, str]:
    """检查 Excel 文件是否为财务报告模板。

    通过读取 Excel 的 sheet 名称来判断：
    - 检查是否包含预期数量的财务相关 sheet（如 01采购报告、02客户合同 等）
    - 检查解析后的总数据行数是否达到最低阈值

    Returns:
        (is_valid, reason) — is_valid 表示是否通过验证，reason 为说明
    """
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        sheet_names = wb.sheetnames
        wb.close()
    except Exception as e:
        return False, f"无法读取 Excel 文件: {e}"

    if not sheet_names:
        return False, "Excel 文件中没有 sheet"

    # 检查匹配的 sheet 数量
    matched = [name for name in _REQUIRED_SHEETS if name in sheet_names]
    match_count = len(matched)

    if match_count == 0:
        return False, f"Excel 文件中未找到任何财务报告 sheet（当前 sheet: {sheet_names[:5]}...）"

    if match_count < _MIN_MATCHED_SHEETS:
        return False, (
            f"Excel 中仅匹配到 {match_count} 个财务报告 sheet（需要至少 {_MIN_MATCHED_SHEETS} 个），"
            f"匹配的 sheet: {matched}，当前所有 sheet: {sheet_names}"
        )

    # 进一步检查解析后是否有足够数据
    parser = ExcelParser(file_path)
    try:
        parsed = parser.parse_all()
        total = sum(len(v) for v in parsed.values())
        if total < _MIN_TOTAL_ROWS:
            return False, f"解析到的数据行数不足（共 {total} 行，需要至少 {_MIN_TOTAL_ROWS} 行）"
    except Exception as e:
        return False, f"解析 Excel 数据时出错: {e}"
    finally:
        parser.close()

    logger.info(
        "[excel_import] 财务报告验证通过，匹配 sheet %d 个，总数据行 %d",
        match_count, total,
    )
    return True, "验证通过"


def import_excel_to_db(file_path: str, db: Session) -> dict[str, Any]:
    """解析 Excel 文件并将数据批量写入数据库。

    Args:
        file_path: Excel 文件路径
        db: SQLAlchemy 数据库会话

    Returns:
        {
            "success": True,
            "total": 57,
            "tables": {
                "purchase_orders": 5,
                "sale_contracts": 4,
                ...
            },
            "errors": []
        }
        如果不是财务报告，返回 {"success": False, "skipped": True, "reason": "..."}
    """
    # ── 第一步：验证是否为财务报告 ──
    is_valid, reason = _is_financial_report(file_path)
    if not is_valid:
        logger.warning("[excel_import] 非财务报告，跳过入库: %s", reason)
        return {
            "success": False,
            "skipped": True,
            "reason": reason,
        }
    parser = ExcelParser(file_path)
    parsed = parser.parse_all()

    # sheet → (model_class, list_key) 映射（跳过 11 现金流预判，它用 dict 不需要入库）
    TABLE_MAP: list[tuple[type, str]] = [
        (PurchaseOrder,     "purchase_orders"),
        (SaleContract,      "sale_contracts"),
        (PurchaseContract,  "purchase_contracts"),
        (ProjectProgress,   "project_progress"),
        (Logistics,         "logistics"),
        (LarborCost,        "labor_costs"),
        (OfficeExpense,     "office_expenses"),
        (TaxExpense,        "tax_expenses"),
        (CashFlow,          "cash_flows"),
        (BankTransaction,   "bank_transactions"),
    ]

    stats: dict[str, int] = {}
    total = 0
    errors: list[str] = []

    # ── 关闭外键检查 → TRUNCATE 所有表 → 恢复外键检查 ──
    try:
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for model_class, key in TABLE_MAP:
            try:
                db.execute(text(f"TRUNCATE TABLE {model_class.__tablename__}"))
                logger.info("[excel_import] TRUNCATE %s", key)
            except Exception as e:
                logger.warning("[excel_import] TRUNCATE %s 失败: %s", key, e)
    finally:
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

    # ── 写入数据 ──
    for model_class, key in TABLE_MAP:
        objects = parsed.get(key, [])
        count = len(objects)
        stats[key] = count

        if count == 0:
            continue

        try:
            db.add_all(objects)
            db.flush()
            total += count
            logger.info("[excel_import] %s 入库 %d 条", key, count)
        except Exception as e:
            db.rollback()
            msg = f"{key} 入库失败: {str(e)}"
            errors.append(msg)
            logger.error("[excel_import] %s", msg)

    if errors:
        return {
            "success": False,
            "total": total,
            "tables": stats,
            "errors": errors,
        }

    db.commit()
    logger.info("[excel_import] 全部入库成功，共 %d 条", total)

    return {
        "success": True,
        "total": total,
        "tables": stats,
        "errors": [],
    }


def import_uploaded_file_to_db(
    file_content: bytes,
    file_name: str,
    db: Session,
) -> dict[str, Any]:
    """将上传的文件内容保存为临时文件，解析并入库。

    Args:
        file_content: 文件二进制内容
        file_name: 原始文件名
        db: 数据库会话

    Returns:
        同 import_excel_to_db
    """
    suffix = os.path.splitext(file_name)[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        return import_excel_to_db(tmp_path, db)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
