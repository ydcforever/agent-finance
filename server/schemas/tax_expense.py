# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class TaxExpenseDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )

    id: str = Field("", description="财务税费ID")
    expense_type: str = Field(..., min_length=1, max_length=50, description="费用类型")
    description: str = Field(..., min_length=1, max_length=255, description="费用描述")
    tax_amount: float = Field(..., description="税费金额")
    fiscal_month: str = Field(..., min_length=1, max_length=7, description="财务月份")
    declaration_date: date = Field(..., description="申报日期，格式 YYYY-MM-DD")
    payment_date: Optional[date] = Field(None, description="支付日期，格式 YYYY-MM-DD")
    payment_status: str = Field(..., min_length=1, max_length=50, description="支付状态")
    payment_account: str = Field(..., min_length=1, max_length=255, description="支付账户")
    remark: Optional[str] = Field("", description="备注信息")
    
class TaxExpenseVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="财务税费ID")
    expense_type: str = Field(..., description="费用类型")
    description: str = Field(..., description="费用描述")
    tax_amount: float = Field(..., description="税费金额")
    fiscal_month: str = Field(..., description="财务月份")
    declaration_date: date = Field(..., description="申报日期，格式 YYYY-MM-DD")
    payment_date: Optional[date] = Field(None, description="支付日期，格式 YYYY-MM-DD")
    payment_status: str = Field(..., description="支付状态")
    payment_account: str = Field(..., description="支付账户")
    remark: Optional[str] = Field("", description="备注信息")

class TaxExpenseQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )
    expense_type: Optional[str] = Field(None, description="费用类型")
    fiscal_month: Optional[str] = Field(None, description="财务月份")
    payment_status: Optional[str] = Field(None, description="支付状态")
