from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from server.util.database import Base


class Loan(Base):
    __tablename__ = "loan"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="自增ID")
    
    # 核心字段
    borrower_subject: Mapped[str] = mapped_column(String(50), comment="借款主体（如：企业/个人）")
    loan_type: Mapped[str] = mapped_column(String(50), comment="贷款类型（如：经营贷/信用贷）")
    lender: Mapped[str] = mapped_column(String(100), comment="银行/机构/出借人")
    product_name: Mapped[str] = mapped_column(String(100), comment="产品名称")
    
    # 金额字段（支持到千亿，保留两位小数）
    credit_limit: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, comment="授信额度")
    used_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0.00, comment="已用额度/贷款本金")
    
    # 日期字段（允许为空，因为表格中有“待定”等情况）
    loan_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="借款日")
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="到期日")
    
    # 方式与频率
    repayment_method: Mapped[str] = mapped_column(String(50), comment="还款方式（如：先息后本）")
    repayment_frequency: Mapped[str] = mapped_column(String(50), comment="还款频率（如：每月/每季）")
    
    # 担保与账户
    collateral: Mapped[str] = mapped_column(String(255), comment="担保/抵押物")
    repayment_account: Mapped[str] = mapped_column(String(100), comment="还款账户")
    
    # 备注
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备注")

    __table_args__ = (
    
        {"comment": "贷款授信"},
    )
