from fastapi import APIRouter, Depends

from fastapi_pagination import Page, Params
from sqlalchemy.orm import Session
from server.models.project_progress import ProjectProgress
from server.schemas.project_progress import ProjectProgressDto, ProjectProgressVo, ProjectProgressQuery
from server.util import get_db
from server.util import R
from server.util.page_util import get_vo_page

router = APIRouter(prefix="/yyy/project/progress", tags=["项目进度"])

@router.post("/save", response_model=R[ProjectProgressDto])
def save(record: ProjectProgressDto, db: Session = Depends(get_db)):
    record_data = record.model_dump(exclude_unset=True)

    if record.id:
        row = db.query(ProjectProgress).filter(ProjectProgress.id == record.id).first()
        if not row:
            return R.error(message="项目进度不存在")

        for key, value in record_data.items():
            setattr(row, key, value)
    else:
        row = ProjectProgress(**record_data)
        db.add(row)

    db.commit()
    db.refresh(row)
    return R.success(data=ProjectProgressDto.model_validate(row))


@router.get("/page", response_model=R[Page[ProjectProgressVo]])
def page(condition: ProjectProgressQuery = Depends(), db: Session = Depends(get_db), params: Params = Depends()):
    query = db.query(ProjectProgress)

    if condition.related_party:
        query = query.filter(ProjectProgress.related_party.like(f"%{condition.related_party}%"))
    if condition.manager:
        query = query.filter(ProjectProgress.manager.like(f"%{condition.manager}%"))
    if condition.affect_received is not None:
        query = query.filter(ProjectProgress.affect_received == condition.affect_received)
    if condition.follow_up_date_from:
        query = query.filter(ProjectProgress.follow_up_date >= condition.follow_up_date_from)
    if condition.follow_up_date_to:
        query = query.filter(ProjectProgress.follow_up_date <= condition.follow_up_date_to)

    return R.success(data=get_vo_page(db, query, ProjectProgressVo, params))


@router.delete("/delete", response_model=R[str])
def delete(id: str, db: Session = Depends(get_db)):
    progress = db.get(ProjectProgress, id)
    if not progress:
        return R.error(message="项目进度不存在")

    db.delete(progress)
    db.commit()
    return R.success(data="删除成功", message="项目进度已成功删除")
