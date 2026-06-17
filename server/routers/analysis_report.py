"""
经营分析报告 API 路由（仅保留最新一份）
POST /yyy/report/save   — 从 AI 文本中提取并保存报告（覆盖旧报告）
GET  /yyy/report/latest — 获取最新报告
"""
import logging

from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session

from server.service.analysis_report_service import (
    save_report,
    get_latest_report,
)
from server.util.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yyy/report", tags=["经营分析报告"])


@router.post("/save", summary="保存经营分析报告")
def api_save_report(
    content: str = Form(..., description="AI 对话输出的完整文本"),
    db: Session = Depends(get_db),
):
    """
    从 AI 对话输出文本中提取结构化数据，保存为经营分析报告（仅保留最新一份）。
    返回保存后的报告 ID 和提取的数据。
    """
    report = save_report(db, content)
    return {
        "id": report.id,
        "title": report.title,
        "extracted_data": report.extracted_data,
        "created_at": report.created_at.isoformat(),
    }


@router.get("/latest", summary="获取最新经营分析报告")
def api_get_latest(db: Session = Depends(get_db)):
    """返回最新一份经营分析报告，含原始内容和提取数据"""
    report = get_latest_report(db)
    if not report:
        return {"error": "暂无分析报告"}
    return report
