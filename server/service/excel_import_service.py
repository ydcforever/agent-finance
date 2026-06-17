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
    """
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
