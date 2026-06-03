from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy import select
from sqlalchemy.orm import Session
from server.models import PrivateTxs
from server.schemas import PrivateTxsDto, PrivateTxsQuery, PrivateTxsVo
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page_v2

router = APIRouter(prefix="/yyy/private/txs", tags=["非公收支"])

@router.post("/save", response_model=R[PrivateTxsDto])
def save(record: PrivateTxsDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(PrivateTxsDto).filter(PrivateTxsDto.id == record.id).first()
        if not row:
            return R.error(message="人工成本记录不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = PrivateTxsDto(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=PrivateTxsDto.model_validate(row))

@router.get("/page", response_model=R[Page[PrivateTxsVo]])
def page(condition: PrivateTxsQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    stmt = select(PrivateTxs).order_by(
        PrivateTxs.transaction_date.desc(), 
        PrivateTxs.id.desc()
    )
    if condition.flow_direction:
        stmt = stmt.where(PrivateTxs.flow_direction == condition.flow_direction)
        
    if condition.payment_channel:
        stmt = stmt.where(PrivateTxs.payment_channel == condition.payment_channel)
        
    if condition.counterparty:
        stmt = stmt.where(PrivateTxs.counterparty.like(f"%{condition.counterparty}%"))
        
    if condition.related_entity:
        stmt = stmt.where(PrivateTxs.related_entity.like(f"%{condition.related_entity}%"))
        
    if condition.is_corporate_business is not None:  # 注意：布尔值过滤要防范 False 被过滤掉，不能直接 if condition
        stmt = stmt.where(PrivateTxs.is_corporate_business == condition.is_corporate_business)
        
    if condition.handler:
        stmt = stmt.where(PrivateTxs.handler == condition.handler)

    return R.success(data=get_vo_page_v2(db, stmt, PrivateTxsVo, params))

@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    record = db.get(PrivateTxs, id)
    if not record:
        return R.error(message="人工成本记录不存在")

    db.delete(record)
    db.commit()
    return R.success(data="删除成功", message="人工成本记录已成功删除")
