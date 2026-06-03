from typing import Optional

from sqlalchemy import Boolean, Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class BankTransaction(Base):
    __tablename__ = "bank_transaction"
    
    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # 核心字段
    transaction_date: Mapped[date] = mapped_column(comment="交易日期")
    account_name: Mapped[str] = mapped_column(String(50), comment="账户名称")
    counterparty_name: Mapped[str] = mapped_column(String(100), comment="对方户名")
    
    # 财务金额在 MySQL 中必须使用 Numeric/Decimal 类型，防止浮点数精度丢失
    # Precision=14, Scale=2 表示最大支持千亿金额（12位整数 + 2位小数）
    income_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, comment="收入金额")
    expense_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, comment="支出金额")
    balance: Mapped[float] = mapped_column(Numeric(14, 2), comment="账户余额")
    
    summary: Mapped[str] = mapped_column(String(255), comment="摘要")
    
    # 可空字段（使用 Optional 并在 mapped_column 中设为 nullable=True）
    related_party: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="关联客户/供应商")
    related_contract: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="关联合同/项目")
    
    payment_method: Mapped[str] = mapped_column(String(50), comment="支付方式")
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备注")

    __table_args__ = (
        Index('idx_bank_transaction_account', 'account_name'),
        {"comment": "银行流水"},
    )