from fastapi import FastAPI, Request, status
from fastapi.concurrency import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from scalar_fastapi import Theme, get_scalar_api_reference

from server.util.database import init_db

from server.routers import (
    purchase_order_router, 
    sale_contract_router, 
    purchase_contract_router, 
    logistics_router, 
    project_progress_router, 
    labor_cost_router, 
    office_expense_router,
    bank_transaction_router,
    loan_router,
    private_txs_router,
    cash_flow_router,
    tax_expense_router,
    ai_chat_workbuddy_router,
    ai_chat_coze_router,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # 启动时初始化数据库
    yield  # 这里可以放一些清理资源的代码，比如关闭数据库连接等


# ================= 4. FastAPI 接口层 =================
app = FastAPI(lifespan=lifespan, swagger_ui_parameters={"defaultModelExpandDepth": 5, "defaultModelsExpandDepth": 5})
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
add_pagination(app)  # 添加分页功能

app.mount('/static', StaticFiles(directory='.'), name='static')

@app.get('/workbuddy', include_in_schema=False)
async def demo_html():
    return FileResponse('server/workbuddy/workbuddy_demo.html')

@app.get('/coze', include_in_schema=False)
async def coze_demo_html():
    return FileResponse('server/coze/coze_demo.html')

@app.get('/coze_ui', include_in_schema=False)
async def coze_ui_html():
    return FileResponse('server/coze/index.html')

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        theme=Theme.KEPLER,
    )

app.include_router(purchase_order_router)
app.include_router(sale_contract_router)
app.include_router(purchase_contract_router)
app.include_router(logistics_router)
app.include_router(project_progress_router)
app.include_router(labor_cost_router)
app.include_router(office_expense_router)
app.include_router(bank_transaction_router)
app.include_router(loan_router)
app.include_router(private_txs_router)
app.include_router(cash_flow_router)
app.include_router(tax_expense_router)
app.include_router(ai_chat_workbuddy_router)
app.include_router(ai_chat_coze_router)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # 提取具体的报错信息，方便前端展示
    error_messages = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error["loc"])  # 报错的字段路径
        msg = error["msg"]  # 报错的具体原因
        error_messages.append(f"{field}: {msg}")
    
    # 返回符合 R 结构的 JSON 响应
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content= {
            "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "message": "Validation Error",
            "data": error_messages
        }
    )
