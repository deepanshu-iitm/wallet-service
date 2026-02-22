from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

from app.schemas.transactions import TopUpRequest, BonusRequest, SpendRequest
from app.services.wallet_service import (
    top_up_wallet,
    credit_bonus,
    spend_from_wallet,
    get_balance,
)
from app.db.deps import get_db

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/topup")
def top_up(request: TopUpRequest, db: Session = Depends(get_db)):
    try:
        result = top_up_wallet(
            db,
            user_id=request.user_id,
            asset_code=request.asset_code,
            amount=request.amount,
            idempotency_key=request.idempotency_key,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/bonus")
def bonus(request: BonusRequest, db: Session = Depends(get_db)):
    try:
        result = credit_bonus(
            db,
            user_id=request.user_id,
            asset_code=request.asset_code,
            amount=request.amount,
            idempotency_key=request.idempotency_key,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/balance")
def balance(
    user_id: UUID = Query(..., description="User ID"),
    asset_code: str = Query(..., description="Asset code (e.g. GOLD, DIAMONDS)"),
    db: Session = Depends(get_db),
):
    try:
        return get_balance(db, user_id=user_id, asset_code=asset_code)
    except NoResultFound:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found for this user and asset",
        )


@router.post("/spend")
def spend(request: SpendRequest, db: Session = Depends(get_db)):
    try:
        result = spend_from_wallet(
            db,
            user_id=request.user_id,
            asset_code=request.asset_code,
            amount=request.amount,
            idempotency_key=request.idempotency_key,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")

