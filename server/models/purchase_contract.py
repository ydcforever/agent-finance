
from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date, datetime, timezone
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class PurchaseContract(Base):
    __tablename__ = "purchase_contract"
    
    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), comment="合同编号") 
    name: Mapped[str] = mapped_column(String(50), comment="合同名称") 
    supplier_name: Mapped[str] = mapped_column(String(255), comment="供应商名称")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="合同金额")
    sign_date: Mapped[date] = mapped_column(Date, comment="签约日期")
    detail: Mapped[str] = mapped_column(Text, comment="采购内容")
    payment_type: Mapped[str] = mapped_column(String(50), comment="付款方式")
    payment_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="已付款金额")
    unpayment_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="未付款金额")
    expected_payment_date: Mapped[date] = mapped_column(Date, comment="预计付款日期")
    delivery_status: Mapped[str] = mapped_column(String(50), comment="发货状态")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, comment="签单状态")
    operator: Mapped[str] = mapped_column(String(255), comment="经办人")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (

        Index('idx_pc_code', 'code', 'name'),
        {"comment": "采购合同信息"},
    )