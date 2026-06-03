
from sqlalchemy import Boolean, Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class Logistics(Base):
    __tablename__ = "logistics"
    

    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company: Mapped[str] = mapped_column(String(255), comment="物流公司名称")
    tracking_number: Mapped[str] = mapped_column(String(255), comment="物流单号")
    detail: Mapped[str] = mapped_column(Text, comment="物流内容")
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="数量")
    ship_date: Mapped[date] = mapped_column(Date, comment="发货日期")
    shipped_out: Mapped[bool] = mapped_column(Boolean, comment="是否发货")
    delivery_type: Mapped[str] = mapped_column(String(50), comment="配送方式")
    related_party: Mapped[str] = mapped_column(String(255), comment="关联方，如项目/客户等")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="物流费用")
    payment_status: Mapped[str] = mapped_column(String(50), comment="付款状态")
    payment_date: Mapped[date] = mapped_column(Date, comment="付款日期")
    attachment: Mapped[str] = mapped_column(String(255), comment="附件URL")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")


    __table_args__ = (
    
        Index('idx_logistics_tracking_number', 'tracking_number'),
        {"comment": "物流信息"},
    )