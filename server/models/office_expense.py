
from sqlalchemy import Boolean, Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class OfficeExpense(Base):
    __tablename__ = "office_expense"

    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    expense_type: Mapped[str] = mapped_column(String(50), comment="费用类型")
    expense_name: Mapped[str] = mapped_column(String(255), comment="费用名称")
    address: Mapped[str] = mapped_column(String(255), comment="地址")
    fiscal_month: Mapped[str] = mapped_column(String(7), comment="财务月份")
    billing_cycle: Mapped[str] = mapped_column(String(7), comment="计费周期")
    billing_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="账单金额")
    expected_payment_date: Mapped[date] = mapped_column(Date, comment="预计付款日期")
    payment_status: Mapped[str] = mapped_column(String(50), comment="付款状态")
    payer: Mapped[str] = mapped_column(String(255), comment="付款方")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")

    __table_args__ = (
    
        Index('idx_office_expense_name', 'expense_name', 'expense_type'),
        {"comment": "行政费用"},
    )