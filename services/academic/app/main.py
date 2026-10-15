from fastapi import FastAPI
from classync_contracts.models import HealthResponse

app = FastAPI(title="ClassSync Academic Service", version="1.0.0")

@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    return HealthResponse(service="academic")
