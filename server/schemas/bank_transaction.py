# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class BankTransactionDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )

    id: str = Field("", description="流水ID")
    transaction_date: date = Field(..., description="交易日期")
    account_name: str = Field(..., description="账户名称")
    counterparty_name: str = Field(..., description="对方户名")
    
    # 财务金额推荐使用 float 或 Decimal
    income_amount: float = Field(..., ge=0, description="收入金额")
    expense_amount: float = Field(..., ge=0, description="支出金额")
    balance: float = Field(..., description="账户余额")
    
    summary: str = Field(..., description="摘要")
    
    # 以下为可选的关联字段（允许为 None/空字符串）
    related_party: Optional[str] = Field(None, description="关联客户/供应商")
    related_contract: Optional[str] = Field(None, description="关联合同/项目")
    
    payment_method: str = Field(..., description="支付方式")
    remark: Optional[str] = Field(None, description="备注")


class BankTransactionVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="行政费用ID")
    transaction_date: date = Field(..., description="交易日期，格式：YYYY-MM-DD")
    account_name: str = Field(..., description="账户名称")
    counterparty_name: str = Field(..., description="对方户名")
    
    # 前端展示金额一般也是 float，但格式化通常交由前端逻辑（加千分位等）
    income_amount: float = Field(..., description="收入金额")
    expense_amount: float = Field(..., description="支出金额")
    balance: float = Field(..., description="账户余额")
    
    summary: str = Field(..., description="摘要")
    
    # 允许返回给前端时为 None 或空字符串
    related_party: Optional[str] = Field("", description="关联客户/供应商")
    related_contract: Optional[str] = Field("", description="关联合同/项目")
    
    payment_method: str = Field(..., description="支付方式")
    remark: Optional[str] = Field("", description="备注")


class BankTransactionQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )
    account_name: Optional[str] = Field(None, description="账户名称（精确或模糊）")
    counterparty_name: Optional[str] = Field(None, description="对方户名（支持模糊搜索）")
    summary: Optional[str] = Field(None, description="摘要关键词")
    related_party: Optional[str] = Field(None, description="关联客户/供应商")
    related_contract: Optional[str] = Field(None, description="关联合同/项目")
    payment_method: Optional[str] = Field(None, description="支付方式")
