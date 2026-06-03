# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class LaborCostDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )
    id: str = Field("", description="物流ID")
    employee: str = Field(..., min_length=1, description="员工")
    post: str = Field(..., min_length=1, description="岗位")
    gross_salary: float = Field(..., ge=0, description="税前工资，不能为负数")
    social_insurance_amount: float = Field(..., ge=0, description="社保费用，不能为负数")
    housing_fund_amount: float = Field("0.00", ge=0, description="公积金费用，不能为负数")
    individual_income_tax: float = Field("0.00", ge=0, description="个人所得税，不能为负数")
    net_salary: float = Field(..., ge=0, description="税后工资，不能为负数")
    fiscal_month: str = Field(..., min_length=7, max_length=7, description="财务月份，格式 YYYY-MM")
    payment_date: date = Field(..., description="发薪日期，格式 YYYY-MM-DD")
    payment_status: str = Field("", description="发薪状态")
    payment_account: str = Field("", description="发薪账户")
    remark: Optional[str] = Field("", description="备注信息")
    
    @model_validator(mode='after')
    def calculate_net_salary(self):
        # 只有当单价和数量都有值时，才触发自动计算
        if self.gross_salary is not None and self.social_insurance_amount is not None and self.housing_fund_amount is not None and self.individual_income_tax is not None:
            self.net_salary = round(self.gross_salary - self.social_insurance_amount - self.housing_fund_amount - self.individual_income_tax, 2)
        return self

class LaborCostVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="人工成本ID")
    employee: str = Field(..., description="员工")
    post: str = Field(..., description="岗位")
    gross_salary: float = Field(..., description="税前工资")
    social_insurance_amount: float = Field(..., description="社保费用")
    housing_fund_amount: float = Field(..., description="公积金费用")
    individual_income_tax: float = Field(..., description="个人所得税")
    net_salary: float = Field(..., description="税后工资")
    fiscal_month: str = Field(..., description="财务月份")
    payment_date: date = Field(..., description="发薪日期")
    payment_status: str = Field(..., description="发薪状态")
    payment_account: str = Field(..., description="发薪账户")
    remark: str = Field(..., description="备注信息")

class LaborCostQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    employee: Optional[str] = Field(None, description="员工，支持模糊查询")
    fiscal_month: Optional[str] = Field(None, description="财务月份，格式 YYYY-MM，支持模糊查询")
    payment_status: Optional[str] = Field(None, description="发薪状态，支持精确查询")
    