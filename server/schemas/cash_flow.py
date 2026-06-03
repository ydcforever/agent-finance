from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from pydantic.alias_generators import to_camel

# ================= 2. Data Transfer Object (Dto) =================
class CashFlowDto(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    
    record_date: date = Field(..., description="日期")
    target_type: str = Field(..., description="对象类型")
    entity_name: str = Field(..., description="客户/供应商名称")
    item_type: str = Field(..., description="事项类型（回款/付款）")
    amount: float = Field(..., ge=0, description="金额")
    
    voucher_no: Optional[str] = Field(None, description="发票号码/凭证号")
    account_name: str = Field(..., description="收付款账户")
    bank_summary: Optional[str] = Field(None, description="银行流水摘要")
    
    expected_actual_date: Optional[date] = Field(None, description="预计/实际日期")
    handler: str = Field(..., description="经办人")
    attachment_name: Optional[str] = Field(None, description="附件名称")
    remark: Optional[str] = Field(None, description="备注")


# ================= 3. View Object (Vo) =================
class CashFlowVo(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    
    id: int = Field(..., description="自增ID")
    record_date: str = Field(..., description="日期，格式：YYYY-MM-DD")
    target_type: str = Field(..., description="对象类型")
    entity_name: str = Field(..., description="客户/供应商名称")
    item_type: str = Field(..., description="事项类型")
    amount: float = Field(..., description="金额")
    
    voucher_no: Optional[str] = Field("", description="发票号码/凭证号")
    account_name: str = Field(..., description="收付款账户")
    bank_summary: Optional[str] = Field("", description="银行流水摘要")
    
    expected_actual_date: Optional[str] = Field("", description="预计/实际日期")
    handler: str = Field(..., description="经办人")
    attachment_name: Optional[str] = Field("", description="附件名称")
    remark: Optional[str] = Field("", description="备注")


# ================= 4. Query Object & Filter =================
class CashFlowQuery(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=to_camel, populate_by_name=True)
    
    target_type: Optional[str] = Field(None, description="对象类型")
    entity_name: Optional[str] = Field(None, description="客户/供应商名称（模糊）")
    item_type: Optional[str] = Field(None, description="事项类型（回款/付款）")
    account_name: Optional[str] = Field(None, description="收付款账户")
    handler: Optional[str] = Field(None, description="经办人")