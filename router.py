from fastapi import APIRouter

from .schemas import TipsBatchIn, TipsBatchOut
from .agent import PersonalizedTipsAgent

router = APIRouter(prefix="/api/v1/tips", tags=["tips"])

_agent = PersonalizedTipsAgent()

@router.post("/personalized_batch", response_model=TipsBatchOut)
def tips_batch(payload: TipsBatchIn) -> TipsBatchOut:
    """根据到检名单批量生成个性化注意事项（独立于 recom2）。"""
    return _agent.run_batch(payload)