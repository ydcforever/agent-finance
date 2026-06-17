"""
Excel 解析工具 - 将 financial_data.xlsx 各 sheet 解析为对应的 Model 对象列表。

用法:
    from server.service.excel_parser import ExcelParser
    parser = ExcelParser("path/to/financial_data.xlsx")
    result = parser.parse_all()  # -> dict[str, list]
    
    # 或单独解析
    purchase_orders = parser.parse_purchase_orders()
"""

import re
from datetime import date, datetime
from typing import Any, Optional

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from server.models import (
    PurchaseOrder,
    SaleContract,
    PurchaseContract,
    ProjectProgress,
    Logistics,
    LarborCost,
    OfficeExpense,
    TaxExpense,
    CashFlow,
    BankTransaction,
)


# ---------------------------------------------------------------------------
# 通用工具函数
# ---------------------------------------------------------------------------

def _parse_date(value: Any) -> Optional[date]:
    """将 Excel 单元格值解析为 date 对象。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # 尝试字符串解析
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(value: Any) -> float:
    """解析为 float，None 或空字符串返回 0.0。"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "")
    if s == "" or s == "-":
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_str(value: Any) -> str:
    """解析为字符串，None 返回空字符串。"""
    if value is None:
        return ""
    return str(value).strip()


def _parse_bool(value: Any) -> bool:
    """解析布尔值。"""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    s = str(value).strip()
    return s in ("是", "true", "True", "1", "yes", "Yes")


def _get_data_rows(ws: Worksheet, header_row: int = 6) -> list[list]:
    """从指定 header 行之后读取所有非空数据行。"""
    rows = []
    for r in range(header_row + 1, ws.max_row + 1):
        row_vals = [c.value for c in ws[r]]
        if all(v is None for v in row_vals):
            continue
        rows.append(row_vals)
    return rows


# ---------------------------------------------------------------------------
# 解析器
# ---------------------------------------------------------------------------

class ExcelParser:
    """Excel 数据解析器。

    Args:
        filepath: Excel 文件路径
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._wb: Optional[openpyxl.Workbook] = None

    @property
    def wb(self) -> openpyxl.Workbook:
        if self._wb is None:
            self._wb = openpyxl.load_workbook(self.filepath, data_only=True)
        return self._wb

    def close(self):
        if self._wb is not None:
            self._wb.close()
            self._wb = None

    # ------------------------------------------------------------------
    # 01 采购报告 → PurchaseOrder
    # ------------------------------------------------------------------
    def parse_purchase_orders(self) -> list[PurchaseOrder]:
        """解析「01采购报告」→ List[PurchaseOrder]"""
        ws = self.wb["01采购报告"]
        results: list[PurchaseOrder] = []
        for row in _get_data_rows(ws, header_row=6):
            results.append(PurchaseOrder(
                purchase_date=_parse_date(row[0]),
                code=_parse_str(row[1]),
                order_type=_parse_str(row[2]),
                supplier=_parse_str(row[3]),
                detail=_parse_str(row[4]),
                quantity=_parse_float(row[5]),
                price=_parse_float(row[6]),
                amount=_parse_float(row[7]),
                compared=_parse_bool(row[8]),
                project=_parse_str(row[10]),          # 关联项目/客户
                related_party=_parse_str(row[10]),     # 关联方（同 project）
                operator=_parse_str(row[11]),
                remark=_parse_str(row[12]),
            ))
        return results

    # ------------------------------------------------------------------
    # 02 客户合同 → SaleContract
    # ------------------------------------------------------------------
    def parse_sale_contracts(self) -> list[SaleContract]:
        """解析「02客户合同」→ List[SaleContract]"""
        ws = self.wb["02客户合同"]
        results: list[SaleContract] = []
        for row in _get_data_rows(ws, header_row=6):
            results.append(SaleContract(
                sign_date=_parse_date(row[0]),
                customer_name=_parse_str(row[1]),
                code=_parse_str(row[2]),
                name=_parse_str(row[3]),
                amount=_parse_float(row[4]),
                # row[5] 合同期限 → 拆成 effective_date / expire_date
                effective_date=self._parse_contract_start(row[5]) or date(1970, 1, 1),
                expire_date=self._parse_contract_end(row[5]) or date(1970, 1, 1),
                progress=_parse_str(row[6]),
                # row[7] 是否有合同 → 存 remark
                invoice_status=_parse_str(row[9]),
                invoice_amount=_parse_float(row[10]),
                received_amount=_parse_float(row[11]),
                unreceived_amount=_parse_float(row[12]),
                expected_received_date=_parse_date(row[13]),
                customer_manager=_parse_str(row[14]),
                has_chat=_parse_bool(row[8]),   # 是否有聊天记录
                attachments=_parse_str(row[7]),  # 是否有合同
                remark=_parse_str(row[15]),
            ))
        return results

    def _parse_contract_start(self, value: Any) -> Optional[date]:
        s = _parse_str(value)
        if not s:
            return None
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        return _parse_date(m.group(1)) if m else None

    def _parse_contract_end(self, value: Any) -> Optional[date]:
        s = _parse_str(value)
        if not s:
            return None
        m = re.search(r"至\s*(\d{4}-\d{2}-\d{2})", s)
        return _parse_date(m.group(1)) if m else None

    # ------------------------------------------------------------------
    # 03 供应商合同 → PurchaseContract
    # ------------------------------------------------------------------
    def parse_purchase_contracts(self) -> list[PurchaseContract]:
        """解析「03供应商合同」→ List[PurchaseContract]"""
        ws = self.wb["03供应商合同"]
        results: list[PurchaseContract] = []
        for row in _get_data_rows(ws, header_row=6):
            results.append(PurchaseContract(
                sign_date=_parse_date(row[0]),
                supplier_name=_parse_str(row[1]),
                code=_parse_str(row[2]),
                name=_parse_str(row[2]),  # 用合同编号作为名称（Excel 无单独名称列）
                detail=_parse_str(row[3]),
                confirmed=_parse_bool(row[4]) or _parse_str(row[4]) != "",
                amount=_parse_float(row[5]),
                payment_amount=_parse_float(row[6]),
                unpayment_amount=_parse_float(row[7]),
                expected_payment_date=_parse_date(row[8]),
                payment_type=_parse_str(row[9]),
                delivery_status=_parse_str(row[10]),
                operator=_parse_str(row[11]),
                remark=_parse_str(row[12]),
            ))
        return results

    # ------------------------------------------------------------------
    # 04 生产跟进 → ProjectProgress
    # ------------------------------------------------------------------
    def parse_project_progress(self) -> list[ProjectProgress]:
        """解析「04生产跟进」→ List[ProjectProgress]

        Excel 列: 日期, 关联客户/项目, 生产/施工事项, 负责人, 当前状态,
                   预计完成日期, 是否影响回款, 需要补充资料, 备注
        """
        ws = self.wb["04生产跟进"]
        results: list[ProjectProgress] = []
        for row in _get_data_rows(ws, header_row=6):
            results.append(ProjectProgress(
                follow_up_date=_parse_date(row[0]),      # 日期
                related_party=_parse_str(row[1]),         # 关联客户/项目
                construction_task=_parse_str(row[2]),      # 生产/施工事项
                manager=_parse_str(row[3]),                # 负责人
                progress=_parse_str(row[4]),               # 当前状态
                expected_completion_date=_parse_date(row[5]),  # 预计完成日期
                affect_received=_parse_bool(row[6]),       # 是否影响回款
                additional_notes=_parse_str(row[7]),       # 需要补充资料
                remark=_parse_str(row[8]),                 # 备注
            ))
        return results

    # ------------------------------------------------------------------
    # 05 发货物流 → Logistics
    # ------------------------------------------------------------------
    def parse_logistics(self) -> list[Logistics]:
        """解析「05发货物流」→ List[Logistics]

        Excel 列: 发货日期, 关联客户/项目, 物流公司/运输方式, 物流单号,
                   发货内容, 数量, 是否已发货, 签收日期, 物流费用,
                   物流付款状态, 付款日期, 回单附件名称, 备注
        """
        ws = self.wb["05发货物流"]
        results: list[Logistics] = []
        for row in _get_data_rows(ws, header_row=6):
            results.append(Logistics(
                ship_date=_parse_date(row[0]),             # 发货日期
                related_party=_parse_str(row[1]),           # 关联客户/项目
                company=_parse_str(row[2]),                 # 物流公司/运输方式
                tracking_number=_parse_str(row[3]),         # 物流单号
                detail=_parse_str(row[4]),                  # 发货内容
                quantity=_parse_float(row[5]),              # 数量
                shipped_out=_parse_bool(row[6]),            # 是否已发货
                delivery_type=_parse_str(row[7]),           # 签收日期
                amount=_parse_float(row[8]),                # 物流费用
                payment_status=_parse_str(row[9]),          # 物流付款状态
                payment_date=_parse_date(row[10]) or date(1970, 1, 1),  # 付款日期（NOT NULL，空值用默认日期）
                attachment=_parse_str(row[11]),             # 回单附件名称
                remark=_parse_str(row[12]),                 # 备注
            ))
        return results

    # ------------------------------------------------------------------
    # 06 人员工资社保 → LarborCost
    # ------------------------------------------------------------------
    def parse_labor_costs(self) -> list[LarborCost]:
        """解析「06人员工资社保」→ List[LarborCost]"""
        ws = self.wb["06人员工资社保"]
        results: list[LarborCost] = []
        for row in _get_data_rows(ws, header_row=6):
            # 列: 月份, 姓名, 岗位, 工资金额, 社保金额, 公积金金额, 个税, 应发合计, 预计发放日期, 付款状态, 付款账户, 备注
            results.append(LarborCost(
                fiscal_month=_parse_str(row[0]),
                employee=_parse_str(row[1]),
                post=_parse_str(row[2]),
                gross_salary=_parse_float(row[3]),
                social_insurance_amount=_parse_float(row[4]),
                housing_fund_amount=_parse_float(row[5]),
                individual_income_tax=_parse_float(row[6]),
                net_salary=_parse_float(row[7]),
                payment_date=_parse_date(row[8]),
                payment_status=_parse_str(row[9]),
                payment_account=_parse_str(row[10]),
                remark=_parse_str(row[11]),
            ))
        return results

    # ------------------------------------------------------------------
    # 07 房租水电 → OfficeExpense
    # ------------------------------------------------------------------
    def parse_office_expenses(self) -> list[OfficeExpense]:
        """解析「07房租水电」→ List[OfficeExpense]"""
        ws = self.wb["07房租水电"]
        results: list[OfficeExpense] = []
        for row in _get_data_rows(ws, header_row=6):
            # 列: 月份, 费用类型, 地点, 费用项目, 金额, 计费周期, 预计付款日期, 付款状态, 付款方式, 备注
            results.append(OfficeExpense(
                fiscal_month=_parse_str(row[0]),
                expense_type=_parse_str(row[1]),
                address=_parse_str(row[2]),
                expense_name=_parse_str(row[3]),
                billing_amount=_parse_float(row[4]),
                billing_cycle=_parse_str(row[5]),
                expected_payment_date=_parse_date(row[6]),
                payment_status=_parse_str(row[7]),
                payer=_parse_str(row[8]),
                remark=_parse_str(row[9]),
            ))
        return results

    # ------------------------------------------------------------------
    # 08 财务税费 → TaxExpense
    # ------------------------------------------------------------------
    def parse_tax_expenses(self) -> list[TaxExpense]:
        """解析「08财务税费」→ List[TaxExpense]"""
        ws = self.wb["08财务税费"]
        results: list[TaxExpense] = []
        for row in _get_data_rows(ws, header_row=6):
            # 列: 月份, 税费类型, 计税/费用说明, 金额, 申报/缴纳日期, 付款状态, 付款账户, 备注
            results.append(TaxExpense(
                fiscal_month=_parse_str(row[0]),
                expense_type=_parse_str(row[1]),
                description=_parse_str(row[2]),
                tax_amount=_parse_float(row[3]),
                declaration_date=_parse_date(row[4]),
                payment_date=_parse_date(row[4]),  # 同日期
                payment_status=_parse_str(row[5]),
                payment_account=_parse_str(row[6]),
                remark=_parse_str(row[7]),
            ))
        return results

    # ------------------------------------------------------------------
    # 09 付款开票 → CashFlow
    # ------------------------------------------------------------------
    def parse_cash_flows(self) -> list[CashFlow]:
        """解析「09付款开票」→ List[CashFlow]"""
        ws = self.wb["09付款开票"]
        results: list[CashFlow] = []
        for row in _get_data_rows(ws, header_row=6):
            # 列: 日期, 对象类型, 客户/供应商名称, 事项类型, 金额, 发票号码/凭证号,
            #     收付款账户, 银行流水摘要, 预计/实际日期, 经办人, 附件名称, 备注
            results.append(CashFlow(
                record_date=_parse_date(row[0]),
                target_type=_parse_str(row[1]),
                entity_name=_parse_str(row[2]),
                item_type=_parse_str(row[3]),
                amount=_parse_float(row[4]),
                voucher_no=_parse_str(row[5]),
                account_name=_parse_str(row[6]),
                bank_summary=_parse_str(row[7]),
                expected_actual_date=_parse_date(row[8]),
                handler=_parse_str(row[9]),
                attachment_name=_parse_str(row[10]),
                remark=_parse_str(row[11]),
            ))
        return results

    # ------------------------------------------------------------------
    # 10 银行流水 → BankTransaction
    # ------------------------------------------------------------------
    def parse_bank_transactions(self) -> list[BankTransaction]:
        """解析「10银行流水」→ List[BankTransaction]"""
        ws = self.wb["10银行流水"]
        results: list[BankTransaction] = []
        for row in _get_data_rows(ws, header_row=6):
            # 列: 交易日期, 账户名称, 对方户名, 收入金额, 支出金额, 账户余额,
            #     摘要, 关联客户/供应商, 关联合同/项目, 支付方式, 备注
            results.append(BankTransaction(
                transaction_date=_parse_date(row[0]),
                account_name=_parse_str(row[1]),
                counterparty_name=_parse_str(row[2]),
                income_amount=_parse_float(row[3]),
                expense_amount=_parse_float(row[4]),
                balance=_parse_float(row[5]),
                summary=_parse_str(row[6]),
                related_party=_parse_str(row[7]),
                related_contract=_parse_str(row[8]),
                payment_method=_parse_str(row[9]),
                remark=_parse_str(row[10]),
            ))
        return results

    # ------------------------------------------------------------------
    # 11 现金流预判 → CashFlow（复用，或用 dict 承载）
    # ------------------------------------------------------------------
    def parse_cash_flow_forecast(self) -> list[dict]:
        """解析「11现金流预判」→ List[dict]（预判表列与 CashFlow 不完全匹配，用 dict）"""
        ws = self.wb["11现金流预判"]
        results: list[dict] = []
        for row in _get_data_rows(ws, header_row=6):
            # 列: 日期/期间, 现金流项目, 对象/来源, 预计收入, 预计支出,
            #     预计余额变化, 预测后余额, 风险判断, 建议动作
            results.append({
                "forecast_date": _parse_date(row[0]) or _parse_str(row[0]),
                "item": _parse_str(row[1]),
                "target": _parse_str(row[2]),
                "expected_income": _parse_float(row[3]),
                "expected_expense": _parse_float(row[4]),
                "balance_change": _parse_float(row[5]),
                "forecast_balance": _parse_float(row[6]),
                "risk_level": _parse_str(row[7]),
                "suggested_action": _parse_str(row[8]),
            })
        return results

    # ------------------------------------------------------------------
    # 全量解析
    # ------------------------------------------------------------------
    def parse_all(self) -> dict[str, list]:
        """解析所有 sheet（跳过第1个「00填写说明」），返回 {sheet_key: [objects]} 字典。

        Returns:
            {
                "purchase_orders": list[PurchaseOrder],
                "sale_contracts": list[SaleContract],
                "purchase_contracts": list[PurchaseContract],
                "project_progress": list[ProjectProgress],
                "logistics": list[Logistics],
                "labor_costs": list[LarborCost],
                "office_expenses": list[OfficeExpense],
                "tax_expenses": list[TaxExpense],
                "cash_flows": list[CashFlow],
                "bank_transactions": list[BankTransaction],
                "cash_flow_forecast": list[dict],
            }
        """
        result = {
            "purchase_orders": self.parse_purchase_orders(),
            "sale_contracts": self.parse_sale_contracts(),
            "purchase_contracts": self.parse_purchase_contracts(),
            "project_progress": self.parse_project_progress(),
            "logistics": self.parse_logistics(),
            "labor_costs": self.parse_labor_costs(),
            "office_expenses": self.parse_office_expenses(),
            "tax_expenses": self.parse_tax_expenses(),
            "cash_flows": self.parse_cash_flows(),
            "bank_transactions": self.parse_bank_transactions(),
            "cash_flow_forecast": self.parse_cash_flow_forecast(),
        }
        self.close()
        return result


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------

def parse_excel(filepath: str) -> dict[str, list]:
    """快捷解析函数。"""
    return ExcelParser(filepath).parse_all()
