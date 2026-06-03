
from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date, datetime, timezone
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class PurchaseOrder(Base):
    __tablename__ = "purchase_order"
    

    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(255), comment="采购单号")
    order_type: Mapped[str] = mapped_column(String(50), comment="采购类型") 
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="数量")
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="单价")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="总金额，自动计算得出")
    supplier: Mapped[str] = mapped_column(String(255), comment="供应商名称")
    detail: Mapped[str] = mapped_column(Text, comment="采购内容")
    compared: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否比价")
    project: Mapped[str] = mapped_column(String(255), comment="所属项目")
    related_party: Mapped[str] = mapped_column(String(255), comment="关联方，如项目/客户等")
    operator : Mapped[str] = mapped_column(String(255), comment="经办人")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")
    purchase_date: Mapped[date] = mapped_column(Date, comment="采购日期", default=date.today)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        
        # 为 code 字段单独建一个索引
        Index('idx_po_code', 'code'),
        # 创建一个复合索引：经常按供应商和日期联合查询时，这种索引效率极高
        Index('idx_po_supplier_date', 'supplier', 'purchase_date'),
        {"comment": "采购订单信息"},
    )