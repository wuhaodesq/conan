from hybrid_trainer.engine import TrainingEngine
from hybrid_trainer.pipeline import DecisionNode
from hybrid_trainer.strategy import StrategyManager, TrainingStrategy


def test_strategy_recommend_sft_when_block_high() -> None:
    manager = StrategyManager(current=TrainingStrategy.RL)
    engine = TrainingEngine(strategy_manager=manager)
    engine.run_cycles(1, 4, DecisionNode.FAILURE_REVIEW)

    switch = engine.maybe_switch_strategy()
    assert switch is not None
    assert switch.to_strategy == TrainingStrategy.SFT


def test_strategy_recommend_rl_when_quality_stable() -> None:
    engine = TrainingEngine()
    engine.run_cycles(7, 13, DecisionNode.REWARD_CALIBRATION)

    switch = engine.maybe_switch_strategy()
    assert switch is not None
    assert switch.to_strategy == TrainingStrategy.RL
