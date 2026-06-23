"""
财务看板 API 路由
GET /yyy/dashboard  — 获取完整看板数据（KPI + 现金流推演 + 预警）
GET /yyy/dashboard/project-profit  — 获取项目成本利润分析看板数据
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from server.service.dashboard_service import DashboardService
from server.service.project_profit_service import ProjectProfitService
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


@router.get("/receivable_payment", summary="获取收付款面板数据")
def get_receivable_payment(db: Session = Depends(get_db)):
    """返回收付款面板独立数据（客户回款进度、供应商付款、催收、刚性支付、资金缺口）"""
    svc = DashboardService(db)
    return {
        "receivable_payment": svc._calc_receivable_payment(),
        "summary": svc._build_summary(),
    }


@router.get("/project-profit", summary="获取项目成本利润分析看板数据")
def get_project_profit(db: Session = Depends(get_db)):
    """
    返回项目成本利润分析看板完整数据：

    - **summary_cards**: 合同总额、采购成本、人工成本、行政费用、税费、物流费用、总成本、估算利润、利润率
    - **cost_structure**: 成本费用结构占比（含各成本项金额、占比、颜色，以及采购成本按供应商拆解）
    - **project_payments**: 项目回款进度条（按客户/合同展示回款比例、状态标签）
    """
    svc = ProjectProfitService(db)
    return svc.get_project_profit_analysis()
