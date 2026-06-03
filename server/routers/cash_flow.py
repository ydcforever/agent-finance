from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy import select
from sqlalchemy.orm import Session
from server.models import CashFlow
from server.schemas import CashFlowDto, CashFlowQuery, CashFlowVo
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page_v2

router = APIRouter(prefix="/yyy/cashflow", tags=["现金流"])

@router.post("/save", response_model=R[CashFlowDto])
def save(record: CashFlowDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(CashFlowDto).filter(CashFlowDto.id == record.id).first()
        if not row:
            return R.error(message="现金流记录不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = CashFlowDto(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=CashFlowDto.model_validate(row))

@router.get("/page", response_model=R[Page[CashFlowVo]])
def page(condition: CashFlowQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    stmt = select(CashFlow).order_by(CashFlow.record_date.desc(), CashFlow.id.desc())
    
    if condition.target_type:
        stmt = stmt.where(CashFlow.target_type == condition.target_type)
    if condition.entity_name:
        stmt = stmt.where(CashFlow.entity_name.like(f"%{condition.entity_name}%"))
    if condition.item_type:
        stmt = stmt.where(CashFlow.item_type == condition.item_type)
    if condition.account_name:
        stmt = stmt.where(CashFlow.account_name == condition.account_name)
    if condition.handler:
        stmt = stmt.where(CashFlow.handler == condition.handler)

    return R.success(data=get_vo_page_v2(db, stmt, CashFlowVo, params))

@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    record = db.get(CashFlow, id)
    if not record:
        return R.error(message="现金流记录不存在")

    db.delete(record)
    db.commit()
    return R.success(data="删除成功", message="现金流记录已成功删除")
