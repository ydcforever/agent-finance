from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models import SaleContract
from server.schemas import SaleContractDto, SaleContractVo, SaleContractQuery
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/sale/contract", tags=["销售合同"])

@router.post("/save", response_model=R[SaleContractDto])
def save(record: SaleContractDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(SaleContract).filter(SaleContract.id == record.id).first()
        if not row:
            return R.error(message="销售合同不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = SaleContract(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=SaleContractDto.model_validate(row))
     
   
@router.get("/page", response_model=R[Page[SaleContractVo]])
def page(condition: SaleContractQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    query = db.query(SaleContract)
    if condition.code:
        query = query.filter(SaleContract.code.like(f"%{condition.code}%"))
    if condition.name:
        query = query.filter(SaleContract.name.like(f"%{condition.name}%"))
    if condition.customer_name:
        query = query.filter(SaleContract.customer_name.like(f"%{condition.customer_name}%"))
    if condition.customer_manager:
        query = query.filter(SaleContract.customer_manager.like(f"%{condition.customer_manager}%"))
    if condition.sign_date_from:
        query = query.filter(SaleContract.sign_date >= condition.sign_date_from)
    if condition.sign_date_to:
        query = query.filter(SaleContract.sign_date <= condition.sign_date_to)
    return R.success(data=get_vo_page(db, query, SaleContractVo, params))
     

@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    contract = db.get(SaleContract, id)
    if not contract:
        return R.error(message="销售合同不存在")

    db.delete(contract)
    db.commit()
    return R.success(data="删除成功", message="销售合同已成功删除")
