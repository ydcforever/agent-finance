from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models import Logistics
from server.schemas import LogisticsDto, LogisticsVo, LogisticsQuery
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/logistics", tags=["物流信息"])

@router.post("/save", response_model=R[LogisticsDto])
def save(record: LogisticsDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(Logistics).filter(Logistics.id == record.id).first()
        if not row:
            return R.error(message="物流记录不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = Logistics(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=LogisticsDto.model_validate(row))

@router.get("/page", response_model=R[Page[LogisticsVo]])
def page(condition: LogisticsQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    query = db.query(Logistics)

    if condition.company:
        query = query.filter(Logistics.company.like(f"%{condition.company}%"))
    if condition.tracking_number:
        query = query.filter(Logistics.tracking_number.like(f"%{condition.tracking_number}%"))
    if condition.related_party:
        query = query.filter(Logistics.related_party.like(f"%{condition.related_party}%"))
    if condition.payment_status:
        query = query.filter(Logistics.payment_status == condition.payment_status)
    if condition.ship_date_from:
        query = query.filter(Logistics.ship_date >= condition.ship_date_from)
    if condition.ship_date_to:
        query = query.filter(Logistics.ship_date <= condition.ship_date_to)
    return R.success(data=get_vo_page(db, query, LogisticsVo, params))

@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    logistics = db.get(Logistics, id)
    if not logistics:
        return R.error(message="物流记录不存在")

    db.delete(logistics)
    db.commit()
    return R.success(data="删除成功", message="物流记录已成功删除")
