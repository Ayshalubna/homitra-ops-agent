"""FastAPI surface for the Homitra Ops Agent.

Run:  uvicorn app.main:app --reload
Docs: http://127.0.0.1:8000/docs   (interactive OpenAPI UI)

Endpoints:
  GET  /healthz              -> liveness + current config (public, no auth)
  GET  /bookings/pending     -> bookings worth the agent's attention
  POST /runs                 -> start an agent run on a booking (may pause for approval)
  GET  /runs                 -> list runs
  GET  /runs/{run_id}        -> one run (triage, risk, proposal, decision, trace)
  POST /runs/{run_id}/approve-> approve the proposed action (executes it)
  POST /runs/{run_id}/reject -> reject the proposed action (no side-effect)
  GET  /metrics              -> token / latency / cost summary

Security: when API_TOKEN is set (production), every endpoint except /healthz
requires `Authorization: Bearer <API_TOKEN>`. When it is empty (local/offline),
the API is open so the demo runs with zero setup.
"""
from __future__ import annotations
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .observability import metrics
from . import service, store

app = FastAPI(title="Homitra Ops Agent", version="0.1.0",
              description="LLM operations agent with human-in-the-loop approval.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_token(authorization: str = Header(default="")) -> None:
    """Gate every protected route behind a bearer token when API_TOKEN is set."""
    if settings.api_token and authorization != f"Bearer {settings.api_token}":
        raise HTTPException(401, "missing or invalid API token")


class StartRun(BaseModel):
    booking_id: str


class Decide(BaseModel):
    decided_by: str = "operator"
    note: str = ""


@app.get("/healthz")
def healthz():
    # public: no secrets, used by Render/uptime checks
    return {"ok": True, "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "data_source": "supabase" if settings.use_supabase else "sample",
            "auth_required": bool(settings.api_token),
            "auto_approve": settings.auto_approve}


@app.get("/bookings/pending", dependencies=[Depends(require_token)])
def pending():
    # anything not finished is "pending attention" for ops
    return [b for b in store.list_bookings()
            if b.status in ("pending", "confirmed", "in_progress")]


@app.post("/runs", dependencies=[Depends(require_token)])
def create_run(body: StartRun):
    try:
        return service.start_run(body.booking_id)
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/runs", dependencies=[Depends(require_token)])
def runs():
    return service.list_runs()


@app.get("/runs/{run_id}", dependencies=[Depends(require_token)])
def one_run(run_id: str):
    r = service.get_run(run_id)
    if not r:
        raise HTTPException(404, "run not found")
    return r


@app.post("/runs/{run_id}/approve", dependencies=[Depends(require_token)])
def approve(run_id: str, body: Decide):
    if not service.get_run(run_id):
        raise HTTPException(404, "run not found")
    return service.approve(run_id, body.decided_by, body.note)


@app.post("/runs/{run_id}/reject", dependencies=[Depends(require_token)])
def reject(run_id: str, body: Decide):
    if not service.get_run(run_id):
        raise HTTPException(404, "run not found")
    return service.reject(run_id, body.decided_by, body.note)


@app.get("/metrics", dependencies=[Depends(require_token)])
def get_metrics():
    return metrics.summary()
