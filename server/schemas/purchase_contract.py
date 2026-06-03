# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class PurchaseContractDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )

    id: str = Field("", description="采购合同ID")
    code: str = Field(..., min_length=1, max_length=50, description="合同编号")
    name: str = Field(..., min_length=1, max_length=50, description="合同名称")
    supplier_name: str = Field(..., min_length=1, max_length=255, description="供应商名称")
    amount: float = Field(..., ge=0, description="合同金额，不能为负数")
    sign_date: date = Field(..., description="签约日期，格式 YYYY-MM-DD")
    detail: str = Field(..., min_length=1, max_length=255, description="采购内容")
    payment_type: str = Field(..., min_length=1, max_length=50, description="付款方式")
    payment_amount: float = Field("", ge=0, description="已付款金额，不能为负数")
    unpayment_amount: float = Field("", ge=0, description="未付款金额，不能为负数")
    expected_payment_date: date = Field("", description="预计付款日期，格式 YYYY-MM-DD")
    delivery_status: str = Field("", description="发货状态")
    confirmed: bool = Field(False, description="签单状态")
    operator: str = Field(..., description="经办人")
    remark: Optional[str] = Field("", description="备注信息")

    @model_validator(mode='after')
    def calculate_unpayment_amount(self):
        # 只有当单价和数量都有值时，才触发自动计算
        if self.amount is not None and self.payment_amount is not None:
            self.unpayment_amount = round(self.amount - self.payment_amount, 2)
        return self

class PurchaseContractVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="采购订单ID")
    code: str = Field(..., description="合同编号")
    name: str = Field(..., description="合同名称")
    supplier_name: str = Field(..., description="供应商名称")
    amount: float = Field(..., description="合同金额")
    sign_date: date = Field(..., description="签约日期")
    detail: str = Field(..., description="采购内容")
    payment_type: str = Field(..., description="付款方式")
    payment_amount: float = Field(..., description="已付款金额")
    unpayment_amount: float = Field(..., description="未付款金额")
    expected_payment_date: date = Field(..., description="预计付款日期")
    delivery_status: str = Field(..., description="发货状态")
    confirmed: bool = Field(..., description="签单状态")
    operator: str = Field(..., description="经办人")
    remark: str = Field(..., description="备注信息")

class PurchaseContractQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    code: str = Field("", description="采购单号，支持模糊查询")
    name: str = Field("", description="合同名称，支持模糊查询")
    supplier_name: str = Field("", description="供应商名称，支持模糊查询")
    min_amount: Optional[float] = Field(None, ge=0, description="最小合同金额，不能为负数")
    max_amount: Optional[float] = Field(None, ge=0, description="最大合同金额，不能为负数")
    sign_date_from: Optional[date] = Field(None, description="签约日期起，格式 YYYY-MM-DD")
    sign_date_to: Optional[date] = Field(None, description="签约日期止，格式 YYYY-MM-DD")
    delivery_status: Optional[str] = Field(None, description="发货状态")
    confirmed: Optional[bool] = Field(None, description="签单状态")
    operator: str = Field("", description="经办人，支持模糊查询")
