from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models.tax_expense import TaxExpense
from server.schemas.tax_expense import TaxExpenseDto, TaxExpenseVo, TaxExpenseQuery
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/tax/expense", tags=["财务税费"])

@router.post("/save", response_model=R[TaxExpenseDto])
def save(record: TaxExpenseDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(TaxExpense).filter(TaxExpense.id == record.id).first()
        if not row:
            return R.error(message="税费不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = TaxExpense(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=TaxExpenseDto.model_validate(row))


@router.get("/page", response_model=R[Page[TaxExpenseVo]])
def page(condition: TaxExpenseQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    query = db.query(TaxExpense)

    if condition.expense_type:
        query = query.filter(TaxExpense.expense_type.like(f"%{condition.expense_type}%"))
    if condition.expense_name:
        query = query.filter(TaxExpense.expense_name.like(f"%{condition.expense_name}%"))
    if condition.fiscal_month:
        query = query.filter(TaxExpense.fiscal_month.like(f"%{condition.fiscal_month}%"))
    if condition.payment_status:
        query = query.filter(TaxExpense.payment_status.like(f"%{condition.payment_status}%"))

    return R.success(data=get_vo_page(db, query, TaxExpenseVo, params))


@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    expense = db.get(TaxExpense, id)
    if not expense:
        return R.error(message="税费不存在")

    db.delete(expense)
    db.commit()
    return R.success(data="删除成功", message="税费已成功删除")
