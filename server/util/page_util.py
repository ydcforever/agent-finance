from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate 
from typing import Type, TypeVar
from pydantic import BaseModel
from sqlalchemy import Select
from sqlalchemy.orm import Session

VoType = TypeVar("VoType", bound=BaseModel)

def get_vo_page(db, query, vo_class: Type[VoType], params: Params) -> Page[VoType]:
    # 1. 使用官方 SQLAlchemy 扩展进行数据库分页
    orm_page = paginate(db, query, params)
    
    # 2. 批量将 ORM 对象转换为指定的 VO 对象
    vo_items = [vo_class.model_validate(orm_obj) for orm_obj in orm_page.items]
    
    # 3. 核心修改：直接传入 params 对象，而不是 page 和 size
    return Page.create(
        items=vo_items,
        total=orm_page.total,
        params=params  # 👈 传入完整的 params 对象，库内部会自动提取 page 和 size
    )

def get_vo_page_v2(db: Session, query_stmt: Select, vo_class: Type[VoType], params: Params) -> Page[VoType]:
    # 1. 使用官方 2.0 扩展进行数据库分页（此时传入的是 query_stmt 表达式）
    orm_page = paginate(db, query_stmt, params)
    
    # 2. 批量将 ORM 对象转换为指定的 VO 对象
    vo_items = [vo_class.model_validate(orm_obj) for orm_obj in orm_page.items]
    
    # 3. 传入完整的 params 对象，组装成分页格式
    return Page.create(
        items=vo_items,
        total=orm_page.total,
        params=params
    )