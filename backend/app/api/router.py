from fastapi import APIRouter
from app.api.endpoints import admin, auth, classes, predict, reports, students

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Accounts"])
api_router.include_router(predict.router, prefix="/predict", tags=["Classification Core"])
api_router.include_router(classes.router, prefix="/classes", tags=["Classes"])
api_router.include_router(students.router, prefix="/students", tags=["Students"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
