from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models.purchase_contract import PurchaseContract
from server.schemas.purchase_contract import PurchaseContractDto, PurchaseContractVo, PurchaseContractQuery
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/purchase/contract", tags=["采购合同"])

@router.post("/save", response_model=R[PurchaseContractDto])
def save(record: PurchaseContractDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(PurchaseContract).filter(PurchaseContract.id == record.id).first()
        if not row:
            return R.error(message="采购合同不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = PurchaseContract(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=PurchaseContractDto.model_validate(row))


@router.get("/page", response_model=R[Page[PurchaseContractVo]])
def page(condition: PurchaseContractQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    query = db.query(PurchaseContract)
    if condition.code:
        query = query.filter(PurchaseContract.code.like(f"%{condition.code}%"))
    if condition.name:
        query = query.filter(PurchaseContract.name.like(f"%{condition.name}%"))
    if condition.supplier_name:
        query = query.filter(PurchaseContract.supplier_name.like(f"%{condition.supplier_name}%"))
    if condition.delivery_status:
        query = query.filter(PurchaseContract.delivery_status == condition.delivery_status)
    if condition.confirmed is not None:
        query = query.filter(PurchaseContract.confirmed == condition.confirmed)
    if condition.operator:
        query = query.filter(PurchaseContract.operator.like(f"%{condition.operator}%"))
    if condition.min_amount is not None:
        query = query.filter(PurchaseContract.amount >= condition.min_amount)
    if condition.max_amount is not None:
        query = query.filter(PurchaseContract.amount <= condition.max_amount)
    if condition.sign_date_from:
        query = query.filter(PurchaseContract.sign_date >= condition.sign_date_from)
    if condition.sign_date_to:
        query = query.filter(PurchaseContract.sign_date <= condition.sign_date_to)

    return R.success(data=get_vo_page(db, query, PurchaseContractVo, params))


@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    contract = db.get(PurchaseContract, id)
    if not contract:
        return R.error(message="采购合同不存在")

    db.delete(contract)
    db.commit()
    return R.success(data="删除成功", message="采购合同已成功删除")
