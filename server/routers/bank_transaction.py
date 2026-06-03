from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy import select
from sqlalchemy.orm import Session
from server.models import BankTransaction
from server.schemas import BankTransactionDto, BankTransactionQuery, BankTransactionVo
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page_v2

router = APIRouter(prefix="/yyy/bank/transaction", tags=["银行流水"])

@router.post("/save", response_model=R[BankTransactionDto])
def save(record: BankTransactionDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(BankTransaction).filter(BankTransaction.id == record.id).first()
        if not row:
            return R.error(message="流水账单不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = BankTransaction(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=BankTransactionDto.model_validate(row))

@router.get("/page", response_model=R[Page[BankTransactionVo]], description="分页接口")
def page(condition: BankTransactionQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    stmt = select(BankTransaction)

    if condition.account_name:
      stmt = stmt.where(BankTransaction.account_name.like(f"%{condition.account_name}%"))
    if condition.counterparty_name:
      stmt = stmt.where(BankTransaction.counterparty_name.like(f"%{condition.counterparty_name}%"))
    
    if condition.summary:
      stmt = stmt.where(BankTransaction.summary.like(f"%{condition.summary}%"))
    
    if condition.related_party:
      stmt = stmt.where(BankTransaction.related_party.like(f"%{condition.related_party}%"))
    
    if condition.related_contract:
      stmt = stmt.where(BankTransaction.related_contract.like(f"%{condition.related_contract}%"))
    
    if condition.payment_method:
      # 2.0 推荐精确匹配
      stmt = stmt.where(BankTransaction.payment_method == condition.payment_method)

    return R.success(data=get_vo_page_v2(db, stmt, BankTransactionVo, params))


@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    find = db.get(BankTransaction, id)
    if not find:
        return R.error(message="流水账单不存在")

    db.delete(find)
    db.commit()
    return R.success(data="删除成功", message="流水账单已成功删除")
