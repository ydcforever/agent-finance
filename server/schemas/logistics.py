# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class LogisticsDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )
    id: str = Field("", description="物流ID")
    company: str = Field(..., min_length=1, description="物流公司名称")
    tracking_number: str = Field(..., min_length=1, description="物流单号")
    detail: str = Field(..., description="物流内容")
    quantity: float = Field(..., gt=0, description="数量，必须大于0")
    ship_date: date = Field(..., description="发货日期，格式 YYYY-MM-DD")
    shipped_out: bool = Field(False, description="是否发货")
    delivery_type: str = Field("", description="配送方式")
    related_party: str = Field("", description="关联方，如项目/客户等")
    amount: float = Field(..., ge=0, description="物流费用，不能为负数")
    payment_status: str = Field("", description="付款状态")
    payment_date: date = Field("", description="付款日期，格式 YYYY-MM-DD")
    attachment: str = Field("", description="附件URL")
    remark: Optional[str] = Field("", description="备注信息")

class LogisticsVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="采购订单ID")
    company: str = Field(..., description="物流公司名称")
    tracking_number: str = Field(..., description="物流单号")
    detail: str = Field(..., description="物流内容")
    quantity: float = Field(..., description="数量")
    ship_date: date = Field(..., description="发货日期")
    shipped_out: bool = Field(..., description="是否发货")
    delivery_type: str = Field(..., description="配送方式")
    related_party: str = Field(..., description="关联方，如项目/客户等")
    amount: float = Field(..., description="物流费用")
    payment_status: str = Field(..., description="付款状态")
    payment_date: date = Field(..., description="付款日期，格式 YYYY-MM-DD")
    attachment: str = Field(..., description="附件URL")
    remark: str = Field(..., description="备注信息")

class LogisticsQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    company: Optional[str] = Field(None, description="物流公司名称，支持模糊查询")
    tracking_number: Optional[str] = Field(None, description="物流单号，支持模糊查询")
    related_party: Optional[str] = Field(None, description="关联方，支持模糊查询")
    payment_status: Optional[str] = Field(None, description="付款状态，支持精确查询")
    ship_date_from: Optional[date] = Field(None, description="发货日期起始，格式 YYYY-MM-DD")
    ship_date_to: Optional[date] = Field(None, description="发货日期结束，格式 YYYY-MM-DD")
    