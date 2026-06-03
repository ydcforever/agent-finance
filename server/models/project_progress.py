
from sqlalchemy import Boolean, Date, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

import uuid
from datetime import date
from server.util.database import Base

# ================= 2. 数据库模型 (结合你之前的代码) =================
class ProjectProgress(Base):
    __tablename__ = "project_progress"


    # 注意：在现代写法中，推荐使用 Mapped 和 mapped_column 来定义字段
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    related_party: Mapped[str] = mapped_column(String(255), comment="关联方，如项目/客户")
    manager: Mapped[str] = mapped_column(String(255), comment="负责人")
    construction_task: Mapped[str] = mapped_column(String(255), comment="施工任务")
    progress: Mapped[str] = mapped_column(String(255), comment="进度")
    expected_completion_date: Mapped[date] = mapped_column(Date, comment="预计完成日期")
    affect_received: Mapped[bool] = mapped_column(Boolean, comment="是否影响回款")
    additional_notes: Mapped[str] = mapped_column(String(255), comment="补充说明")
    remark: Mapped[str] = mapped_column(String(255), comment="备注信息")
    follow_up_date: Mapped[date] = mapped_column(Date, comment="跟进日期")

    __table_args__ = (
        Index('idx_project_progress_construction_task', 'related_party', 'manager'),
        {"comment": "施工进度"},
    )