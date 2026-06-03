from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models import PurchaseOrder
from server.schemas import PurchaseOrderDto, PurchaseOrderVo, PurchaseOrderQuery
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/purchase/order", tags=["采购订单"])

@router.post("/save", response_model=R[PurchaseOrderDto])
def save(record: PurchaseOrderDto, db: Session = Depends(get_db)) : 
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
       row = db.query(PurchaseOrder).filter(PurchaseOrder.id == record.id).first()

       calc_price = record.price if record.price is not None else row.price
       calc_quantity = record.quantity if record.quantity is not None else row.quantity
        
       # 手动触发一次计算逻辑（或者直接在这里算出 amount 塞进 record_data）
       if calc_price is not None and calc_quantity is not None:
            record_data['amount'] = round(calc_price * calc_quantity, 2)

       for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = PurchaseOrder(**record_data)
        db.add(row)
    db.commit()
    db.refresh(row)
    return R.success(data=PurchaseOrderDto.model_validate(row)) 
     
   
@router.get("/page", response_model=R[Page[PurchaseOrderVo]])
def page(condition: PurchaseOrderQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()) : 
    # 把接口收来的数据，打包成数据库模型对象
    query = db.query(PurchaseOrder)
    if condition.code:
        query = query.filter(PurchaseOrder.code.like(f"%{condition.code}%"))
    if condition.supplier:
        query = query.filter(PurchaseOrder.supplier.like(f"%{condition.supplier}%"))
    if condition.project:
        query = query.filter(PurchaseOrder.project.like(f"%{condition.project}%"))
    if condition.related_party:
        query = query.filter(PurchaseOrder.related_party.like(f"%{condition.related_party}%"))
    if condition.operator:
        query = query.filter(PurchaseOrder.operator.like(f"%{condition.operator}%"))
    if condition.purchase_date_from:
        query = query.filter(PurchaseOrder.purchase_date >= condition.purchase_date_from)
    if condition.purchase_date_to:
        query = query.filter(PurchaseOrder.purchase_date <= condition.purchase_date_to)
    return R.success(data=get_vo_page(db, query, PurchaseOrderVo, params))     
     

@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)) : 
     order = db.get(PurchaseOrder, id)
     if not order:
          return R.error(message="订单不存在")
     db.delete(order)     
     db.commit()
     return R.success(data="删除成功", message="采购订单已成功删除")   
