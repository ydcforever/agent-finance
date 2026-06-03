from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Date, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from server.util.database import Base

class PrivateTxs(Base):
    __tablename__ = "private_txs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transaction_date: Mapped[date] = mapped_column(Date, comment="交易日期")
    flow_direction: Mapped[str] = mapped_column(String(20), comment="收支方向")
    payment_channel: Mapped[str] = mapped_column(String(50), comment="支付渠道")
    counterparty: Mapped[str] = mapped_column(String(100), comment="交易对象")
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, comment="金额")
    related_entity: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="关联客户/供应商/项目")
    payment_nature: Mapped[str] = mapped_column(String(100), comment="款项性质")
    is_corporate_business: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否公司业务")
    accounting_status: Mapped[str] = mapped_column(String(100), comment="是否需要报销/入账状态")
    invoice_status: Mapped[str] = mapped_column(String(100), comment="是否有合同/发票状态")
    voucher_attachment: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="凭证截图")
    handler: Mapped[str] = mapped_column(String(50), comment="经办人")
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备注")
