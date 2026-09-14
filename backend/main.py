# HTTP API for BuildFlow AI

from backend.claude_service import chat_with_buildflow

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.project_service import (
    projects,
    get_critical_rfis,
    get_blocking_rfis,
    get_project_summary
)

class RFIInput(BaseModel):
    title: str
    days_open: int
    is_blocking: bool

class ChatInput(BaseModel):
    message: str

app = FastAPI(title="BuildFlow AI API")


# ENDPOINTS

# GET END POINTS

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/projects")
def get_projects():
    return projects

@app.get("/projects/{project_id}")
def get_project(project_id: int):
    for project in projects:
        if project["id"] == project_id:
            return project

    raise HTTPException(
        status_code=404,
        detail="Project not found"
    )

@app.get("/projects/{project_id}/rfis")
def get_project_rfis(project_id: int):
    for project in projects:
        if project["id"] == project_id:
            return project["rfis"]

    raise HTTPException(
        status_code=404,
        detail="Project not found"
    )

@app.get("/projects/{project_id}/summary")
def project_summary(project_id: int):
    for project in projects:
        if project["id"] == project_id:
            return get_project_summary(project)

    raise HTTPException(
        status_code=404,
        detail="Project not found"
    )

@app.get("/projects/{project_id}/rfis/critical")
def get_project_critical_rfis(project_id: int):
    for project in projects:
        if project["id"] == project_id:
            return get_critical_rfis(project["rfis"])

    raise HTTPException(
        status_code=404,
        detail="Project not found"
    )

@app.get("/projects/{project_id}/rfis/filter")
def filter_project_rfis(project_id: int, blocking: bool = False):
    for project in projects:
        if project["id"] == project_id:
            rfis = project["rfis"]

            if blocking:
                return get_blocking_rfis(rfis)

            return rfis

    raise HTTPException(
        status_code=404,
        detail="Project not found"
    )

# POST ENDPOINTS

@app.post("/projects/{project_id}/rfis")
def create_rfi(project_id: int, rfi: RFIInput):
    for project in projects:
        if project["id"] == project_id:
            new_rfi = {
                "id": len(project["rfis"]) + 1,
                "title": rfi.title,
                "days_open": rfi.days_open,
                "is_blocking": rfi.is_blocking
            }

            project["rfis"].append(new_rfi)

            return new_rfi

    raise HTTPException(
        status_code=404,
        detail="Project not found"
    )

@app.post("/ai/chat")
def chat_with_ai(chat: ChatInput):
    answer = chat_with_buildflow(chat.message)

    return {
        "answer": answer
    }