# 2. 引入 Pydantic (用于定义接口接收的数据格式)
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel
from datetime import date

# Pydantic 数据校验模型（接口收发数据用）
class ProjectProgressDto(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       # 对应 V1 的 orm_mode
        alias_generator=to_camel,   # 自动转驼峰
        populate_by_name=True       # 允许同时用原名和别名赋值
    )

    id: str = Field("", description="项目进度ID")
    related_party: str = Field(..., min_length=1, max_length=255, description="关联方，如项目/客户")
    manager: str = Field(..., min_length=1, max_length=255, description="负责人")
    construction_task: str = Field(..., min_length=1, max_length=255, description="施工任务")
    progress: str = Field(..., min_length=1, max_length=255, description="进度")
    expected_completion_date: date = Field(..., description="预计完成日期，格式 YYYY-MM-DD")
    affect_received: bool = Field(False, description="是否影响回款")
    additional_notes: str = Field("", description="补充说明")
    remark: Optional[str] = Field("", description="备注信息")
    follow_up_date: date = Field(..., description="跟进日期，格式 YYYY-MM-DD")

class ProjectProgressVo(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,       
        alias_generator=to_camel,   
        populate_by_name=True       
    )

    id: str = Field(..., description="项目进度ID")
    related_party: str = Field(..., description="关联方，如项目/客户")
    manager: str = Field(..., description="负责人")
    construction_task: str = Field(..., description="施工任务")
    progress: str = Field(..., description="进度")
    expected_completion_date: date = Field(..., description="预计完成日期")
    affect_received: bool = Field(False, description="是否影响回款")
    additional_notes: str = Field("", description="补充说明")
    remark: Optional[str] = Field("", description="备注信息")
    follow_up_date: date = Field(..., description="跟进日期")

class ProjectProgressQuery(BaseModel):
    
    model_config = ConfigDict(
        from_attributes=True,     
        alias_generator=to_camel,   
        populate_by_name=True       
    )
    
    related_party: str = Field("", description="关联方，如项目/客户，支持模糊查询")
    manager: str = Field("", description="负责人，支持模糊查询")
    affect_received: Optional[bool] = Field(None, description="是否影响回款，True/False")
    follow_up_date_from: Optional[date] = Field(None, description="跟进日期起始，格式 YYYY-MM-DD")
    follow_up_date_to: Optional[date] = Field(None, description="跟进日期结束，格式 YYYY-MM-DD")
