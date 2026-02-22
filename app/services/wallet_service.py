import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Wallet,
    Asset,
    Transaction,
    LedgerEntry,
    TransactionType,
)

def get_balance(db: Session, *, user_id: uuid.UUID, asset_code: str) -> dict:
    asset = db.execute(
        select(Asset).where(Asset.code == asset_code)
    ).scalar_one()
    wallet = db.execute(
        select(Wallet)
        .where(Wallet.user_id == user_id)
        .where(Wallet.asset_id == asset.id)
    ).scalar_one()
    return {
        "user_id": str(user_id),
        "asset_code": asset_code,
        "balance": wallet.balance,
    }


def _get_and_lock_wallets(
    db: Session,
    user_id: uuid.UUID,
    asset_code: str,
):
    # Get asset
    asset = db.execute(
        select(Asset).where(Asset.code == asset_code)
    ).scalar_one()

    # Get system (treasury) wallet
    system_wallet = db.execute(
        select(Wallet)
        .where(Wallet.user_id.is_(None))
        .where(Wallet.asset_id == asset.id)
        .with_for_update()
    ).scalar_one()

    # Get user wallet
    user_wallet = db.execute(
        select(Wallet)
        .where(Wallet.user_id == user_id)
        .where(Wallet.asset_id == asset.id)
        .with_for_update()
    ).scalar_one()

    return system_wallet, user_wallet


def _get_existing_transaction_amount(db: Session, transaction_id) -> int:
    result = db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.transaction_id == transaction_id)
        .where(LedgerEntry.amount > 0)
    )
    entry = result.scalar_one()
    return entry.amount


def top_up_wallet(
    db: Session,
    *,
    user_id: uuid.UUID,
    asset_code: str,
    amount: int,
    idempotency_key: str,
):
    if amount <= 0:
        raise ValueError("Amount must be positive")

    try:
        # Start logical transaction
        transaction = Transaction(
            type=TransactionType.TOPUP,
            idempotency_key=idempotency_key,
        )
        db.add(transaction)
        db.flush()  # get transaction.id

        # Lock wallets
        system_wallet, user_wallet = _get_and_lock_wallets(
            db, user_id, asset_code
        )

        # Ledger entries
        debit = LedgerEntry(
            transaction_id=transaction.id,
            wallet_id=system_wallet.id,
            amount=-amount,
        )
        credit = LedgerEntry(
            transaction_id=transaction.id,
            wallet_id=user_wallet.id,
            amount=amount,
        )

        db.add_all([debit, credit])

        # Update cached balances
        system_wallet.balance -= amount
        user_wallet.balance += amount

        db.commit()

        return {
            "transaction_id": str(transaction.id),
            "credited": amount,
        }

    except IntegrityError:
        db.rollback()
        # idempotency_key already exists — return original result
        existing = db.execute(
            select(Transaction).where(
                Transaction.idempotency_key == idempotency_key
            )
        ).scalar_one()
        amount = _get_existing_transaction_amount(db, existing.id)
        return {
            "transaction_id": str(existing.id),
            "credited": amount,
            "status": "duplicate",
        }

    except Exception:
        db.rollback()
        raise


def credit_bonus(
    db: Session,
    *,
    user_id: uuid.UUID,
    asset_code: str,
    amount: int,
    idempotency_key: str,
):
    """Issue free credits to a user (e.g. referral bonus, incentive). Same flow as top-up with type BONUS."""
    if amount <= 0:
        raise ValueError("Amount must be positive")

    try:
        transaction = Transaction(
            type=TransactionType.BONUS,
            idempotency_key=idempotency_key,
        )
        db.add(transaction)
        db.flush()

        system_wallet, user_wallet = _get_and_lock_wallets(db, user_id, asset_code)

        debit = LedgerEntry(
            transaction_id=transaction.id,
            wallet_id=system_wallet.id,
            amount=-amount,
        )
        credit = LedgerEntry(
            transaction_id=transaction.id,
            wallet_id=user_wallet.id,
            amount=amount,
        )
        db.add_all([debit, credit])

        system_wallet.balance -= amount
        user_wallet.balance += amount

        db.commit()
        return {
            "transaction_id": str(transaction.id),
            "credited": amount,
        }

    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(Transaction).where(
                Transaction.idempotency_key == idempotency_key
            )
        ).scalar_one()
        amount = _get_existing_transaction_amount(db, existing.id)
        return {
            "transaction_id": str(existing.id),
            "credited": amount,
            "status": "duplicate",
        }

    except Exception:
        db.rollback()
        raise


def spend_from_wallet(
    db: Session,
    *,
    user_id: uuid.UUID,
    asset_code: str,
    amount: int,
    idempotency_key: str,
):
    if amount <= 0:
        raise ValueError("Amount must be positive")

    try:
        # Create logical transaction
        transaction = Transaction(
            type=TransactionType.SPEND,
            idempotency_key=idempotency_key,
        )
        db.add(transaction)
        db.flush()  # get transaction.id

        # Lock wallets
        system_wallet, user_wallet = _get_and_lock_wallets(
            db, user_id, asset_code
        )

        # Balance check
        if user_wallet.balance < amount:
            raise ValueError("Insufficient balance")

        # Ledger entries (user pays, system receives)
        debit = LedgerEntry(
            transaction_id=transaction.id,
            wallet_id=user_wallet.id,
            amount=-amount,
        )
        credit = LedgerEntry(
            transaction_id=transaction.id,
            wallet_id=system_wallet.id,
            amount=amount,
        )

        db.add_all([debit, credit])

        # Update cached balances
        user_wallet.balance -= amount
        system_wallet.balance += amount

        db.commit()

        return {
            "transaction_id": str(transaction.id),
            "spent": amount,
        }

    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(Transaction).where(
                Transaction.idempotency_key == idempotency_key
            )
        ).scalar_one()
        amount = _get_existing_transaction_amount(db, existing.id)
        return {
            "transaction_id": str(existing.id),
            "spent": amount,
            "status": "duplicate",
        }

    except Exception:
        db.rollback()
        raise
