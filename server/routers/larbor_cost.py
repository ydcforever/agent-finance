from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models import LarborCost
from server.schemas import LaborCostDto, LaborCostQuery, LaborCostVo
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/larbor/cost", tags=["人工成本"])

@router.post("/save", response_model=R[LaborCostDto])
def save(record: LaborCostDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(LarborCost).filter(LarborCost.id == record.id).first()
        if not row:
            return R.error(message="人工成本记录不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = LarborCost(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=LaborCostDto.model_validate(row))

@router.get("/page", response_model=R[Page[LaborCostVo]])
def page(condition: LaborCostQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    query = db.query(LarborCost)

    if condition.employee:
        query = query.filter(LarborCost.employee.like(f"%{condition.employee}%"))
    if condition.fiscal_month:
        query = query.filter(LarborCost.fiscal_month.like(f"%{condition.fiscal_month}%"))
    if condition.payment_status:
        query = query.filter(LarborCost.payment_status == condition.payment_status)

    return R.success(data=get_vo_page(db, query, LaborCostVo, params))

@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    record = db.get(LarborCost, id)
    if not record:
        return R.error(message="人工成本记录不存在")

    db.delete(record)
    db.commit()
    return R.success(data="删除成功", message="人工成本记录已成功删除")
