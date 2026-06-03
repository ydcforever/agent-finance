# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class PurchaseOrderDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )

    id: str = Field("", description="采购订单ID")
    code: str = Field(..., min_length=1, max_length=50, description="采购单号")
    order_type: str = Field(..., description="采购类型") 
    quantity: float = Field(..., gt=0, description="数量，必须大于0")
    price: float = Field(..., gt=0, description="单价，必须大于0")
    amount: float = Field(..., ge=0, description="总金额，不能为负数")
    supplier: str = Field(..., min_length=1, description="供应商名称")
    
    # 非必填字段，给个默认值，前端不传也不会报错
    detail: str = Field("", description="采购详情")
    remark: Optional[str] = Field("", description="备注信息")
    
    compared: bool = Field(False, description="是否已比价")
    project: str = Field("", description="所属项目")
    related_party: str = Field("", description="关联方")
    operator: str = Field(..., description="操作员")
    
    purchase_date: date = Field(..., description="采购日期，格式 YYYY-MM-DD")

    @model_validator(mode='after')
    def calculate_amount(self):
        # 只有当单价和数量都有值时，才触发自动计算
        if self.price is not None and self.quantity is not None:
            self.amount = round(self.price * self.quantity, 2)
        return self

class PurchaseOrderVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="采购订单ID")
    code: str = Field(..., description="采购单号")
    order_type: str = Field(..., description="采购类型") 
    quantity: float = Field(..., description="数量")
    price: float = Field(..., description="单价")
    amount: float = Field(..., description="总金额")
    supplier: str = Field(..., description="供应商名称")
    
    # 非必填字段，给个默认值，防止数据库里是 NULL 导致序列化报错
    detail: str = Field("", description="采购详情")
    remark: str = Field("", description="备注信息")
    
    compared: bool = Field(False, description="是否已比价")
    project: str = Field("", description="所属项目")
    related_party: str = Field("", description="关联方")
    operator: str = Field(..., description="操作员")
    
    purchase_date: date = Field(..., description="采购日期，格式 YYYY-MM-DD")

class PurchaseOrderQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    code: str = Field("", description="采购单号，支持模糊查询")
    supplier: str = Field("", description="供应商名称，支持模糊查询")
    project: str = Field("", description="所属项目，支持模糊查询")
    related_party: str = Field("", description="关联方，支持模糊查询")
    operator: str = Field("", description="操作员，支持模糊查询")
    
    # ✅ 正确写法：加上 Optional，明确告诉 Pydantic 这个字段允许为 None
    purchase_date_from: str = Field("", description="采购日期起，格式 YYYY-MM-DD")
    purchase_date_to: str = Field("", description="采购日期止，格式 YYYY-MM-DD")