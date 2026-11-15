from datetime import timedelta

from app.config import StrategyCfg
from app.strategy.exits import evaluate_exit
from app.utils import utcnow


def _position(**overrides):
    now = utcnow()
    position = {
        "entry_price": 1.0,
        "current_price": 1.0,
        "peak_price": 1.0,
        "tokens_remaining": 1_000.0,
        "token_amount": 1_000.0,
        "liquidity_at_entry": 50_000.0,
        "liquidity_now": 50_000.0,
        "tp_taken": [],
        "trailing_active": False,
        "opened_at": now - timedelta(minutes=10),
    }
    position.update(overrides)
    return position


def test_stop_loss_triggers_below_limit():
    plan = evaluate_exit(_position(current_price=0.74), StrategyCfg(), utcnow())
    assert plan.has_actions
    assert plan.actions[0].kind == "stop_loss"
    assert plan.actions[0].sell_all
    assert plan.emergency


def test_first_take_profit_is_partial_and_activates_trailing():
    plan = evaluate_exit(_position(current_price=2.0, peak_price=2.0), StrategyCfg(), utcnow())
    assert len(plan.actions) == 1
    action = plan.actions[0]
    assert action.kind == "take_profit"
    assert action.fraction_of_original == 0.5
    assert action.tp_index == 0
    assert action.activates_trailing
    assert not action.sell_all


def test_two_take_profits_can_fire_together():
    plan = evaluate_exit(_position(current_price=4.2, peak_price=4.2), StrategyCfg(), utcnow())
    indices = [action.tp_index for action in plan.actions]
    assert indices == [0, 1]


def test_taken_profit_is_not_repeated():
    plan = evaluate_exit(
        _position(current_price=2.0, peak_price=2.0, tp_taken=[0]),
        StrategyCfg(),
        utcnow(),
    )
    assert not plan.has_actions


def test_trailing_stop_after_peak():
    position = _position(
        current_price=1.30,
        peak_price=2.0,
        tp_taken=[0],
        trailing_active=True,
    )
    plan = evaluate_exit(position, StrategyCfg(), utcnow())
    assert plan.actions[0].kind == "trailing_stop"
    assert plan.actions[0].sell_all


def test_time_stop_for_flat_position():
    position = _position(opened_at=utcnow() - timedelta(minutes=50))
    plan = evaluate_exit(position, StrategyCfg(), utcnow())
    assert plan.actions[0].kind == "time_stop"


def test_rugged_token_exits_with_zero_proceeds():
    plan = evaluate_exit(_position(current_price=0.01), StrategyCfg(), utcnow(), {"rugged": True})
    assert plan.actions[0].kind == "rug"
    assert plan.actions[0].zero_proceeds
    assert plan.emergency


def test_liquidity_drain_emergency_exit():
    position = _position(current_price=1.05, liquidity_now=20_000.0)
    plan = evaluate_exit(position, StrategyCfg(), utcnow())
    assert plan.actions[0].kind == "emergency"
    assert plan.actions[0].sell_all


def test_creator_sell_and_holder_dump_emergencies():
    creator = evaluate_exit(_position(current_price=1.05), StrategyCfg(), utcnow(), {"creator_sold": True})
    dump = evaluate_exit(_position(current_price=1.05), StrategyCfg(), utcnow(), {"top_holders_dump": True})
    assert creator.actions[0].kind == "emergency"
    assert dump.actions[0].kind == "emergency"
