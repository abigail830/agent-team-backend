import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AgentOut
from app.db.models import AgentModel
from app.db.session import get_db
from app.platform.current_user import get_current_user

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[AgentOut]:
    result = await db.execute(
        select(AgentModel).where(AgentModel.slug.isnot(None)).order_by(AgentModel.name)
    )
    return [_to_out(a) for a in result.scalars().all()]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
) -> AgentOut:
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _to_out(agent)


def _to_out(agent: AgentModel) -> AgentOut:
    return AgentOut(
        id=agent.id,
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        model_provider=agent.model_provider,
        model_name=agent.model_name,
    )
