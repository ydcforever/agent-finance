from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = "mysql+pymysql://root:Jsy123654!@rm-uf6pivyzvokc94150zo.mysql.rds.aliyuncs.com:3306/formula_ai_finance?charset=utf8mb4"
engine = create_engine(DATABASE_URL, echo=True)

# 创建数据库会话（用来和数据库打交道）
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ================= 1. 定义数据库模型基类 =================
class Base(DeclarativeBase):
    pass

def init_db() -> None:
    # 导入所有模型类（确保它们都被注册到 SQLAlchemy 的元数据中）
    from server import models  # noqa: F401

    # 自动在数据库里创建表
    Base.metadata.create_all(bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()