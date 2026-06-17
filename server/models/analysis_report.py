"""
经营分析报告模型 —— 从 AI 对话输出中提取结构化报告数据
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON
from server.util.database import Base


class AnalysisReport(Base):
    """经营分析报告表"""
    __tablename__ = "analysis_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False, comment="报告标题")
    content_raw = Column(Text, nullable=True, comment="AI 原始对话输出全文")
    extracted_data = Column(JSON, nullable=True, comment="提取的结构化数据")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
