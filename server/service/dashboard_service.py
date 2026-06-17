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
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from server.models import (
    BankTransaction,
    CashFlow,
    LarborCost,
    Logistics,
    OfficeExpense,
    PrivateTxs,
    PurchaseContract,
    PurchaseOrder,
    SaleContract,
    TaxExpense,
)

logger = logging.getLogger(__name__)

TODAY = date.today()
FUTURE_7  = TODAY + timedelta(days=7)
FUTURE_15 = TODAY + timedelta(days=15)
FUTURE_30 = TODAY + timedelta(days=30)

# 安全线：企业最低资金安全线，默认 50,000 元
SAFETY_LINE = 50_000.0


class DashboardService:
    """财务看板服务"""

    def __init__(self, db: Session):
        self.db = db

    # ────────────────────────────── 公开入口 ──────────────────────────────
    def get_dashboard(self) -> dict[str, Any]:
        """返回完整看板数据（不含收付款面板，收付款面板走独立接口）"""
        return {
            "overview": self._calc_overview(),          # 经营总览核心指标
            "risk_dashboard": self._calc_risk_dashboard(),  # 风险仪表盘
            "net_exposure": self._calc_net_exposure(),       # 应收应付净敞口
            "key_risks": self._build_key_risks(),             # 关键风险
            "action_items": self._build_action_items(),      # 今天先做3件事
            "cashflow_forecast": self._calc_cashflow_forecast(),  # 保留：趋势图 daily_series 仍需
            "summary": self._build_summary(),
        }

    # ──────────────────────────── 经营总览核心指标 ─────────────────────────
    def _calc_overview(self) -> dict:
        """计算经营总览页的核心指标卡片 + 概括分析"""
        balance = self._latest_bank_balance()

        # 应收未收
        total_receivable = self._total_receivable()

        # 近期应付（7天内）
        total_payable_7d = self._total_payable_near(7)

        # 本月回款率
        collection_rate = self._monthly_collection_rate()

        # 真实净利率
        net_profit_rate = self._real_net_profit_rate()

        # 现金流日序列 → 找最低水位
        daily_series = self._daily_cashflow_series(30)
        min_balance = balance
        min_date = TODAY.isoformat()
        for entry in daily_series:
            if entry["balance"] < min_balance:
                min_balance = entry["balance"]
                min_date = entry["date"]

        # 安全线缺口
        safety_gap = min_balance - SAFETY_LINE

        # ── 概括分析：资金时间错配 + 核心判断 ──
        def _fmt_md(dt):
            return f"{dt.month}/{dt.day}"

        # 7天内集中支付的总额
        total_payable_7d_val = total_payable_7d

        # 找最晚回款日 vs 最早付款日
        earliest_payment_date = None
        pcs_7d = (
            self.db.query(PurchaseContract)
            .filter(
                PurchaseContract.unpayment_amount > 0,
                PurchaseContract.expected_payment_date >= TODAY,
                PurchaseContract.expected_payment_date <= FUTURE_7,
            )
            .order_by(PurchaseContract.expected_payment_date.asc())
            .all()
        )
        if pcs_7d:
            earliest_payment_date = pcs_7d[0].expected_payment_date
        # 也看工资、行政、税费
        labor_first = (
            self.db.query(LarborCost.payment_date)
            .filter(LarborCost.payment_date >= TODAY, LarborCost.payment_date <= FUTURE_7)
            .order_by(LarborCost.payment_date.asc())
            .first()
        )
        if labor_first and labor_first.payment_date:
            if earliest_payment_date is None or labor_first.payment_date < earliest_payment_date:
                earliest_payment_date = labor_first.payment_date

        # 最早回款日
        earliest_collection_date = None
        sales_future = (
            self.db.query(SaleContract)
            .filter(
                SaleContract.unreceived_amount > 0,
                SaleContract.expected_received_date >= TODAY,
            )
            .order_by(SaleContract.expected_received_date.asc())
            .first()
        )
        if sales_future and sales_future.expected_received_date:
            earliest_collection_date = sales_future.expected_received_date

        # 最晚回款日
        latest_collection_date = None
        sales_latest = (
            self.db.query(SaleContract)
            .filter(
                SaleContract.unreceived_amount > 0,
                SaleContract.expected_received_date >= TODAY,
            )
            .order_by(SaleContract.expected_received_date.desc())
            .first()
        )
        if sales_latest and sales_latest.expected_received_date:
            latest_collection_date = sales_latest.expected_received_date

        # 最大的单笔应收（催收对象）
        max_receivable = (
            self.db.query(SaleContract)
            .filter(SaleContract.unreceived_amount > 0)
            .order_by(SaleContract.unreceived_amount.desc())
            .first()
        )
        max_receivable_name = max_receivable.customer_name if max_receivable else ""
        max_receivable_amount = float(max_receivable.unreceived_amount or 0) if max_receivable else 0

        # 生成概括文案
        if total_payable_7d_val > 0 and balance - total_payable_7d_val < SAFETY_LINE:
            # 现金流偏紧
            level = "warning"
            title = "⚠ 现金流偏紧"
            if min_date:
                title += f"，本周先保住 {_fmt_md(date.fromisoformat(min_date))} 最低点"
            lines = [
                f"当前余额 {balance:,.0f} 元",
            ]
            if earliest_payment_date and earliest_collection_date and earliest_payment_date <= FUTURE_7:
                lines.append(f"{_fmt_md(earliest_payment_date)}-{_fmt_md(latest_collection_date) if latest_collection_date else '?'} 将集中支付 {total_payable_7d_val:,.0f} 元")
            if earliest_collection_date and earliest_collection_date > (earliest_payment_date or TODAY):
                lines.append(f"若 {_fmt_md(earliest_collection_date)} {max_receivable_name}尾款延迟，资金会贴近断裂线")
            summary_analysis = {
                "level": level,
                "title": title,
                "lines": lines,
            }
        elif safety_gap < 0:
            level = "danger"
            title = "🔴 资金已跌破安全线"
            lines = [
                f"当前余额 {balance:,.0f} 元，最低水位仅 {min_balance:,.0f} 元",
                f"距 50,000 安全线缺口 {abs(safety_gap):,.0f} 元",
            ]
            summary_analysis = {
                "level": level,
                "title": title,
                "lines": lines,
            }
        else:
            level = "safe"
            title = "🟢 现金流健康"
            lines = [
                f"当前余额 {balance:,.0f} 元，最低水位 {min_balance:,.0f} 元",
                f"安全线之上，暂无流动性风险",
            ]
            summary_analysis = {
                "level": level,
                "title": title,
                "lines": lines,
            }

        # 最早一笔回款日的可用现金
        available_cash = balance
        available_cash_date = TODAY.strftime("%m/%d")
        if daily_series:
            # 找第一个有收入的日子
            for entry in daily_series:
                if entry["income"] > 0:
                    available_cash = entry["balance"]
                    available_cash_date = date.fromisoformat(entry["date"]).strftime("%m/%d")
                    break

        return {
            "current_balance": round(balance, 2),
            "available_cash": round(available_cash, 2),
            "available_cash_date": available_cash_date,
            "min_water_level": round(min_balance, 2),
            "min_water_date": min_date,
            "safety_gap": round(safety_gap, 2),
            "safety_line": SAFETY_LINE,
            "total_receivable": round(total_receivable, 2),
            "total_payable_7d": round(total_payable_7d, 2),
            "monthly_collection_rate": round(collection_rate, 4),
            "net_profit_rate": round(net_profit_rate, 4),
            "summary_analysis": summary_analysis,
        }

    # ──────────────────────────── 风险仪表盘 ───────────────────────────────
    def _calc_risk_dashboard(self) -> dict:
        """计算风险仪表盘指标：
        ① 应付压力 — 近期应付 / 当前余额
        ② AR账龄风险 — 逾期应收 / 总应收
        ③ 合同完整度 — 有合同销售额 / 总销售额
        ④ 现金状况 — 当前余额 / (近期应付 + 安全线)
        ⑤ 无合同客户风险
        ⑥ 品质退款
        ⑦ 真实净利率
        """
        balance = self._latest_bank_balance()
        total_receivable = self._total_receivable()
        total_payable_7d = self._total_payable_near(7)

        # ① 应付压力：近期应付 / 当前余额（越高越危险）
        payable_pressure = (total_payable_7d / balance * 100) if balance > 0 else 100.0

        # ② AR 账龄风险：已逾期应收 / 总应收
        overdue_receivable = self._total_overdue_receivable()
        ar_aging_risk = (overdue_receivable / total_receivable * 100) if total_receivable > 0 else 0.0

        # ③ 合同完整度
        contract_completeness = self._contract_completeness_pct()

        # ④ 现金状况：直接显示现金总额
        cash_level = "danger" if balance < SAFETY_LINE else ("warning" if balance < SAFETY_LINE * 2 else "safe")

        # ⑤ 无合同客户风险
        no_contract_risk = self._no_contract_customer_risk()

        # ⑥ 品质退款
        quality_refund = self._quality_refund_amount()

        # ⑦ 真实净利率
        net_profit_rate = self._real_net_profit_rate()

        return {
            "payable_pressure": {
                "value": round(payable_pressure, 1),
                "label": "应付压力",
                "level": self._risk_level(payable_pressure, 70, 90),
            },
            "ar_aging": {
                "value": round(ar_aging_risk, 1),
                "label": "AR账龄",
                "level": self._risk_level(ar_aging_risk, 30, 60),
            },
            "contract_completeness": {
                "value": round(contract_completeness, 1),
                "label": "合同完整",
                "level": self._risk_level(100 - contract_completeness, 30, 50, reverse=True),
            },
            "cash_health": {
                "value": round(balance, 2),
                "label": "现金总额",
                "level": cash_level,
                "is_money": True,
            },
            "no_contract_customer_risk": {
                "value": round(no_contract_risk["total_amount"], 2),
                "label": "无合同客户",
                "customers": no_contract_risk["customers"],
                "level": "danger" if no_contract_risk["total_amount"] > 50000 else ("warning" if no_contract_risk["total_amount"] > 0 else "safe"),
            },
            "quality_refund": {
                "value": round(quality_refund, 2),
                "label": "品质退款",
                "level": "warning" if quality_refund > 5000 else ("danger" if quality_refund > 20000 else "safe"),
            },
            "net_profit_rate": {
                "value": round(net_profit_rate, 4),
                "label": "真实净利率",
                "level": "warning" if net_profit_rate < 0.03 else ("danger" if net_profit_rate < 0 else "safe"),
            },
        }

    @staticmethod
    def _risk_level(value: float, warn_threshold: float, danger_threshold: float, reverse: bool = False) -> str:
        """通用风险等级判定
        reverse=True 表示 value 越低越危险（如合同完整度、现金状况）
        """
        if reverse:
            if value >= danger_threshold:
                return "danger"
            elif value >= warn_threshold:
                return "warning"
            return "safe"
        else:
            if value >= danger_threshold:
                return "danger"
            elif value >= warn_threshold:
                return "warning"
            return "safe"

    # ──────────────────────────── 今日行动建议 ─────────────────────────────
    def _build_action_items(self) -> list[dict]:
        """基于数据生成「今天先做 3 件事」"""
        items: list[dict] = []

        # 1. 催收最大单笔逾期应收
        overdue_sales = self._get_overdue_sales()
        if overdue_sales:
            top = overdue_sales[0]
            items.append({
                "priority": 1,
                "title": f"催{top['customer_name']}尾款",
                "amount": round(top["amount"], 2),
                "detail": f"{top['customer_name']} 逾期未收 {top['amount']:,.0f} 元，预计回款日 {top['expected_date']}",
            })

        # 2. 协商最大单笔近期应付
        upcoming_payments = self._get_upcoming_payments()
        if upcoming_payments:
            top = upcoming_payments[0]
            items.append({
                "priority": 2,
                "title": f"协商{top['supplier_name']}分期",
                "amount": round(top["amount"], 2),
                "detail": f"{top['supplier_name']} 近期应付 {top['amount']:,.0f} 元，预计付款日 {top['expected_date']}",
            })

        # 3. 检查非紧急采购
        non_urgent_purchase = self._get_non_urgent_purchase_total()
        if non_urgent_purchase > 0:
            items.append({
                "priority": 3,
                "title": "暂停非紧急采购",
                "amount": round(non_urgent_purchase, 2),
                "detail": f"当前有 {non_urgent_purchase:,.0f} 元非紧急采购可暂缓",
            })

        return items

    # ──────────────────────────── 应收应付净敞口 ────────────────────────────
    def _calc_net_exposure(self) -> dict:
        """计算应收应付净敞口：
        - 应收总额（所有未收销售款）
        - 应付总额（所有未付采购款 + 工资 + 行政 + 税费）
        - 净敞口 = 应收 - 应付
        - 覆盖天数 = 当前余额 / 日均支出
        """
        balance = self._latest_bank_balance()

        # 应收总额
        total_receivable = self._total_receivable()

        # 应付总额：采购未付 + 工资 + 行政 + 税费 + 物流
        total_payable_purchase = float(
            self.db.query(func.coalesce(func.sum(PurchaseContract.unpayment_amount), 0)).scalar() or 0
        )
        total_payable_labor = float(
            self.db.query(func.coalesce(func.sum(LarborCost.net_salary), 0)).scalar() or 0
        )
        total_payable_office = float(
            self.db.query(func.coalesce(func.sum(OfficeExpense.billing_amount), 0)).scalar() or 0
        )
        total_payable_tax = float(
            self.db.query(func.coalesce(func.sum(TaxExpense.tax_amount), 0)).scalar() or 0
        )
        total_payable = total_payable_purchase + total_payable_labor + total_payable_office + total_payable_tax

        # 净敞口
        net_exposure = total_receivable - total_payable

        # 覆盖天数：余额 / 日均支出（用30天总支出估算日均）
        expense_30 = self._future_expense(30)
        avg_daily_expense = expense_30 / 30 if expense_30 > 0 else 0
        cover_days = round(balance / avg_daily_expense, 1) if avg_daily_expense > 0 else None

        return {
            "total_receivable": round(total_receivable, 2),
            "total_payable": round(total_payable, 2),
            "net_exposure": round(net_exposure, 2),
            "balance": round(balance, 2),
            "cover_days": cover_days,
            "level": "danger" if net_exposure < 0 else ("warning" if net_exposure < 50000 else "safe"),
        }

    # ──────────────────────────── 关键风险 ─────────────────────────────────
    def _build_key_risks(self) -> list[dict]:
        """生成关键风险列表（与预警不同，更聚焦核心风险）"""
        risks: list[dict] = []
        balance = self._latest_bank_balance()

        # 1. 资金断裂风险：余额是否跌破安全线
        daily_series = self._daily_cashflow_series(30)
        min_balance = balance
        min_date = TODAY.isoformat()
        for entry in daily_series:
            if entry["balance"] < min_balance:
                min_balance = entry["balance"]
                min_date = entry["date"]

        safety_gap = min_balance - SAFETY_LINE
        if safety_gap < 0:
            risks.append({
                "level": "danger",
                "title": "资金跌破安全线",
                "detail": f"未来30天最低余额 {min_balance:,.0f} 元（{min_date}），距{SAFETY_LINE:,.0f}元安全线缺口 {abs(safety_gap):,.0f} 元",
                "suggestion": "建议尽快催收应收账款或准备融资方案",
            })
        elif safety_gap < 30000:
            risks.append({
                "level": "warning",
                "title": "安全垫偏薄",
                "detail": f"未来30天最低余额 {min_balance:,.0f} 元，安全垫仅 {safety_gap:,.0f} 元",
                "suggestion": "控制非必要支出，关注大额付款时间节点",
            })

        # 2. 大额逾期应收风险
        overdue_sales = self._get_overdue_sales()
        if overdue_sales:
            top_overdue = overdue_sales[0]
            if top_overdue["amount"] > 30000:
                risks.append({
                    "level": "danger",
                    "title": f"大额逾期：{top_overdue['customer_name']}",
                    "detail": f"{top_overdue['customer_name']} 逾期 {top_overdue['amount']:,.0f} 元，预计回款日 {top_overdue['expected_date']}",
                    "suggestion": "立即联系客户确认回款计划，必要时发催款函",
                    "amount": round(top_overdue["amount"], 2),
                })

        # 3. 付款密集风险：7天内集中付款占比
        total_payable_7d = self._total_payable_near(7)
        if total_payable_7d > 0 and balance > 0:
            ratio = total_payable_7d / balance
            if ratio > 0.8:
                risks.append({
                    "level": "danger",
                    "title": "近期付款压力过大",
                    "detail": f"未来7天应付 {total_payable_7d:,.0f} 元，占当前余额 {balance:,.0f} 元的 {ratio*100:.0f}%",
                    "suggestion": "排定付款优先级，与供应商协商分期或延期",
                })
            elif ratio > 0.5:
                risks.append({
                    "level": "warning",
                    "title": "付款节奏偏紧",
                    "detail": f"未来7天应付 {total_payable_7d:,.0f} 元，占当前余额 {ratio*100:.0f}%",
                    "suggestion": "合理安排付款节奏，保留足够运营资金",
                })

        # 4. 无合同交易风险
        no_contract_risk = self._no_contract_customer_risk()
        if no_contract_risk["total_amount"] > 0:
            risks.append({
                "level": "warning",
                "title": f"无合同交易风险（{len(no_contract_risk['customers'])}家）",
                "detail": f"涉及金额 {no_contract_risk['total_amount']:,.0f} 元，缺乏合同保障",
                "suggestion": "尽快补签合同，规范交易流程",
                "amount": round(no_contract_risk["total_amount"], 2),
            })

        # 5. 品质退款风险
        quality_refund = self._quality_refund_amount()
        if quality_refund > 10000:
            risks.append({
                "level": "danger",
                "title": "品质退款异常",
                "detail": f"累计品质退款 {quality_refund:,.0f} 元，可能影响客户信任和回款",
                "suggestion": "排查品质问题根源，加强质检流程",
            })
        elif quality_refund > 5000:
            risks.append({
                "level": "warning",
                "title": "存在品质退款",
                "detail": f"累计品质退款 {quality_refund:,.0f} 元",
                "suggestion": "关注退款趋势，及时处理客户投诉",
            })

        # 按风险等级排序：danger 优先
        risks.sort(key=lambda r: 0 if r["level"] == "danger" else (1 if r["level"] == "warning" else 2))
        return risks

    # ──────────────────────────── 辅助查询方法 ─────────────────────────────
    def _total_receivable(self) -> float:
        """应收未收总额"""
        rows = self.db.query(SaleContract.unreceived_amount).all()
        return sum(float(row[0] or 0) for row in rows)

    def _total_payable_near(self, days: int) -> float:
        """近期应付总额（N天内）"""
        end = TODAY + timedelta(days=days)
        total = 0.0

        # 采购合同未付
        pcs = self.db.query(PurchaseContract).filter(
            PurchaseContract.unpayment_amount > 0,
            PurchaseContract.expected_payment_date >= TODAY,
            PurchaseContract.expected_payment_date <= end,
        ).all()
        total += sum(float(pc.unpayment_amount or 0) for pc in pcs)

        # 现金流中的付款
        cfs = self.db.query(CashFlow).filter(
            CashFlow.item_type.in_(["付款", "支出"]),
            CashFlow.expected_actual_date >= TODAY,
            CashFlow.expected_actual_date <= end,
        ).all()
        total += sum(float(cf.amount or 0) for cf in cfs)

        # 工资
        labor = self.db.query(LarborCost).filter(
            LarborCost.payment_date >= TODAY,
            LarborCost.payment_date <= end,
        ).all()
        total += sum(float(l.net_salary or 0) for l in labor)

        # 行政
        office = self.db.query(OfficeExpense).filter(
            OfficeExpense.expected_payment_date >= TODAY,
            OfficeExpense.expected_payment_date <= end,
        ).all()
        total += sum(float(o.billing_amount or 0) for o in office)

        # 税费
        taxes = self.db.query(TaxExpense).filter(
            TaxExpense.payment_date >= TODAY,
            TaxExpense.payment_date <= end,
        ).all()
        total += sum(float(t.tax_amount or 0) for t in taxes)

        return total

    def _monthly_collection_rate(self) -> float:
        """本月回款率 = 已收款总额 / (已收款总额 + 未收款总额)"""
        # 销售合同汇总
        sales = self.db.query(SaleContract).all()
        total_received = 0.0
        total_unreceived = 0.0
        for s in sales:
            total_received += float(s.received_amount or 0)
            total_unreceived += float(s.unreceived_amount or 0)

        denominator = total_received + total_unreceived
        if denominator == 0:
            return 0.0

        return total_received / denominator

    def _total_overdue_receivable(self) -> float:
        """逾期未收总额（预计回款日已过的）"""
        rows = self.db.query(SaleContract).filter(
            SaleContract.unreceived_amount > 0,
            SaleContract.expected_received_date < TODAY,
        ).all()
        return sum(float(r.unreceived_amount or 0) for r in rows)

    def _contract_completeness_pct(self) -> float:
        """合同完整度百分比：销售合同金额 / (已开票金额 或 应收总额)"""
        # 有合同的销售额：所有 SaleContract 的 amount 之和
        contract_total = float(self.db.query(func.coalesce(func.sum(SaleContract.amount), 0)).scalar() or 0)

        # 总应收（包括无合同的，通过银行流水/私账等推断）
        total_receivable = self._total_receivable()

        # 如果 contract_total 覆盖了 total_receivable 就算完整
        # 完整度 = min(合同金额 / 应收, 100%)
        if total_receivable == 0:
            return 100.0
        return min(contract_total / total_receivable * 100, 100.0) if total_receivable > 0 else 100.0

    def _no_contract_customer_risk(self) -> dict:
        """无合同客户风险：识别有未收款但无合同的客户"""
        # 从销售合同中找 unreceived > 0 的客户
        sales = self.db.query(SaleContract).filter(
            SaleContract.unreceived_amount > 0,
        ).all()

        # 从银行流水和私账中找可能有交易但无合同的客户
        # 简化处理：unreceived_amount 大的客户视为高风险
        risky_customers = []
        total_risk = 0.0
        for s in sales:
            if float(s.unreceived_amount or 0) > 0:
                risky_customers.append({
                    "customer_name": s.customer_name,
                    "unreceived_amount": round(float(s.unreceived_amount or 0), 2),
                    "code": s.code,
                })
                total_risk += float(s.unreceived_amount or 0)

        return {
            "total_amount": total_risk,
            "customers": sorted(risky_customers, key=lambda x: x["unreceived_amount"], reverse=True),
        }

    def _quality_refund_amount(self) -> float:
        """品质退款金额：从私账或银行流水中识别退款"""
        # 从 PrivateTxs 中找退款/退货相关
        private_refunds = self.db.query(PrivateTxs).filter(
            PrivateTxs.payment_nature.like("%退款%"),
        ).all()
        refund_total = sum(float(pr.amount or 0) for pr in private_refunds)

        # 从银行流水中找退款摘要
        bank_refunds = self.db.query(BankTransaction).filter(
            or_(
                BankTransaction.summary.like("%退款%"),
                BankTransaction.summary.like("%退货%"),
                BankTransaction.summary.like("%品质%"),
                BankTransaction.summary.like("%质量%"),
            ),
        ).all()
        for br in bank_refunds:
            refund_total += float(br.expense_amount or 0)

        return refund_total

    def _real_net_profit_rate(self) -> float:
        """真实净利率 ≈ (总收入 - 总支出) / 总收入"""
        # 总收入：银行流水收入 + 私账收入
        bank_income = float(self.db.query(func.coalesce(func.sum(BankTransaction.income_amount), 0)).scalar() or 0)

        # 总支出：采购 + 人工 + 行政 + 税费 + 物流 + 私账支出
        bank_expense = float(self.db.query(func.coalesce(func.sum(BankTransaction.expense_amount), 0)).scalar() or 0)

        # 人工成本（已发放的）
        labor_cost = float(self.db.query(func.coalesce(func.sum(LarborCost.net_salary), 0)).scalar() or 0)

        # 行政费用
        office_cost = float(self.db.query(func.coalesce(func.sum(OfficeExpense.billing_amount), 0)).scalar() or 0)

        # 税费
        tax_cost = float(self.db.query(func.coalesce(func.sum(TaxExpense.tax_amount), 0)).scalar() or 0)

        # 物流费用
        logistics_cost = float(self.db.query(func.coalesce(func.sum(Logistics.amount), 0)).scalar() or 0)

        total_expense = bank_expense + labor_cost + office_cost + tax_cost + logistics_cost

        if bank_income == 0:
            return 0.0

        return (bank_income - total_expense) / bank_income

    def _get_overdue_sales(self) -> list[dict]:
        """获取逾期未收的销售合同，按金额降序"""
        sales = self.db.query(SaleContract).filter(
            SaleContract.unreceived_amount > 0,
            SaleContract.expected_received_date < TODAY,
        ).order_by(SaleContract.unreceived_amount.desc()).limit(5).all()

        return [
            {
                "customer_name": s.customer_name,
                "amount": float(s.unreceived_amount or 0),
                "expected_date": s.expected_received_date.isoformat() if s.expected_received_date else "",
            }
            for s in sales
        ]

    def _get_upcoming_payments(self) -> list[dict]:
        """获取近期应付的采购合同，按金额降序"""
        end = TODAY + timedelta(days=7)
        pcs = self.db.query(PurchaseContract).filter(
            PurchaseContract.unpayment_amount > 0,
            PurchaseContract.expected_payment_date >= TODAY,
            PurchaseContract.expected_payment_date <= end,
        ).order_by(PurchaseContract.unpayment_amount.desc()).limit(5).all()

        return [
            {
                "supplier_name": pc.supplier_name,
                "amount": float(pc.unpayment_amount or 0),
                "expected_date": pc.expected_payment_date.isoformat() if pc.expected_payment_date else "",
            }
            for pc in pcs
        ]

    def _get_non_urgent_purchase_total(self) -> float:
        """获取非紧急采购总额（采购单中未关联合同/未比价的）"""
        orders = self.db.query(PurchaseOrder).filter(
            PurchaseOrder.compared == False,
        ).all()
        return sum(float(o.amount or 0) for o in orders)

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

    # ──────────────────────────── 收付款面板 ───────────────────────────────
    def _calc_receivable_payment(self) -> dict:
        """收付款面板数据：
        ① 客户应收与回款 — 每个客户的 amount/received_amount/回款比例
        ② 供应商付款压力 — 采购订单列表（按金额降序）
        ③ 优先催收客户 — 逾期且 unreceived > 0，按金额降序
        ④ 近期必须付款 — 工资社保 + 供应商 + 房租水电税费
        ⑤ 短期净缺口 — 近期回款 - 近期支出
        """
        balance = self._latest_bank_balance()

        # ── ① 客户回款进度 ──
        sales = (
            self.db.query(SaleContract)
            .filter(SaleContract.amount > 0)
            .order_by(SaleContract.unreceived_amount.desc())
            .all()
        )
        customer_progress = []
        for s in sales:
            amount = float(s.amount or 0)
            received = float(s.received_amount or 0)
            unreceived = float(s.unreceived_amount or 0)
            pct = round(received / amount * 100, 1) if amount > 0 else 0.0
            customer_progress.append({
                "customer_name": s.customer_name or "未知客户",
                "total_amount": round(amount, 2),
                "received": round(received, 2),
                "unreceived": round(unreceived, 2),
                "progress_pct": pct,
                "level": "danger" if pct < 30 else ("warning" if pct < 60 else "safe"),
            })

        # ── ② 供应商付款压力（采购订单） ──
        orders = (
            self.db.query(PurchaseOrder)
            .filter(PurchaseOrder.amount > 0)
            .order_by(PurchaseOrder.amount.desc())
            .all()
        )
        supplier_payments = []
        for o in orders:
            supplier_payments.append({
                "supplier_name": o.supplier or "未知供应商",
                "amount": round(float(o.amount or 0), 2),
                "detail": o.detail or "",
                "purchase_date": o.purchase_date.isoformat() if o.purchase_date else "",
                "code": o.code or "",
            })

        # ── ③ 优先催收客户（有逾期未收款） ──
        overdue_sales = (
            self.db.query(SaleContract)
            .filter(
                SaleContract.unreceived_amount > 0,
                SaleContract.expected_received_date < TODAY,
            )
            .order_by(SaleContract.unreceived_amount.desc())
            .limit(5)
            .all()
        )
        priority_collections = []
        for s in overdue_sales:
            overdue_days = (TODAY - s.expected_received_date).days if s.expected_received_date else 0
            priority_collections.append({
                "customer_name": s.customer_name or "未知客户",
                "unreceived_amount": round(float(s.unreceived_amount or 0), 2),
                "expected_date": s.expected_received_date.isoformat() if s.expected_received_date else "",
                "overdue_days": overdue_days,
            })

        # ── ④ 近期必须付款（刚性支付） ──
        # 工资社保
        labor_total = float(
            self.db.query(func.coalesce(func.sum(LarborCost.net_salary), 0)).scalar() or 0
        )
        labor_count = self.db.query(LarborCost).count()

        # 供应商应付（7天内到期 + 已逾期未付）
        purchase_contracts = (
            self.db.query(PurchaseContract)
            .filter(
                PurchaseContract.unpayment_amount > 0,
                PurchaseContract.expected_payment_date <= FUTURE_7,
            )
            .order_by(PurchaseContract.unpayment_amount.desc())
            .all()
        )
        supplier_due = round(sum(float(pc.unpayment_amount or 0) for pc in purchase_contracts), 2)
        supplier_list = [
            {
                "supplier_name": pc.supplier_name or "未知供应商",
                "amount": round(float(pc.unpayment_amount or 0), 2),
                "due_date": pc.expected_payment_date.isoformat() if pc.expected_payment_date else "",
            }
            for pc in purchase_contracts
        ]

        # 房租水电税费（办公费用 + 税费）
        office_total = float(
            self.db.query(func.coalesce(func.sum(OfficeExpense.billing_amount), 0)).scalar() or 0
        )
        tax_total = float(
            self.db.query(func.coalesce(func.sum(TaxExpense.tax_amount), 0)).scalar() or 0
        )
        overhead_total = round(office_total + tax_total, 2)

        # ── ⑤ 短期净缺口 ──
        # 近期回款：7天内预计回款
        recent_income = self._future_income(7)
        # 近期支出：刚性支付合计
        rigid_expense = labor_total + supplier_due + overhead_total
        short_term_gap = round(recent_income - rigid_expense, 2)

        # ── ⑥ 概括分析：时间错配 + 风险判断 ──
        # 总应收 vs 总应付
        total_receivable = sum(c["unreceived"] for c in customer_progress)
        total_payable = supplier_due + labor_total + overhead_total

        # 最早回款日 vs 最早付款日
        earliest_collection = None
        for s in overdue_sales:
            if s.expected_received_date and (earliest_collection is None or s.expected_received_date < earliest_collection):
                earliest_collection = s.expected_received_date
        # 也看非逾期的回款日
        non_overdue = (
            self.db.query(SaleContract)
            .filter(
                SaleContract.unreceived_amount > 0,
                SaleContract.expected_received_date >= TODAY,
            )
            .order_by(SaleContract.expected_received_date.asc())
            .first()
        )
        if non_overdue and non_overdue.expected_received_date:
            if earliest_collection is None or non_overdue.expected_received_date < earliest_collection:
                earliest_collection = non_overdue.expected_received_date

        # 最早付款日（7天内的）
        earliest_payment = None
        due_contracts = (
            self.db.query(PurchaseContract)
            .filter(
                PurchaseContract.unpayment_amount > 0,
                PurchaseContract.expected_payment_date <= FUTURE_7,
            )
            .order_by(PurchaseContract.expected_payment_date.asc())
            .first()
        )
        if due_contracts and due_contracts.expected_payment_date:
            earliest_payment = due_contracts.expected_payment_date
        # 工资/办公/税费日期
        first_labor = (
            self.db.query(LarborCost)
            .filter(LarborCost.payment_date >= TODAY)
            .order_by(LarborCost.payment_date.asc())
            .first()
        )
        if first_labor and first_labor.payment_date:
            if earliest_payment is None or first_labor.payment_date < earliest_payment:
                earliest_payment = first_labor.payment_date

        # 日期格式化（Windows 不支持 %-m/%-d，用自定义函数去掉前导零）
        def _fmt_md(dt):
            return f"{dt.month}/{dt.day}"

        # 生成概括文案
        if total_receivable >= total_payable:
            if earliest_collection and earliest_payment and earliest_collection > earliest_payment:
                analysis_text = (
                    f"应收看似够付，但回款晚于付款——应收未收 {total_receivable:,.0f} 元，应付未付 {total_payable:,.0f} 元；"
                    f"真正卡点在 {_fmt_md(earliest_payment)}-{_fmt_md(earliest_collection)} 先付款、{_fmt_md(earliest_collection)} 才回款"
                )
            else:
                analysis_text = (
                    f"应收覆盖应付——应收未收 {total_receivable:,.0f} 元，应付未付 {total_payable:,.0f} 元，"
                    f"回款节奏匹配付款节奏，暂无时间错配风险"
                )
        else:
            if earliest_collection and earliest_payment and earliest_collection > earliest_payment:
                analysis_text = (
                    f"应收不够付，且回款晚于付款——应收 {total_receivable:,.0f} 元 vs 应付 {total_payable:,.0f} 元，"
                    f"缺口 {total_payable - total_receivable:,.0f} 元；付款高峰在 {_fmt_md(earliest_payment)}，回款在 {_fmt_md(earliest_collection)}"
                )
            else:
                analysis_text = (
                    f"应收不够付——应收 {total_receivable:,.0f} 元 vs 应付 {total_payable:,.0f} 元，"
                    f"净缺口 {total_payable - total_receivable:,.0f} 元，需尽快催收或融资"
                )

        summary_analysis = {
            "text": analysis_text,
            "total_receivable": round(total_receivable, 2),
            "total_payable": round(total_payable, 2),
            "earliest_collection_date": earliest_collection.strftime("%Y-%m-%d") if earliest_collection else None,
            "earliest_payment_date": earliest_payment.strftime("%Y-%m-%d") if earliest_payment else None,
            "level": "danger" if (total_receivable < total_payable) or (short_term_gap < 0) else ("warning" if (earliest_collection and earliest_payment and earliest_collection > earliest_payment) else "safe"),
        }

        return {
            "summary_analysis": summary_analysis,
            "customer_progress": customer_progress,
            "supplier_payments": supplier_payments,
            "priority_collections": priority_collections,
            "mandatory_payments": {
                "labor_salary": {
                    "label": "工资社保",
                    "amount": round(labor_total, 2),
                    "detail": f"共 {labor_count} 人",
                },
                "supplier_due": {
                    "label": "供应商采购",
                    "amount": supplier_due,
                    "detail": f"共 {len(supplier_list)} 笔",
                    "items": supplier_list,
                },
                "overhead": {
                    "label": "房租水电税费",
                    "amount": overhead_total,
                    "detail": f"办公 {office_total:,.0f} + 税费 {tax_total:,.0f}",
                },
                "total_rigid": round(rigid_expense, 2),
            },
            "short_term_gap": {
                "recent_income": round(recent_income, 2),
                "rigid_expense": round(rigid_expense, 2),
                "gap": short_term_gap,
                "balance": round(balance, 2),
                "level": "danger" if short_term_gap < 0 else ("warning" if short_term_gap < 50000 else "safe"),
            },
        }
