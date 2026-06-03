from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models.office_expense import OfficeExpense
from server.schemas.office_expense import OfficeExpenseDto, OfficeExpenseQuery, OfficeExpenseVo
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/office/expense", tags=["行政费用"])

@router.post("/save", response_model=R[OfficeExpenseDto])
def save(record: OfficeExpenseDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(OfficeExpense).filter(OfficeExpense.id == record.id).first()
        if not row:
            return R.error(message="行政费用不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = OfficeExpense(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=OfficeExpenseDto.model_validate(row))


@router.get("/page", response_model=R[Page[OfficeExpenseVo]])
def page(condition: OfficeExpenseQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    query = db.query(OfficeExpense)

    if condition.expense_type:
        query = query.filter(OfficeExpense.expense_type.like(f"%{condition.expense_type}%"))
    if condition.expense_name:
        query = query.filter(OfficeExpense.expense_name.like(f"%{condition.expense_name}%"))
    if condition.fiscal_month:
        query = query.filter(OfficeExpense.fiscal_month.like(f"%{condition.fiscal_month}%"))
    if condition.payment_status:
        query = query.filter(OfficeExpense.payment_status.like(f"%{condition.payment_status}%"))

    return R.success(data=get_vo_page(db, query, OfficeExpenseVo, params))


@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    expense = db.get(OfficeExpense, id)
    if not expense:
        return R.error(message="行政费用不存在")

    db.delete(expense)
    db.commit()
    return R.success(data="删除成功", message="行政费用已成功删除")
