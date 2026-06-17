"""
财务看板 API 路由
GET /yyy/dashboard  — 获取完整看板数据（KPI + 现金流推演 + 预警）
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.service.dashboard_service import DashboardService
from server.util.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/yyy/dashboard", tags=["现金流雷达"])


@router.get("/view", summary="获取财务看板数据")
def get_dashboard(db: Session = Depends(get_db)):
    """
    返回看板完整数据：

    - **kpi_cards**: 4 个核心 KPI（账面余额、未来30天回款/支出、资金缺口）
    - **cashflow_forecast**: 7/15/30天现金流推演 + 每日时序
    - **alerts**: 基于规则的风险预警
    - **summary**: 数据汇总（应收/应付/余额）
    """
    svc = DashboardService(db)
    return svc.get_dashboard()
