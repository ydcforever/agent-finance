# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class SaleContractDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )

    id: str = Field("", description="销售合同ID")
    code: str = Field(..., min_length=1, max_length=50, description="合同编号")
    name: str = Field(..., min_length=1, max_length=50, description="合同名称")
    customer_name: str = Field(..., min_length=1, max_length=255, description="客户名称")
    amount: float = Field(..., ge=0, description="合同金额，不能为负数")
    sign_date: date = Field(..., description="签约日期，格式 YYYY-MM-DD")
    effective_date: date = Field(..., description="有效期，格式 YYYY-MM-DD")
    expire_date: date = Field(..., description="失效期，格式 YYYY-MM-DD")
    progress: str = Field("", description="合同进度")
    invoice_status: str = Field("", description="开票状态")
    invoice_amount: float = Field("", ge=0, description="已开票金额，不能为负数")
    received_amount: float = Field("", ge=0, description="已收款金额，不能为负数")
    unreceived_amount: float = Field("", ge=0, description="未收款金额，不能为负数")
    expected_received_date: date = Field("", description="预计回款日期，格式 YYYY-MM-DD")
    customer_manager: str = Field("", description="客户经理")
    has_chat: bool = Field(False, description="是否有聊天记录")
    attachments: str = Field("", description="附件列表，存储与合同相关的文件信息，如文件名、URL等")
    remark: Optional[str] = Field("", description="备注信息")  

    @model_validator(mode='after')
    def calculate_unreceived_amount(self):
        # 只有当单价和数量都有值时，才触发自动计算
        if self.amount is not None and self.received_amount is not None:
            self.unreceived_amount = round(self.amount - self.received_amount, 2)
        return self

class SaleContractVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="销售合同ID")
    code: str = Field(..., description="合同编号")
    name: str = Field(..., description="合同名称")
    customer_name: str = Field(..., description="客户名称")
    amount: float = Field(..., description="合同金额")
    sign_date: date = Field(..., description="签约日期")
    effective_date: date = Field(..., description="有效期")
    expire_date: date = Field(..., description="失效期")
    progress: str = Field(..., description="合同进度")
    invoice_status: str = Field(..., description="开票状态")
    invoice_amount: float = Field(..., description="已开票金额")
    received_amount: float = Field(..., description="已收款金额")
    unreceived_amount: float = Field(..., description="未收款金额")
    expected_received_date: date = Field(..., description="预计回款日期")
    customer_manager: str = Field(..., description="客户经理")
    has_chat: bool = Field(False, description="是否有聊天记录")
    attachments: str = Field("", description="附件列表，存储与合同相关的文件信息，如文件名、URL等")
    remark: str = Field("", description="备注信息")

class SaleContractQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    code: str = Field("", description="销售合同编号，支持模糊查询")
    name: str = Field("", description="合同名称，支持模糊查询")
    customer_name: str = Field("", description="客户名称，支持模糊查询")
    sign_date_from: Optional[date] = Field(None, description="签约日期起始，格式 YYYY-MM-DD")
    sign_date_to: Optional[date] = Field(None, description="签约日期结束，格式 YYYY-MM-DD")
    customer_manager: str = Field("", description="客户经理，支持模糊查询")
