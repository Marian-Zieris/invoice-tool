from fastapi import FastAPI

from app.routers import auth, customers, invoices, me, upload

app = FastAPI(title="Invoice OCR Tool")

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(upload.router)
app.include_router(invoices.router)
app.include_router(me.router)


@app.get("/health")
def health():
    return {"success": True, "data": {"status": "ok"}, "message": "Health check passed."}
