from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

# 定义一个泛型变量，用来承载具体的业务数据
T = TypeVar('T')

class R(BaseModel, Generic[T]):
    """通用的 API 返回结构"""
    code: int = Field(default=200, description="业务状态码，200表示成功")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = Field(default=None, description="业务数据")

    class Config:
        from_attributes = True 

    @classmethod
    def success(cls, data: T = None, message: str = "success"):
        """快捷返回成功结果"""
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int = 400, message: str = "error"):
        """快捷返回失败结果"""
        return cls(code=code, message=message, data=None)