# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class OfficeExpenseDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )

    id: str = Field("", description="行政费用ID")
    expense_type: str = Field(..., min_length=1, max_length=50, description="费用类型")
    expense_name: str = Field(..., min_length=1, max_length=255, description="费用名称")
    address: str = Field("", min_length=1, max_length=255, description="地址")
    fiscal_month: str = Field(..., min_length=1, max_length=7, description="财务月份")
    billing_cycle: str = Field(..., min_length=1, max_length=7, description="计费周期")
    billing_amount: float = Field(..., description="账单金额")
    expected_payment_date: date = Field(..., description="预计付款日期，格式 YYYY-MM-DD")
    payment_status: str = Field(..., min_length=1, max_length=50, description="付款状态")
    payer: str = Field(..., min_length=1, max_length=255, description="付款方")
    remark: Optional[str] = Field("", description="备注信息")

class OfficeExpenseVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="行政费用ID")
    expense_type: str = Field(..., description="费用类型")
    expense_name: str = Field(..., description="费用名称")
    address: str = Field(..., description="地址")
    fiscal_month: str = Field(..., description="财务月份")
    billing_cycle: str = Field(..., description="计费周期")
    billing_amount: float = Field(..., description="账单金额")
    expected_payment_date: date = Field(..., description="预计付款日期，格式 YYYY-MM-DD")
    payment_status: str = Field(..., description="付款状态")
    payer: str = Field(..., description="付款方")
    remark: Optional[str] = Field("", description="备注信息")


class OfficeExpenseQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )
    expense_type: Optional[str] = Field(None, description="费用类型")
    expense_name: Optional[str] = Field(None, description="费用名称")
    fiscal_month: Optional[str] = Field(None, description="财务月份")
    payment_status: Optional[str] = Field(None, description="付款状态")
