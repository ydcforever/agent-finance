
from sqlalchemy import Boolean, Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class TaxExpense(Base):
    __tablename__ = "tax_expense"

    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    expense_type: Mapped[str] = mapped_column(String(50), comment="费用类型")
    description: Mapped[str] = mapped_column(String(255), comment="费用描述")
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="税费金额")
    fiscal_month: Mapped[str] = mapped_column(String(7), comment="财务月份")
    declaration_date: Mapped[date] = mapped_column(Date, comment="申报日期")
    payment_date: Mapped[date] = mapped_column(Date, nullable=True, comment="支付日期")
    payment_status: Mapped[str] = mapped_column(String(50), comment="支付状态")
    payment_account: Mapped[str] = mapped_column(String(255), comment="支付账户")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")

    __table_args__ = (
    
        Index('idx_tax_expense_description', 'expense_type', 'payment_status'),
        {"comment": "财务税费"},
    )