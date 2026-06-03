
from sqlalchemy import Boolean, Date, DateTime, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date, datetime, timezone
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class SaleContract(Base):
    __tablename__ = "sale_contract"
    
    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), comment="合同编号") 
    name: Mapped[str] = mapped_column(String(50), comment="合同名称") 
    customer_name: Mapped[str] = mapped_column(String(255), comment="客户名称")
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="合同金额")
    sign_date: Mapped[date] = mapped_column(Date, comment="签约日期")
    effective_date: Mapped[date] = mapped_column(Date, default=date.today, comment="有效期")       
    expire_date: Mapped[date] = mapped_column(Date, comment="失效期")
    progress: Mapped[str] = mapped_column(String(50), comment="合同进度")
    invoice_status: Mapped[str] = mapped_column(String(50), comment="开票状态")
    invoice_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="已开票金额")
    received_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="已收款金额")
    unreceived_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="未收款金额")
    expected_received_date: Mapped[date] = mapped_column(Date, comment="预计回款日期")
    customer_manager: Mapped[str] = mapped_column(String(255), comment="客户经理")
    has_chat: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否有聊天记录")
    attachments: Mapped[str] = mapped_column(Text, comment="附件列表，存储与合同相关的文件信息，如文件名、URL等")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
       
        Index('idx_fc_code', 'code', 'name'),
        {"comment": "销售合同信息"},
    )