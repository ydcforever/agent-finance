"""
财务看板数据服务 —— 基于已入库的 Excel 数据，计算 KPI 卡片 + 现金流趋势 + AI 预警。

用法:
    from server.service.dashboard_service import DashboardService
    svc = DashboardService(db)
    data = svc.get_dashboard()  # -> dict
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from server.models import (
    BankTransaction,
    CashFlow,
    LarborCost,
    OfficeExpense,
    PurchaseContract,
    SaleContract,
    TaxExpense,
)

logger = logging.getLogger(__name__)

TODAY = date.today()
FUTURE_7  = TODAY + timedelta(days=7)
FUTURE_15 = TODAY + timedelta(days=15)
FUTURE_30 = TODAY + timedelta(days=30)


class DashboardService:
    """财务看板服务"""

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────── 公开入口 ──────────────────────────────
    def get_dashboard(self) -> dict[str, Any]:
        """返回完整看板数据"""
        return {
            "kpi_cards": self._calc_kpi_cards(),
            "cashflow_forecast": self._calc_cashflow_forecast(),
            "alerts": self._build_alerts(),
            "summary": self._build_summary(),
        }

    # ──────────────────────────── KPI 卡片 ────────────────────────────────
    def _calc_kpi_cards(self) -> dict:
        """计算 4 个核心 KPI 卡片

        ① 当前账面余额 — 取最近一条银行流水的 balance
        ② 未来 30 天预计回款 — 未收 + 预期收入
        ③ 未来 30 天预计支出 — 未付 + 预期支出（工资/行政/税费/采购）
        ④ 资金缺口 / 安全垫 — 回款 - 支出（正=安全垫，负=缺口）
        """
        balance = self._latest_bank_balance()
        income_30 = self._future_income(30)
        expense_30 = self._future_expense(30)
        gap = income_30 - expense_30

        return {
            "current_balance": {
                "value": round(balance, 2),
                "label": "当前账面余额",
                "trend": "up" if balance > 0 else "down",
            },
            "expected_income_30d": {
                "value": round(income_30, 2),
                "label": "未来30天预计回款",
                "breakdown": self._income_breakdown(30),
            },
            "expected_expense_30d": {
                "value": round(expense_30, 2),
                "label": "未来30天预计支出",
                "breakdown": self._expense_breakdown(30),
            },
            "funding_gap": {
                "value": round(gap, 2),
                "label": "资金缺口" if gap < 0 else "资金安全垫",
                "level": "danger" if gap < 0 else ("warning" if gap < 50000 else "safe"),
            },
        }

    def _latest_bank_balance(self) -> float:
        row = (
            self.db.query(BankTransaction.balance)
            .order_by(BankTransaction.transaction_date.desc())
            .first()
        )
        return float(row.balance) if row and row.balance else 0.0

    def _future_income(self, days: int) -> float:
        """未来 N 天预计回款总额"""
        end = TODAY + timedelta(days=days)
        total = 0.0

        # 销售合同：未收款 + 预计回款日在未来 N 天内的
        sales: list[SaleContract] = (
            self.db.query(SaleContract)
            .filter(
                or_(
                    SaleContract.unreceived_amount > 0,
                    SaleContract.expected_received_date.between(TODAY, end),
                )
            )
            .all()
        )
        for s in sales:
            # 未收款部分
            total += float(s.unreceived_amount or 0)
            # 如果预计回款日在范围内且已收完，加已收（实际上 unreceived 已经覆盖）
            # 这里用 unreceived_amount 即可

        # 现金流表中 item_type=回款 且日期在范围内的
        cash_flows: list[CashFlow] = (
            self.db.query(CashFlow)
            .filter(
                CashFlow.item_type.in_(["回款", "收入"]),
                CashFlow.expected_actual_date >= TODAY,
                CashFlow.expected_actual_date <= end,
            )
            .all()
        )
        for cf in cash_flows:
            total += float(cf.amount or 0)

        return total

    def _future_expense(self, days: int) -> float:
        """未来 N 天预计支出总额"""
        end = TODAY + timedelta(days=days)
        total = 0.0

        # 采购合同：未付款
        pcs: list[PurchaseContract] = (
            self.db.query(PurchaseContract)
            .filter(
                or_(
                    PurchaseContract.unpayment_amount > 0,
                    PurchaseContract.expected_payment_date.between(TODAY, end),
                )
            )
            .all()
        )
        for pc in pcs:
            total += float(pc.unpayment_amount or 0)

        # 人工成本（工资社保）：预计发放日期在范围内
        labor: list[LarborCost] = (
            self.db.query(LarborCost)
            .filter(
                LarborCost.payment_date >= TODAY,
                LarborCost.payment_date <= end,
            )
            .all()
        )
        for l in labor:
            total += float(l.net_salary or 0)

        # 行政费用（房租水电）
        office: list[OfficeExpense] = (
            self.db.query(OfficeExpense)
            .filter(
                OfficeExpense.expected_payment_date >= TODAY,
                OfficeExpense.expected_payment_date <= end,
            )
            .all()
        )
        for o in office:
            total += float(o.billing_amount or 0)

        # 税费
        taxes: list[TaxExpense] = (
            self.db.query(TaxExpense)
            .filter(
                TaxExpense.payment_date >= TODAY,
                TaxExpense.payment_date <= end,
            )
            .all()
        )
        for t in taxes:
            total += float(t.tax_amount or 0)

        # 现金流表中 item_type=付款/支出 且日期在范围内的
        cash_flows: list[CashFlow] = (
            self.db.query(CashFlow)
            .filter(
                CashFlow.item_type.in_(["付款", "支出"]),
                CashFlow.expected_actual_date >= TODAY,
                CashFlow.expected_actual_date <= end,
            )
            .all()
        )
        for cf in cash_flows:
            total += float(cf.amount or 0)

        return total

    def _income_breakdown(self, days: int) -> dict:
        """回款来源拆解"""
        end = TODAY + timedelta(days=days)

        # 按客户拆
        by_customer: dict[str, float] = defaultdict(float)
        sales: list[SaleContract] = self.db.query(SaleContract).filter(
            SaleContract.unreceived_amount > 0
        ).all()
        for s in sales:
            by_customer[s.customer_name] += float(s.unreceived_amount or 0)

        # 现金流中的回款
        cash_flows: list[CashFlow] = (
            self.db.query(CashFlow)
            .filter(
                CashFlow.item_type.in_(["回款", "收入"]),
                CashFlow.expected_actual_date >= TODAY,
                CashFlow.expected_actual_date <= end,
            )
            .all()
        )
        for cf in cash_flows:
            by_customer[cf.entity_name or "未知"] += float(cf.amount or 0)

        return {
            "by_customer": dict(
                sorted(by_customer.items(), key=lambda x: x[1], reverse=True)
            )
        }

    def _expense_breakdown(self, days: int) -> dict:
        """支出类别拆解"""
        end = TODAY + timedelta(days=days)
        result: dict[str, float] = defaultdict(float)

        # 采购未付
        pcs = self.db.query(PurchaseContract).filter(PurchaseContract.unpayment_amount > 0).all()
        for pc in pcs:
            result["采购应付款"] += float(pc.unpayment_amount or 0)

        # 工资
        labor = self.db.query(LarborCost).filter(
            LarborCost.payment_date >= TODAY, LarborCost.payment_date <= end
        ).all()
        for l in labor:
            result["工资社保"] += float(l.net_salary or 0)

        # 行政
        office = self.db.query(OfficeExpense).filter(
            OfficeExpense.expected_payment_date >= TODAY,
            OfficeExpense.expected_payment_date <= end,
        ).all()
        for o in office:
            result["房租水电"] += float(o.billing_amount or 0)

        # 税费
        taxes = self.db.query(TaxExpense).filter(
            TaxExpense.payment_date >= TODAY, TaxExpense.payment_date <= end
        ).all()
        for t in taxes:
            result["税费"] += float(t.tax_amount or 0)

        return {"by_category": dict(sorted(result.items(), key=lambda x: x[1], reverse=True))}

    # ──────────────────────── 现金流趋势推演 ──────────────────────────────
    def _calc_cashflow_forecast(self) -> dict:
        """7天 / 15天 / 30天 三级现金流推演"""
        return {
            "perspectives": [
                self._forecast_perspective(7,  "7天视角",  "短期流动性"),
                self._forecast_perspective(15, "15天视角", "中期资金调度"),
                self._forecast_perspective(30, "30天视角", "长期资金规划"),
            ],
            "daily_series": self._daily_cashflow_series(30),
        }

    def _forecast_perspective(self, days: int, title: str, desc: str) -> dict:
        """单视角现金流推演"""
        balance = self._latest_bank_balance()
        income = self._future_income(days)
        expense = self._future_expense(days)
        net = income - expense
        end_balance = balance + net

        return {
            "title": title,
            "description": desc,
            "start_balance": round(balance, 2),
            "total_income": round(income, 2),
            "total_expense": round(expense, 2),
            "net_change": round(net, 2),
            "end_balance": round(end_balance, 2),
            "health": (
                "healthy" if end_balance > 100000
                else "warning" if end_balance > 0
                else "danger"
            ),
        }

    def _daily_cashflow_series(self, days: int) -> list[dict]:
        """按日汇总未来 N 天的收入/支出/余额变化，供前端绘制趋势图"""
        end = TODAY + timedelta(days=days)
        series: dict[str, dict] = defaultdict(
            lambda: {"date": "", "income": 0.0, "expense": 0.0}
        )

        # 销售合同回款
        sales = (
            self.db.query(SaleContract)
            .filter(
                SaleContract.expected_received_date >= TODAY,
                SaleContract.expected_received_date <= end,
                SaleContract.unreceived_amount > 0,
            )
            .all()
        )
        for s in sales:
            key = s.expected_received_date.isoformat() if s.expected_received_date else ""
            if key:
                series[key]["date"] = key
                series[key]["income"] += float(s.unreceived_amount or 0)

        # 现金流
        cfs = (
            self.db.query(CashFlow)
            .filter(
                CashFlow.expected_actual_date >= TODAY,
                CashFlow.expected_actual_date <= end,
            )
            .all()
        )
        for cf in cfs:
            key = cf.expected_actual_date.isoformat() if cf.expected_actual_date else ""
            if not key:
                continue
            series[key]["date"] = key
            if cf.item_type in ("回款", "收入"):
                series[key]["income"] += float(cf.amount or 0)
            else:
                series[key]["expense"] += float(cf.amount or 0)

        # 采购合同付款
        pcs = (
            self.db.query(PurchaseContract)
            .filter(
                PurchaseContract.expected_payment_date >= TODAY,
                PurchaseContract.expected_payment_date <= end,
                PurchaseContract.unpayment_amount > 0,
            )
            .all()
        )
        for pc in pcs:
            key = pc.expected_payment_date.isoformat() if pc.expected_payment_date else ""
            if key:
                series[key]["date"] = key
                series[key]["expense"] += float(pc.unpayment_amount or 0)

        # 工资
        labor = (
            self.db.query(LarborCost)
            .filter(
                LarborCost.payment_date >= TODAY,
                LarborCost.payment_date <= end,
            )
            .all()
        )
        for l in labor:
            key = l.payment_date.isoformat() if l.payment_date else ""
            if key:
                series[key]["date"] = key
                series[key]["expense"] += float(l.net_salary or 0)

        # 行政
        office = (
            self.db.query(OfficeExpense)
            .filter(
                OfficeExpense.expected_payment_date >= TODAY,
                OfficeExpense.expected_payment_date <= end,
            )
            .all()
        )
        for o in office:
            key = o.expected_payment_date.isoformat() if o.expected_payment_date else ""
            if key:
                series[key]["date"] = key
                series[key]["expense"] += float(o.billing_amount or 0)

        # 税费
        taxes = (
            self.db.query(TaxExpense)
            .filter(
                TaxExpense.payment_date >= TODAY,
                TaxExpense.payment_date <= end,
            )
            .all()
        )
        for t in taxes:
            key = t.payment_date.isoformat() if t.payment_date else ""
            if key:
                series[key]["date"] = key
                series[key]["expense"] += float(t.tax_amount or 0)

        # 按日期排序，累加余额
        sorted_dates = sorted(series.keys())
        running_balance = self._latest_bank_balance()
        result = []
        for d in sorted_dates:
            entry = series[d]
            net = entry["income"] - entry["expense"]
            running_balance += net
            result.append({
                "date": d,
                "income": round(entry["income"], 2),
                "expense": round(entry["expense"], 2),
                "net": round(net, 2),
                "balance": round(running_balance, 2),
            })
        return result

    # ──────────────────────────── 预警建议 ────────────────────────────────
    def _build_alerts(self) -> list[dict]:
        """基于数据规则生成预警"""
        alerts: list[dict] = []

        balance = self._latest_bank_balance()
        income_30 = self._future_income(30)
        expense_30 = self._future_expense(30)

        # 1. 资金缺口预警
        gap = income_30 - expense_30
        if gap < 0:
            alerts.append({
                "level": "danger",
                "title": "资金缺口预警",
                "detail": f"未来30天预计回款 {income_30:,.0f} 元，预计支出 {expense_30:,.0f} 元，"
                           f"资金缺口 {abs(gap):,.0f} 元",
                "suggestion": "建议加快应收账款催收，或与供应商协商延期付款",
            })
        elif gap < 50000:
            alerts.append({
                "level": "warning",
                "title": "资金安全垫偏薄",
                "detail": f"未来30天净流入仅 {gap:,.0f} 元，安全垫较薄",
                "suggestion": "建议控制不必要的支出，确保流动性充足",
            })

        # 2. 应收账款预警（长期未收）
        overdue_sales: list[SaleContract] = (
            self.db.query(SaleContract)
            .filter(
                SaleContract.unreceived_amount > 0,
                SaleContract.expected_received_date < TODAY,
            )
            .all()
        )
        if overdue_sales:
            total_overdue = sum(float(s.unreceived_amount or 0) for s in overdue_sales)
            clients = ", ".join(s.customer_name for s in overdue_sales[:3])
            if len(overdue_sales) > 3:
                clients += f" 等{len(overdue_sales)}家"
            alerts.append({
                "level": "danger",
                "title": "应收账款逾期",
                "detail": f"{clients} 合计 {total_overdue:,.0f} 元已过预计回款日",
                "suggestion": "建议立即联系客户确认回款计划，必要时发送催款函",
            })

        # 3. 应付账款密集预警
        upcoming_payments: list[PurchaseContract] = (
            self.db.query(PurchaseContract)
            .filter(
                PurchaseContract.unpayment_amount > 0,
                PurchaseContract.expected_payment_date >= TODAY,
                PurchaseContract.expected_payment_date <= FUTURE_7,
            )
            .all()
        )
        if upcoming_payments:
            total = sum(float(pc.unpayment_amount or 0) for pc in upcoming_payments)
            if total > balance * 0.8:
                alerts.append({
                    "level": "warning",
                    "title": "近期付款压力大",
                    "detail": f"未来7天应付 {total:,.0f} 元，占当前账面余额 {balance/total*100:.0f}%",
                    "suggestion": "建议排定付款优先级，优先保障关键供应商",
                })

        # 4. 现金流紧张预警
        if balance < expense_30:
            alerts.append({
                "level": "warning",
                "title": "现金流可能不足",
                "detail": f"当前余额 {balance:,.0f} 元不足以覆盖未来30天预计支出 {expense_30:,.0f} 元",
                "suggestion": "建议提前准备融资方案或压缩非必要开支",
            })

        return alerts

    # ──────────────────────────── 数据汇总 ────────────────────────────────
    def _build_summary(self) -> dict:
        """全局汇总"""
        # 应收账款
        total_receivable = sum(
            float(row[0] or 0)
            for row in self.db.query(SaleContract.unreceived_amount).all()
        )

        total_payable = sum(
            float(row[0] or 0)
            for row in self.db.query(PurchaseContract.unpayment_amount).all()
        )

        return {
            "total_receivable": round(total_receivable, 2),
            "total_payable": round(total_payable, 2),
            "current_balance": round(self._latest_bank_balance(), 2),
            "data_refresh_time": TODAY.isoformat(),
        }
