from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy import select
from sqlalchemy.orm import Session
from server.models import Loan
from server.schemas import LoanDto, LoanQuery, LoanVo
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page_v2

router = APIRouter(prefix="/yyy/loan", tags=["贷款授信"])

@router.post("/save", response_model=R[LoanDto])
def save(record: LoanDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(LoanDto).filter(LoanDto.id == record.id).first()
        if not row:
            return R.error(message="人工成本记录不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = LoanDto(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=LoanDto.model_validate(row))

@router.get("/page", response_model=R[Page[LoanVo]])
def page(condition: LoanQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    stmt = select(Loan).order_by(Loan.due_date.asc(), Loan.id.desc())
    
    # 2. 动态拼接
    if condition.borrower_subject:
        stmt = stmt.where(Loan.borrower_subject == condition.borrower_subject)
        
    if condition.loan_type:
        stmt = stmt.where(Loan.loan_type == condition.loan_type)
        
    if condition.lender:
        stmt = stmt.where(Loan.lender.like(f"%{condition.lender}%"))
        
    if condition.product_name:
        stmt = stmt.where(Loan.product_name.like(f"%{condition.product_name}%"))

    return R.success(data=get_vo_page_v2(db, stmt, LoanVo, params))

@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    record = db.get(Loan, id)
    if not record:
        return R.error(message="人工成本记录不存在")

    db.delete(record)
    db.commit()
    return R.success(data="删除成功", message="人工成本记录已成功删除")
