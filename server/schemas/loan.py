from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel

class LoanDto(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    borrower_subject: str = Field(..., description="借款主体")
    loan_type: str = Field(..., description="贷款类型")
    lender: str = Field(..., description="银行/机构/出借人")
    product_name: str = Field(..., description="产品名称")
    
    credit_limit: float = Field(..., ge=0, description="授信额度")
    used_amount: float = Field(..., ge=0, description="已用额度/贷款本金")
    
    # 考虑到可能填“待定”，后端接收传参时可以允许为 None，或者前端传字符串，这里用 Optional[date] 最标准
    loan_date: Optional[date] = Field(None, description="借款日")
    due_date: Optional[date] = Field(None, description="到期日")
    
    repayment_method: str = Field(..., description="还款方式")
    repayment_frequency: str = Field(..., description="还款频率")
    
    collateral: str = Field(..., description="担保/抵押物")
    repayment_account: str = Field(..., description="还款账户")
    remark: Optional[str] = Field(None, description="备注")
    

class LoanVo(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,  # 👈 允许直接从 SQLAlchemy ORM 转换
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    id: int = Field(..., description="自增ID")
    borrower_subject: str = Field(..., description="借款主体")
    loan_type: str = Field(..., description="贷款类型")
    lender: str = Field(..., description="银行/机构/出借人")
    product_name: str = Field(..., description="产品名称")
    
    credit_limit: float = Field(..., description="授信额度")
    used_amount: float = Field(..., description="已用额度/贷款本金")
    
    # 返回给前端时，将日期统一转为字符串输出，方便处理“待定”等中文字样
    loan_date: Optional[str] = Field(None, description="借款日，格式：YYYY-MM-DD")
    due_date: Optional[str] = Field(None, description="到期日，格式：YYYY-MM-DD")
    
    repayment_method: str = Field(..., description="还款方式")
    repayment_frequency: str = Field(..., description="还款频率")
    
    collateral: str = Field(..., description="担保/抵押物")
    repayment_account: str = Field(..., description="还款账户")
    remark: Optional[str] = Field("", description="备注")

class LoanQuery(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True
    )
    # 常用筛选字段
    borrower_subject: Optional[str] = Field(None, description="借款主体")
    loan_type: Optional[str] = Field(None, description="贷款类型")
    lender: Optional[str] = Field(None, description="银行/机构/出借人（支持模糊）")
    product_name: Optional[str] = Field(None, description="产品名称（支持模糊）")