from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class ResearchRequest(BaseModel):
    research_topic: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Topic the user wants to research"
    )

    research_depth: str = Field(
        default="standard",
        description="Research depth: basic, standard, or comprehensive"
    )


@router.post("/validate")
async def validate_research_request(request: ResearchRequest):

    allowed_depths = ["basic", "standard", "comprehensive"]

    if request.research_depth not in allowed_depths:
        return {
            "status": "error",
            "message": "Invalid research depth",
            "allowed_values": allowed_depths
        }

    return {
        "status": "success",
        "message": "Research request validated successfully",
        "data": {
            "research_topic": request.research_topic,
            "research_depth": request.research_depth
        }
    }