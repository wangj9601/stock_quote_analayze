"""模拟交易相关API"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, conint, confloat
from sqlalchemy.orm import Session

from backend_api.auth import get_current_user
from backend_api.database import get_db
from backend_api.models import (
    SimTradeAccount,
    SimTradePosition,
    SimTradeOrder,
    StockRealtimeQuote,
    User,
)


router = APIRouter(prefix="/api/simtrade", tags=["simtrade"])

DEFAULT_INITIAL_CAPITAL = 1_000_000.0


class TradeOrderRequest(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    side: str
    quantity: conint(gt=0)
    price: Optional[confloat(gt=0)] = None
    remark: Optional[str] = None


class SimTradePositionSchema(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    quantity: int
    avg_price: float
    last_price: float
    market_value: float
    unrealized_profit: float
    unrealized_percent: float


class SimTradeOrderSchema(BaseModel):
    id: int
    stock_code: str
    stock_name: Optional[str] = None
    side: str
    price: float
    quantity: int
    amount: float
    fee: float
    status: str
    remark: Optional[str] = None
    realized_profit: float
    created_at: datetime


class SimTradeAccountSummary(BaseModel):
    initial_capital: float
    cash_balance: float
    total_market_value: float
    total_assets: float
    total_profit: float
    total_profit_rate: float
    day_profit: float = 0.0
    day_profit_rate: float = 0.0


class SimTradeDashboardResponse(BaseModel):
    account: SimTradeAccountSummary
    positions: List[SimTradePositionSchema]
    recent_orders: List[SimTradeOrderSchema]


def _ensure_account(db: Session, user_id: int) -> SimTradeAccount:
    account = (
        db.query(SimTradeAccount)
        .filter(SimTradeAccount.user_id == user_id)
        .first()
    )
    if account is None:
        account = SimTradeAccount(
            user_id=user_id,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            cash_balance=DEFAULT_INITIAL_CAPITAL,
            total_market_value=0.0,
            total_profit=0.0,
            total_profit_rate=0.0,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def _latest_quote(db: Session, stock_code: str) -> Optional[StockRealtimeQuote]:
    return (
        db.query(StockRealtimeQuote)
        .filter(StockRealtimeQuote.code == stock_code)
        .order_by(StockRealtimeQuote.trade_date.desc())
        .first()
    )


def _fallback_price(position: Optional[SimTradePosition], quote: Optional[StockRealtimeQuote]) -> float:
    if quote:
        # StockRealtimeQuote 模型中没有 close 字段，只有 current_price 和 pre_close
        for candidate in [quote.current_price, quote.pre_close]:
            if candidate is not None:
                return float(candidate)
    if position is not None:
        if position.last_price:
            return float(position.last_price)
        return float(position.avg_price or 0.0)
    return 0.0


def _refresh_positions(db: Session, user_id: int) -> List[SimTradePosition]:
    positions = (
        db.query(SimTradePosition)
        .filter(SimTradePosition.user_id == user_id)
        .all()
    )

    total_market_value = 0.0
    for position in positions:
        quote = _latest_quote(db, position.stock_code)
        price = _fallback_price(position, quote)
        position.last_price = price
        position.market_value = round(price * position.quantity, 2)
        cost = position.avg_price * position.quantity
        position.unrealized_profit = round(position.market_value - cost, 2)
        position.updated_at = datetime.now()
        total_market_value += position.market_value

    account = _ensure_account(db, user_id)
    account.total_market_value = round(total_market_value, 2)
    account.total_profit = round(account.cash_balance + total_market_value - account.initial_capital, 2)
    account.total_profit_rate = (
        round((account.total_profit / account.initial_capital) * 100, 4)
        if account.initial_capital
        else 0.0
    )
    account.updated_at = datetime.now()

    db.flush()
    return positions


def _serialize_position(position: SimTradePosition) -> SimTradePositionSchema:
    market_value = float(position.market_value or 0.0)
    cost = float(position.avg_price or 0.0) * position.quantity
    unrealized_profit = float(position.unrealized_profit or 0.0)
    unrealized_percent = 0.0
    if cost > 0:
        unrealized_percent = (unrealized_profit / cost) * 100
    return SimTradePositionSchema(
        stock_code=position.stock_code,
        stock_name=position.stock_name,
        quantity=position.quantity,
        avg_price=float(position.avg_price or 0.0),
        last_price=float(position.last_price or 0.0),
        market_value=market_value,
        unrealized_profit=round(unrealized_profit, 2),
        unrealized_percent=round(unrealized_percent, 2),
    )


def _serialize_order(order: SimTradeOrder) -> SimTradeOrderSchema:
    return SimTradeOrderSchema(
        id=order.id,
        stock_code=order.stock_code,
        stock_name=order.stock_name,
        side=order.side,
        price=float(order.price),
        quantity=order.quantity,
        amount=float(order.amount),
        fee=float(order.fee or 0.0),
        status=order.status,
        remark=order.remark,
        realized_profit=float(order.realized_profit or 0.0),
        created_at=order.created_at,
    )


def _account_summary(account: SimTradeAccount) -> SimTradeAccountSummary:
    total_assets = float(account.cash_balance or 0.0) + float(account.total_market_value or 0.0)
    return SimTradeAccountSummary(
        initial_capital=float(account.initial_capital or 0.0),
        cash_balance=float(account.cash_balance or 0.0),
        total_market_value=float(account.total_market_value or 0.0),
        total_assets=round(total_assets, 2),
        total_profit=float(account.total_profit or 0.0),
        total_profit_rate=float(account.total_profit_rate or 0.0),
    )


@router.get("/dashboard", response_model=SimTradeDashboardResponse)
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    recent_limit: int = Query(5, ge=1, le=50),
):
    account = _ensure_account(db, current_user.id)
    positions = _refresh_positions(db, current_user.id)

    recent_orders = (
        db.query(SimTradeOrder)
        .filter(SimTradeOrder.user_id == current_user.id)
        .order_by(SimTradeOrder.created_at.desc())
        .limit(recent_limit)
        .all()
    )

    db.commit()

    return SimTradeDashboardResponse(
        account=_account_summary(account),
        positions=[_serialize_position(p) for p in positions],
        recent_orders=[_serialize_order(o) for o in recent_orders],
    )


@router.get("/account", response_model=SimTradeAccountSummary)
def get_account_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = _ensure_account(db, current_user.id)
    _refresh_positions(db, current_user.id)
    db.commit()
    return _account_summary(account)


@router.get("/positions", response_model=List[SimTradePositionSchema])
def get_positions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ensure_account(db, current_user.id)
    positions = _refresh_positions(db, current_user.id)
    db.commit()
    return [_serialize_position(p) for p in positions]


@router.get("/orders", response_model=List[SimTradeOrderSchema])
def list_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    orders = (
        db.query(SimTradeOrder)
        .filter(SimTradeOrder.user_id == current_user.id)
        .order_by(SimTradeOrder.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [_serialize_order(o) for o in orders]


@router.post("/orders", response_model=SimTradeDashboardResponse)
def place_order(
    order_request: TradeOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    side = order_request.side.lower()
    if side not in {"buy", "sell"}:
        raise HTTPException(status_code=400, detail="交易方向必须为 buy 或 sell")

    account = _ensure_account(db, current_user.id)

    quote = _latest_quote(db, order_request.stock_code)
    trade_price = order_request.price

    quantity = int(order_request.quantity)

    try:
        position = (
            db.query(SimTradePosition)
            .filter(
                SimTradePosition.user_id == current_user.id,
                SimTradePosition.stock_code == order_request.stock_code,
            )
            .first()
        )

        if trade_price is None:
            if quote is None and position is None:
                raise HTTPException(status_code=400, detail="暂无该股票行情，无法获取成交价格")
            trade_price = _fallback_price(position, quote)

        trade_price = float(trade_price)
        if trade_price <= 0:
            raise HTTPException(status_code=400, detail="无效的成交价格")

        stock_name = order_request.stock_name or (quote.name if quote else None) or order_request.stock_code

        amount = round(trade_price * quantity, 2)

        if side == "buy":
            if amount > account.cash_balance + 1e-6:
                raise HTTPException(status_code=400, detail="账户现金余额不足")
            account.cash_balance = round(account.cash_balance - amount, 2)

            if position is None:
                position = SimTradePosition(
                    user_id=current_user.id,
                    stock_code=order_request.stock_code,
                    stock_name=stock_name,
                    quantity=0,
                    avg_price=0.0,
                )
                db.add(position)

            total_shares = position.quantity + quantity
            total_cost = position.avg_price * position.quantity + amount
            position.quantity = total_shares
            position.avg_price = round(total_cost / total_shares, 4)
            position.stock_name = stock_name
            position.last_price = trade_price

            realized_profit = 0.0
        else:  # sell
            if position is None or position.quantity < quantity:
                raise HTTPException(status_code=400, detail="可用持仓不足")

            account.cash_balance = round(account.cash_balance + amount, 2)
            position.quantity -= quantity
            position.last_price = trade_price

            realized_profit = round((trade_price - position.avg_price) * quantity, 2)

            if position.quantity == 0:
                db.delete(position)

        order = SimTradeOrder(
            user_id=current_user.id,
            stock_code=order_request.stock_code,
            stock_name=stock_name,
            side=side,
            price=trade_price,
            quantity=quantity,
            amount=amount,
            fee=0.0,
            status="filled",
            remark=order_request.remark,
            realized_profit=realized_profit,
            created_at=datetime.now(),
        )
        db.add(order)

        positions = _refresh_positions(db, current_user.id)
        db.commit()

        recent_orders = (
            db.query(SimTradeOrder)
            .filter(SimTradeOrder.user_id == current_user.id)
            .order_by(SimTradeOrder.created_at.desc())
            .limit(5)
            .all()
        )

        return SimTradeDashboardResponse(
            account=_account_summary(account),
            positions=[_serialize_position(p) for p in positions],
            recent_orders=[_serialize_order(o) for o in recent_orders],
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=f"模拟交易下单失败: {exc}")

