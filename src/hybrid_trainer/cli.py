from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

from .engine import TrainingEngine
from .evaluation import AutoEvaluator, CommandAutoEvaluator, Evaluator
from .generation import CommandTaskGenerator, DatasetTaskGenerator, TaskGenerator
from .job_orchestration import JobOrchestrator, save_job_orchestrator
from .model_service import ModelServiceRegistry
from .pipeline import DecisionNode, PipelineConfig, TrainingPipeline
from .runtime_config import RuntimeConfig, load_runtime_config
from .decision_console import save_decision_console
from .human_review import load_review_decisions, save_review_batch, save_review_decisions
from .review_consensus import save_review_consensus
from .state import save_snapshot
from .strategy import TrainingStrategy
from .terminal_ui import collect_review_decisions, render_decision_console, render_review_batch
from .training_execution import CommandTrainingExecutor, SimulatedTrainingExecutor, TrainingExecutor
from .verifier import ReferenceAnswerVerifier, SimpleVerifier
from .web_console import save_decision_console_html


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run hybrid trainer MVP simulation")
    parser.add_argument("--start", type=int, default=1, help="start iteration")
    parser.add_argument("--end", type=int, default=10, help="end iteration")
    parser.add_argument(
        "--node",
        type=str,
        default=DecisionNode.REWARD_CALIBRATION.value,
        choices=[node.value for node in DecisionNode],
        help="decision node used during simulation",
    )
    parser.add_argument("--output", type=str, default="artifacts/run_summary.json", help="summary output path")
    parser.add_argument("--console-output", type=str, default="", help="optional decision console JSON path")
    parser.add_argument("--console-html-output", type=str, default="", help="optional decision console HTML path")
    parser.add_argument("--training-output", type=str, default="", help="optional training execution JSON path")
    parser.add_argument("--task-dataset", type=str, default="", help="optional JSON/JSONL task dataset path")
    parser.add_argument(
        "--external-generator-cmd",
        type=str,
        default="",
        help="optional external task generator command; reads JSON from stdin and returns JSON to stdout",
    )
    parser.add_argument(
        "--external-generator-timeout",
        type=int,
        default=30,
        help="timeout in seconds for the external task generator command",
    )
    parser.add_argument(
        "--external-evaluator-cmd",
        type=str,
        default="",
        help="optional external evaluator command; reads JSON from stdin and returns JSON to stdout",
    )
    parser.add_argument(
        "--external-evaluator-timeout",
        type=int,
        default=30,
        help="timeout in seconds for the external evaluator command",
    )
    parser.add_argument("--review-batch-output", type=str, default="", help="optional pending review batch JSON path")
    parser.add_argument("--review-decisions-output", type=str, default="", help="optional review decisions JSON output path")
    parser.add_argument("--review-consensus-output", type=str, default="", help="optional review consensus JSON output path")
    parser.add_argument(
        "--review-decisions-input",
        type=str,
        default="",
        help="optional human review decisions JSON path to apply before exporting artifacts",
    )
    parser.add_argument("--events-output", type=str, default="", help="optional events JSONL export path")
    parser.add_argument("--state-output", type=str, default="", help="optional state snapshot JSON path")
    parser.add_argument(
        "--job-orchestration-output",
        type=str,
        default="",
        help="optional orchestration job log JSON path",
    )
    parser.add_argument("--execute-training", action="store_true", help="run the current training strategy executor")
    parser.add_argument(
        "--external-training-cmd",
        type=str,
        default="",
        help="optional external training command; reads JSON from stdin and returns JSON to stdout",
    )
    parser.add_argument(
        "--external-training-timeout",
        type=int,
        default=120,
        help="timeout in seconds for the external training command",
    )
    parser.add_argument("--model-service-config", type=str, default="", help="optional model service registry JSON path")
    parser.add_argument("--generator-service", type=str, default="", help="named generator service from model registry")
    parser.add_argument("--evaluator-service", type=str, default="", help="named evaluator service from model registry")
    parser.add_argument("--training-service", type=str, default="", help="named training service from model registry")
    parser.add_argument("--print-console", action="store_true", help="render the decision console to stdout")
    parser.add_argument("--print-review-batch", action="store_true", help="render the selected review batch to stdout")
    parser.add_argument("--interactive-review", action="store_true", help="collect human review decisions interactively")
    parser.add_argument("--reviewer", type=str, default="cli_reviewer", help="reviewer name for interactive decisions")
    parser.add_argument(
        "--review-consensus-min-reviewers",
        type=int,
        default=1,
        help="minimum reviewer count required before consensus or arbitration is applied",
    )
    parser.add_argument(
        "--training-strategy",
        type=str,
        default="",
        choices=["", *[item.value for item in TrainingStrategy]],
        help="override strategy used for training execution",
    )
    parser.add_argument("--config", type=str, default="", help="optional runtime JSON config path")
    parser.add_argument(
        "--reference-verifier",
        action="store_true",
        help="use reference-answer verifier when tasks include reference answers",
    )
    parser.add_argument("--policy-version", type=str, default=None, help="override reward policy version")
    parser.add_argument("--approve-threshold", type=float, default=None, help="override reward approve threshold")
    parser.add_argument("--review-band", type=float, default=None, help="override reward review band")
    parser.add_argument(
        "--blocked-keyword",
        action="append",
        default=[],
        help="append a blocked keyword to the active reward policy",
    )
    parser.add_argument(
        "--trigger-min-samples",
        type=int,
        default=None,
        help="minimum sample count before major node recommendations activate",
    )
    parser.add_argument(
        "--failure-review-block-ratio",
        type=float,
        default=None,
        help="override block ratio threshold for failure review recommendation",
    )
    parser.add_argument(
        "--reward-calibration-review-ratio",
        type=float,
        default=None,
        help="override review ratio threshold for reward calibration recommendation",
    )
    parser.add_argument(
        "--curriculum-shift-approve-ratio",
        type=float,
        default=None,
        help="override approve ratio threshold for curriculum shift recommendation",
    )
    parser.add_argument("--review-budget", type=int, default=5, help="review budget for decision console export")
    parser.add_argument(
        "--active-learning-limit",
        type=int,
        default=5,
        help="active learning sample count for decision console export",
    )
    parser.add_argument(
        "--recent-events-limit",
        type=int,
        default=10,
        help="recent event count for decision console export",
    )
    return parser


def _resolve_runtime_config(ns: argparse.Namespace) -> RuntimeConfig:
    runtime_config = load_runtime_config(ns.config) if ns.config else RuntimeConfig()

    reward_policy = runtime_config.reward_policy
    if ns.policy_version is not None:
        reward_policy = replace(reward_policy, version=ns.policy_version)
    if ns.approve_threshold is not None:
        reward_policy = replace(reward_policy, approve_threshold=ns.approve_threshold)
    if ns.review_band is not None:
        reward_policy = replace(reward_policy, review_band=ns.review_band)
    if ns.blocked_keyword:
        combined_keywords = tuple(dict.fromkeys([*reward_policy.blocked_keywords, *ns.blocked_keyword]))
        reward_policy = replace(reward_policy, blocked_keywords=combined_keywords)

    trigger_rules = runtime_config.trigger_rules
    trigger_overrides = {}
    if ns.trigger_min_samples is not None:
        trigger_overrides["min_samples"] = ns.trigger_min_samples
    if ns.failure_review_block_ratio is not None:
        trigger_overrides["failure_review_block_ratio"] = ns.failure_review_block_ratio
    if ns.reward_calibration_review_ratio is not None:
        trigger_overrides["reward_calibration_review_ratio"] = ns.reward_calibration_review_ratio
    if ns.curriculum_shift_approve_ratio is not None:
        trigger_overrides["curriculum_shift_approve_ratio"] = ns.curriculum_shift_approve_ratio
    if trigger_overrides:
        trigger_rules = replace(trigger_rules, **trigger_overrides)

    return RuntimeConfig(reward_policy=reward_policy, trigger_rules=trigger_rules)


def _resolve_task_generator(ns: argparse.Namespace) -> TaskGenerator:
    service_registry = _resolve_model_services(ns)
    if ns.generator_service:
        service = service_registry.resolve(ns.generator_service, role="generator")
        return CommandTaskGenerator(
            service.command,
            timeout_seconds=service.timeout_seconds,
            service_name=service.name,
        )
    if ns.external_generator_cmd:
        return CommandTaskGenerator(
            ns.external_generator_cmd,
            timeout_seconds=ns.external_generator_timeout,
        )
    if ns.task_dataset:
        return DatasetTaskGenerator.from_file(ns.task_dataset)
    return TaskGenerator()


def _resolve_evaluator(ns: argparse.Namespace) -> Evaluator:
    service_registry = _resolve_model_services(ns)
    if ns.evaluator_service:
        service = service_registry.resolve(ns.evaluator_service, role="evaluator")
        return CommandAutoEvaluator(
            service.command,
            timeout_seconds=service.timeout_seconds,
            service_name=service.name,
        )
    if ns.external_evaluator_cmd:
        return CommandAutoEvaluator(
            ns.external_evaluator_cmd,
            timeout_seconds=ns.external_evaluator_timeout,
        )
    return AutoEvaluator()


def _resolve_verifier(ns: argparse.Namespace) -> SimpleVerifier:
    if ns.reference_verifier or ns.task_dataset:
        return ReferenceAnswerVerifier()
    return SimpleVerifier()


def _resolve_training_executor(ns: argparse.Namespace) -> TrainingExecutor:
    service_registry = _resolve_model_services(ns)
    if ns.training_service:
        service = service_registry.resolve(ns.training_service, role="training")
        return CommandTrainingExecutor(
            service.command,
            timeout_seconds=service.timeout_seconds,
            service_name=service.name,
        )
    if ns.external_training_cmd:
        return CommandTrainingExecutor(
            ns.external_training_cmd,
            timeout_seconds=ns.external_training_timeout,
        )
    return SimulatedTrainingExecutor()


def _resolve_model_services(ns: argparse.Namespace) -> ModelServiceRegistry:
    if not hasattr(ns, "_model_service_registry"):
        if ns.model_service_config:
            registry = ModelServiceRegistry.from_file(ns.model_service_config)
        else:
            registry = ModelServiceRegistry()

        if (ns.generator_service or ns.evaluator_service or ns.training_service) and not ns.model_service_config:
            raise ValueError("model service selectors require --model-service-config")
        setattr(ns, "_model_service_registry", registry)

    return getattr(ns, "_model_service_registry")


def _resolve_job_orchestrator(ns: argparse.Namespace) -> JobOrchestrator | None:
    if (
        ns.job_orchestration_output
        or ns.external_generator_cmd
        or ns.external_evaluator_cmd
        or ns.external_training_cmd
        or ns.generator_service
        or ns.evaluator_service
        or ns.training_service
    ):
        return JobOrchestrator()
    return None


def run(args: list[str] | None = None) -> Path:
    parser = build_parser()
    ns = parser.parse_args(args=args)

    runtime_config = _resolve_runtime_config(ns)
    engine = TrainingEngine(
        generator=_resolve_task_generator(ns),
        evaluator=_resolve_evaluator(ns),
        pipeline=TrainingPipeline(config=PipelineConfig(reward_policy=runtime_config.reward_policy)),
        trigger_rules=runtime_config.trigger_rules,
        training_executor=_resolve_training_executor(ns),
        verifier=_resolve_verifier(ns),
        job_orchestrator=_resolve_job_orchestrator(ns),
    )
    node = DecisionNode(ns.node)
    engine.run_cycles(ns.start, ns.end, node)

    if ns.review_decisions_input:
        loaded_decisions = load_review_decisions(ns.review_decisions_input)
        duplicate_iterations = len({item.iteration for item in loaded_decisions}) != len(loaded_decisions)
        if ns.review_consensus_min_reviewers > 1 or duplicate_iterations:
            min_reviewers = max(ns.review_consensus_min_reviewers, 2 if duplicate_iterations else 1)
            records = engine.apply_review_consensus(loaded_decisions, min_reviewers=min_reviewers)
            if ns.review_consensus_output:
                save_review_consensus(records, ns.review_consensus_output)
        else:
            engine.apply_review_decisions(loaded_decisions)

    review_batch = None
    if ns.review_batch_output or ns.print_review_batch or ns.interactive_review:
        review_batch = engine.get_review_batch(ns.review_budget)
        if ns.review_batch_output:
            save_review_batch(review_batch.items, ns.review_batch_output, budget=review_batch.budget)
            engine.tracker.track(
                event_type="review_batch_exported",
                payload={
                    "path": ns.review_batch_output,
                    "budget": review_batch.budget,
                    "selected": [item.iteration for item in review_batch.items],
                },
            )
        if ns.print_review_batch:
            print(render_review_batch(review_batch), end="")
        if ns.interactive_review:
            decisions = collect_review_decisions(review_batch, reviewer=ns.reviewer)
            if ns.review_decisions_output:
                save_review_decisions(decisions, ns.review_decisions_output)
            if decisions:
                engine.apply_review_decisions(decisions)

    dashboard = engine.generate_dashboard()
    drift = engine.analyze_reward_drift()
    cost = engine.analyze_cost()
    strategy_switch = engine.maybe_switch_strategy()
    curriculum_adv = engine.maybe_advance_curriculum()
    training_result = None
    if ns.execute_training or ns.training_output:
        target_strategy = TrainingStrategy(ns.training_strategy) if ns.training_strategy else None
        training_result = engine.execute_training(strategy=target_strategy, output_path=ns.training_output)

    payload = {
        "range": {"start": ns.start, "end": ns.end},
        "node": ns.node,
        "config": runtime_config.to_dict(),
        "inputs": {
            "task_dataset": ns.task_dataset or None,
            "generator": type(engine.generator).__name__,
            "evaluator": type(engine.evaluator).__name__,
            "verifier": type(engine.verifier).__name__,
            "training_executor": type(engine.training_executor).__name__,
            "external_generator_cmd": ns.external_generator_cmd or None,
            "external_evaluator_cmd": ns.external_evaluator_cmd or None,
            "external_training_cmd": ns.external_training_cmd or None,
            "model_service_config": ns.model_service_config or None,
            "generator_service": ns.generator_service or None,
            "evaluator_service": ns.evaluator_service or None,
            "training_service": ns.training_service or None,
        },
        "job_orchestration": engine.job_orchestrator.summary() if engine.job_orchestrator is not None else None,
        "human_review": {
            "pending": len(engine.review_queue.pending),
            "resolved": len(engine.review_queue.resolved),
        },
        "dashboard": dashboard.to_dict(),
        "reward_drift": {
            "total": drift.total,
            "approve": drift.approve,
            "review_or_block": drift.review_or_block,
            "drift_index": drift.drift_index,
        },
        "cost": {
            "total_iterations": cost.total_iterations,
            "auto_evaluation_cost": cost.auto_evaluation_cost,
            "human_review_cost": cost.human_review_cost,
            "total_cost": cost.total_cost,
        },
        "strategy": {
            "current": engine.strategy_manager.current.value,
            "switched": strategy_switch is not None,
        },
        "curriculum": {
            "stage": engine.curriculum_manager.current_stage.name,
            "advanced": curriculum_adv is not None,
        },
        "training_execution": training_result.to_dict() if training_result is not None else None,
    }

    output = Path(ns.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    console = None
    if ns.console_output or ns.console_html_output or ns.print_console:
        console = engine.generate_decision_console(
            review_budget=ns.review_budget,
            active_learning_limit=ns.active_learning_limit,
            recent_event_limit=ns.recent_events_limit,
        )

    if ns.console_output and console is not None:
        save_decision_console(console, ns.console_output)
    if ns.console_html_output and console is not None:
        save_decision_console_html(console, ns.console_html_output)
    if ns.print_console and console is not None:
        print(render_decision_console(console), end="")

    if ns.events_output:
        engine.tracker.export_jsonl(ns.events_output)

    if ns.state_output:
        save_snapshot(engine.snapshot_state(), ns.state_output)

    if ns.job_orchestration_output and engine.job_orchestrator is not None:
        save_job_orchestrator(engine.job_orchestrator, ns.job_orchestration_output)

    return output


def main() -> None:
    run()


if __name__ == "__main__":
    main()
