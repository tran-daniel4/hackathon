from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from core.analysis_service import execute_analysis

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    file_tree: str = ""
    files: dict[str, str] = Field(default_factory=dict)
    repo_url: str | None = None
    repo_branch: str | None = None
    github_token: str | None = None


class AnalyzeResponse(BaseModel):
    repo_analysis: dict
    system_design: dict
    bottlenecks: dict
    diagram: dict
    diagrams: list[dict]
    graph_facts: dict
    analysis_debug: dict


@router.post("", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest):
    try:
        bundle = await execute_analysis(
            files=body.files,
            repo_url=body.repo_url,
            repo_branch=body.repo_branch,
            github_token=body.github_token,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {exc}",
        )

    return AnalyzeResponse(**bundle.payload)
