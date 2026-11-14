# HTTP API for BuildFlow AI
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated

import anthropic

from backend.claude_service import InvalidProviderResponse, chat_with_buildflow

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints

from backend.project_service import (
    projects,
    get_critical_rfis,
    get_blocking_rfis,
    get_project_summary
)

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RFIInput(BaseModel):
    title: NonBlankText
    days_open: int = Field(ge=0)
    is_blocking: bool

class ChatInput(BaseModel):
    message: NonBlankText

app = FastAPI(title="BuildFlow AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    try:
        answer = chat_with_buildflow(chat.message)
    except InvalidProviderResponse:
        raise HTTPException(502, "BuildFlow's AI service returned an incomplete response. Please try again.") from None
    except anthropic.APITimeoutError:
        raise HTTPException(504, "BuildFlow's AI service timed out. Please try again.") from None
    except anthropic.APIConnectionError:
        raise HTTPException(503, "BuildFlow's AI service is temporarily unavailable. Please try again.") from None
    except anthropic.APIStatusError as error:
        if error.status_code in (408, 504):
            raise HTTPException(504, "BuildFlow's AI service timed out. Please try again.") from None
        if error.status_code == 429:
            raise HTTPException(429, "BuildFlow's AI service is busy. Please wait before trying again.") from None
        if error.status_code in (401, 403):
            raise HTTPException(503, "BuildFlow's AI service needs administrator attention. Please contact the demo operator.") from None
        if error.status_code >= 500:
            raise HTTPException(503, "BuildFlow's AI service is temporarily unavailable. Please try again.") from None
        raise HTTPException(502, "BuildFlow's AI service could not process the request. Please contact the demo operator.") from None
    except anthropic.AnthropicError:
        raise HTTPException(503, "BuildFlow's AI service is not ready. Please contact the demo operator.") from None

    return {
        "answer": answer
    }
