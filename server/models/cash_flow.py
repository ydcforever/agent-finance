from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column

from server.util.database import Base


# ================= 1. MySQL Model (SQLAlchemy 2.0) =================
class CashFlow(Base):
    __tablename__ = "cash_flows" 
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # 核心字段
    record_date: Mapped[date] = mapped_column(Date, comment="日期")
    target_type: Mapped[str] = mapped_column(String(30), comment="对象类型（客户/供应商/物流）")
    entity_name: Mapped[str] = mapped_column(String(100), comment="客户/供应商名称")
    
    # 彻底区分：回款通常是收据(Receipt)，付款通常是支付(Payment)
    # 这里的 item_type 可以存储 "回款" / "付款" 的文本枚举
    item_type: Mapped[str] = mapped_column(String(30), comment="事项类型（回款/付款）") 
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, comment="金额")
    
    # 凭证与账户
    voucher_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="发票号码/凭证号")
    account_name: Mapped[str] = mapped_column(String(50), comment="收付款账户")
    bank_summary: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="银行流水摘要")
    
    # 日期与经办
    expected_actual_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="预计/实际日期")
    handler: Mapped[str] = mapped_column(String(50), comment="经办人")
    
    # 附件与备注
    attachment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="附件名称")
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备注")

    __table_args__ = (
        {"comment": "现金流"},
    )

