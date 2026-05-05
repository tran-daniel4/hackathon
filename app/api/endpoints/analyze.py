from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from agents.orchestrator import run_pipeline

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    file_tree: str
    # Map of relative file path → file contents
    files: dict[str, str]


class AnalyzeResponse(BaseModel):
    repo_analysis: dict
    system_design: dict
    bottlenecks: dict
    diagram: dict


def _format_file_contents(files: dict[str, str]) -> str:
    parts = []
    for path, content in files.items():
        parts.append(f"### {path}\n{content}")
    return "\n\n".join(parts)


@router.post("", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest):
    file_contents = _format_file_contents(body.files)
    try:
        result = run_pipeline(body.file_tree, file_contents)
    except ValueError as e:
        # An agent returned non-JSON — surface the detail so the caller can debug
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {e}",
        )

    return AnalyzeResponse(
        repo_analysis=result["repo_analysis"],
        system_design=result["system_design"],
        bottlenecks=result["bottlenecks"],
        diagram=result["diagram"],
    )
