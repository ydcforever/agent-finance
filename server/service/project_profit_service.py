"""
项目成本利润分析服务 —— 基于入库数据，计算合同总额、采购成本、估算利润、
成本费用结构占比、项目回款进度条。

用法:
    from server.service.project_profit_service import ProjectProfitService
    svc = ProjectProfitService(db)
    data = svc.get_project_profit_analysis()  # -> dict
"""

import logging
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.models import (
    SaleContract,
    PurchaseOrder,
    PurchaseContract,
    LarborCost,
    OfficeExpense,
    TaxExpense,
    Logistics,
)

logger = logging.getLogger(__name__)


class ProjectProfitService:
    """项目成本利润分析服务"""

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────── 公开入口 ──────────────────────────────
    def get_project_profit_analysis(self) -> dict[str, Any]:
        """返回完整的项目成本利润分析数据"""
        return {
            "summary_cards": self._calc_summary_cards(),
            "cost_structure": self._calc_cost_structure(),
            "project_payments": self._calc_project_payments(),
        }

    # ─────────────────── ① 关键指标卡片 ───────────────────
    def _calc_summary_cards(self) -> dict:
        """计算合同总额、采购成本、估算利润"""
        # 合同总额 = 所有销售合同金额之和
        total_contract = float(
            self.db.query(func.coalesce(func.sum(SaleContract.amount), 0)).scalar() or 0
        )

        # 已收款总额
        total_received = float(
            self.db.query(func.coalesce(func.sum(SaleContract.received_amount), 0)).scalar() or 0
        )

        # 未收款总额
        total_unreceived = float(
            self.db.query(func.coalesce(func.sum(SaleContract.unreceived_amount), 0)).scalar() or 0
        )

        # 采购成本 = 采购订单总额 + 采购合同未付
        purchase_order_total = float(
            self.db.query(func.coalesce(func.sum(PurchaseOrder.amount), 0)).scalar() or 0
        )
        purchase_contract_total = float(
            self.db.query(func.coalesce(func.sum(PurchaseContract.amount), 0)).scalar() or 0
        )
        # 取采购订单和采购合同中金额大的作为采购成本基准
        purchase_cost = max(purchase_order_total, purchase_contract_total)

        # 人工成本
        labor_cost = float(
            self.db.query(func.coalesce(func.sum(LarborCost.net_salary), 0)).scalar() or 0
        )

        # 行政费用
        office_cost = float(
            self.db.query(func.coalesce(func.sum(OfficeExpense.billing_amount), 0)).scalar() or 0
        )

        # 税费
        tax_cost = float(
            self.db.query(func.coalesce(func.sum(TaxExpense.tax_amount), 0)).scalar() or 0
        )

        # 物流费用
        logistics_cost = float(
            self.db.query(func.coalesce(func.sum(Logistics.amount), 0)).scalar() or 0
        )

        # 总成本
        total_cost = purchase_cost + labor_cost + office_cost + tax_cost + logistics_cost

        # 估算利润 = 合同总额 - 总成本
        estimated_profit = total_contract - total_cost

        # 利润率
        profit_rate = round(estimated_profit / total_contract * 100, 1) if total_contract > 0 else 0.0

        return {
            "total_contract": round(total_contract, 2),
            "purchase_cost": round(purchase_cost, 2),
            "labor_cost": round(labor_cost, 2),
            "office_cost": round(office_cost, 2),
            "tax_cost": round(tax_cost, 2),
            "logistics_cost": round(logistics_cost, 2),
            "total_cost": round(total_cost, 2),
            "estimated_profit": round(estimated_profit, 2),
            "profit_rate": profit_rate,
            "total_received": round(total_received, 2),
            "total_unreceived": round(total_unreceived, 2),
            "level": "danger" if estimated_profit < 0 else ("warning" if profit_rate < 10 else "safe"),
        }

    # ─────────────────── ② 成本费用结构占比 ───────────────────
    def _calc_cost_structure(self) -> dict:
        """计算成本费用结构占比数据，供前端绘制饼图/环形图"""
        # 采购成本
        purchase_order_total = float(
            self.db.query(func.coalesce(func.sum(PurchaseOrder.amount), 0)).scalar() or 0
        )
        purchase_contract_total = float(
            self.db.query(func.coalesce(func.sum(PurchaseContract.amount), 0)).scalar() or 0
        )
        purchase_cost = max(purchase_order_total, purchase_contract_total)

        # 人工成本
        labor_cost = float(
            self.db.query(func.coalesce(func.sum(LarborCost.net_salary), 0)).scalar() or 0
        )

        # 行政费用
        office_cost = float(
            self.db.query(func.coalesce(func.sum(OfficeExpense.billing_amount), 0)).scalar() or 0
        )

        # 税费
        tax_cost = float(
            self.db.query(func.coalesce(func.sum(TaxExpense.tax_amount), 0)).scalar() or 0
        )

        # 物流费用
        logistics_cost = float(
            self.db.query(func.coalesce(func.sum(Logistics.amount), 0)).scalar() or 0
        )

        total_cost = purchase_cost + labor_cost + office_cost + tax_cost + logistics_cost

        def _pct(val):
            return round(val / total_cost * 100, 1) if total_cost > 0 else 0.0

        # 采购成本拆解（按供应商）
        purchase_by_supplier = defaultdict(float)
        orders = self.db.query(PurchaseOrder).filter(PurchaseOrder.amount > 0).all()
        for o in orders:
            name = o.supplier or "未知供应商"
            purchase_by_supplier[name] += float(o.amount or 0)

        # 如果没有采购订单数据，用采购合同
        if not orders:
            pcs = self.db.query(PurchaseContract).filter(PurchaseContract.amount > 0).all()
            for pc in pcs:
                name = pc.supplier_name or "未知供应商"
                purchase_by_supplier[name] += float(pc.amount or 0)

        return {
            "total_cost": round(total_cost, 2),
            "categories": [
                {
                    "name": "采购成本",
                    "value": round(purchase_cost, 2),
                    "percent": _pct(purchase_cost),
                    "color": "#3b82f6",
                    "breakdown": [
                        {"name": k, "value": round(v, 2)}
                        for k, v in sorted(purchase_by_supplier.items(), key=lambda x: x[1], reverse=True)
                    ],
                },
                {
                    "name": "人工成本",
                    "value": round(labor_cost, 2),
                    "percent": _pct(labor_cost),
                    "color": "#f59e0b",
                },
                {
                    "name": "行政费用",
                    "value": round(office_cost, 2),
                    "percent": _pct(office_cost),
                    "color": "#10b981",
                },
                {
                    "name": "税费",
                    "value": round(tax_cost, 2),
                    "percent": _pct(tax_cost),
                    "color": "#8b5cf6",
                },
                {
                    "name": "物流费用",
                    "value": round(logistics_cost, 2),
                    "percent": _pct(logistics_cost),
                    "color": "#ec4899",
                },
            ],
        }

    # ─────────────────── ③ 项目回款进度条 ───────────────────
    def _calc_project_payments(self) -> dict:
        """按客户/合同计算回款进度，供前端绘制进度条"""
        sales = (
            self.db.query(SaleContract)
            .filter(SaleContract.amount > 0)
            .order_by(SaleContract.unreceived_amount.desc())
            .all()
        )

        projects = []
        total_contract = 0.0
        total_received = 0.0
        total_unreceived = 0.0

        for s in sales:
            amount = float(s.amount or 0)
            received = float(s.received_amount or 0)
            unreceived = float(s.unreceived_amount or 0)
            pct = round(received / amount * 100, 1) if amount > 0 else 0.0

            total_contract += amount
            total_received += received
            total_unreceived += unreceived

            # 回款状态标签
            if pct >= 100:
                status = "已结清"
                status_color = "green"
            elif pct >= 60:
                status = "回款中"
                status_color = "blue"
            elif pct > 0:
                status = "待催收"
                status_color = "orange"
            else:
                status = "未回款"
                status_color = "red"

            projects.append({
                "contract_code": s.code or "",
                "contract_name": s.name or "",
                "customer_name": s.customer_name or "未知客户",
                "total_amount": round(amount, 2),
                "received": round(received, 2),
                "unreceived": round(unreceived, 2),
                "progress_pct": pct,
                "status": status,
                "status_color": status_color,
                "sign_date": s.sign_date.isoformat() if s.sign_date else "",
                "expected_received_date": s.expected_received_date.isoformat() if s.expected_received_date else "",
                "customer_manager": s.customer_manager or "",
            })

        overall_pct = round(total_received / total_contract * 100, 1) if total_contract > 0 else 0.0

        return {
            "overall": {
                "total_contract": round(total_contract, 2),
                "total_received": round(total_received, 2),
                "total_unreceived": round(total_unreceived, 2),
                "progress_pct": overall_pct,
            },
            "projects": projects,
        }
