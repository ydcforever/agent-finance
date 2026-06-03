from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel

class PrivateTxsDto(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    transaction_date: date = Field(..., description="交易日期")
    flow_direction: str = Field(..., description="收支方向")
    payment_channel: str = Field(..., description="支付渠道")
    counterparty: str = Field(..., description="交易对象")
    amount: float = Field(..., ge=0, description="金额")
    
    related_entity: Optional[str] = Field(None, description="关联客户/供应商/项目")
    payment_nature: str = Field(..., description="款项性质")
    
    is_corporate_business: bool = Field(True, description="是否公司业务")
    accounting_status: str = Field(..., description="是否需要报销/入账状态")
    invoice_status: str = Field(..., description="是否有合同/发票状态")
    
    voucher_attachment: Optional[str] = Field(None, description="凭证截图/附件")
    handler: str = Field(..., description="经办人")
    remark: Optional[str] = Field(None, description="备注")

class PrivateTxsVo(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, 
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    id: int = Field(..., description="自增ID")
    transaction_date: str = Field(..., description="交易日期，格式：YYYY-MM-DD")
    flow_direction: str = Field(..., description="收支方向")
    payment_channel: str = Field(..., description="支付渠道")
    counterparty: str = Field(..., description="交易对象")
    amount: float = Field(..., description="金额")
    
    related_entity: Optional[str] = Field("", description="关联客户/供应商/项目")
    payment_nature: str = Field(..., description="款项性质")
    
    is_corporate_business: bool = Field(..., description="是否公司业务")
    accounting_status: str = Field(..., description="是否需要报销/入账状态")
    invoice_status: str = Field(..., description="是否有合同/发票状态")
    
    voucher_attachment: Optional[str] = Field("", description="凭证截图/附件")
    handler: str = Field(..., description="经办人")
    remark: Optional[str] = Field("", description="备注")

class PrivateTxsQuery(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=to_camel,
        populate_by_name=True
    )
    
    # 针对非公收支表特性提炼的常用筛选条件
    flow_direction: Optional[str] = Field(None, description="收支方向")
    payment_channel: Optional[str] = Field(None, description="支付渠道")
    counterparty: Optional[str] = Field(None, description="交易对象（模糊）")
    related_entity: Optional[str] = Field(None, description="关联客户/供应商/项目（模糊）")
    is_corporate_business: Optional[bool] = Field(None, description="是否公司业务")
    handler: Optional[str] = Field(None, description="经办人")