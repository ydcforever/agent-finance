
from sqlalchemy import Boolean, Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class LarborCost(Base):
    __tablename__ = "larbor_cost"
    
    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee: Mapped[str] = mapped_column(String(255), comment="员工")
    post: Mapped[str] = mapped_column(String(255), comment="岗位")
    gross_salary: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="税前工资")
    social_insurance_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="社保费用")
    housing_fund_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="公积金费用")
    individual_income_tax: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="个人所得税")
    net_salary: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="税后工资")
    fiscal_month: Mapped[str] = mapped_column(String(7), comment="财务月份")
    payment_date: Mapped[date] = mapped_column(Date, comment="发薪日期")
    payment_status: Mapped[str] = mapped_column(String(50), comment="发薪状态")
    payment_account: Mapped[str] = mapped_column(String(255), comment="发薪账户")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")
    

    __table_args__ = (
        Index('idx_larbor_cost_employee', 'employee'),
        {"comment": "人工成本"},
    )