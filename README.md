# Hybrid Self-Improvement Trainer

一个面向“自动闭环为主、关键节点人工决策为辅”的推理模型训练原型项目。

## 当前项目状态

本仓库当前处于 **MVP 原型阶段**，目标是先把训练控制流与关键模块边界搭起来，后续逐步替换为真实的数据、评估器与训练器。

## 项目目标

- 构建自动化训练闭环：数据生成 → 自动评估 → 策略更新。
- 在关键节点引入人工决策：奖励校准、失败模式诊断、课程迁移。
- 以最小成本验证混合式策略是否优于纯自动基线。

## 目录结构

```text
.
├── README.md
├── hybrid_self_improvement_training_plan.md
├── src/
│   └── hybrid_trainer/
│       ├── __init__.py
│       ├── active_learning.py
│       ├── cli.py
│       ├── curriculum.py
│       ├── engine.py
│       ├── evaluation.py
│       ├── experiment.py
│       ├── failure_analysis.py
│       ├── generation.py
│       ├── human_review.py
│       ├── metrics.py
│       ├── pipeline.py
│       ├── report.py
│       ├── reward_drift.py
│       ├── reward_policy.py
│       ├── review_router.py
│       ├── state.py
│       ├── strategy.py
│       ├── triggers.py
│       └── verifier.py
└── tests/
    ├── test_cli.py
    ├── test_cli_artifacts.py
    ├── test_curriculum.py
    ├── test_engine.py
    ├── test_active_learning.py
    ├── test_experiment_tracker.py
    ├── test_failure_analysis.py
    ├── test_human_review_and_metrics.py
    ├── test_pipeline.py
    ├── test_review_router.py
    ├── test_report.py
    ├── test_reward_drift.py
    ├── test_reward_policy.py
    ├── test_state.py
    ├── test_strategy.py
    ├── test_triggers.py
    └── test_verifier.py
```

## 快速开始

1. 使用 Python 3.10+。
2. 安装开发依赖（可选）：`pip install pytest`
3. 运行测试：`pytest -q`
4. 运行模拟：`python -m hybrid_trainer.cli --start 1 --end 10`
5. 导出事件/状态：`python -m hybrid_trainer.cli --events-output artifacts/events.jsonl --state-output artifacts/state.json`

## 当前已完成的开发

- MVP 控制流：`TaskGenerator -> AutoEvaluator -> TrainingPipeline`。
- 训练引擎：`TrainingEngine.run_cycle/run_cycles` 支持单轮与区间执行。
- 决策路由：支持 `approve/review/block` 三种分流策略。
- 人工复核队列：自动收集 `review/block` 样本并支持人工结论回填。
- 指标汇总：支持按历史迭代统计三类决策占比。
- 节点触发建议：根据过程指标自动推荐下一步人工重大节点。
- 策略切换建议：基于指标自动评估是否在 SFT/RL/DPO 间切换。
- 实验追踪：记录 cycle/metrics/recommendation/strategy 事件并导出 JSONL。
- Reward 策略版本化：支持阈值与黑名单词规则热更新。
- 课程迁移管理：根据通过率自动尝试从 foundation 提升到更高阶段。
- CLI 运行入口：支持按迭代区间执行并导出 run summary JSON。
- 状态快照：支持保存/恢复关键运行状态（策略、课程阶段、历史计数）。
- 人工审核路由：支持按风险排序并在预算约束下选择高优先级样本。
- 主动学习候选：支持从历史中自动筛选最不确定样本用于重点标注。
- Verifier 交叉检查：支持在评估器与验证器分歧过大时强制进入人工复核。
- 失败模式诊断：支持按 taxonomy 统计低分阻断/策略阻断/验证器复核等失败类型。
- 决策看板：支持聚合 metrics/failures/recommendations 生成可视化友好的 dashboard 数据。
- Reward 漂移分析：支持计算 drift index 并输出到运行摘要。
- 工件导出：CLI 支持额外导出事件 JSONL 与运行状态快照 JSON。

## 下一步开发方向

- 接入真实 task generator/verifier。
- 引入可配置 reward policy 与版本管理。
- 打通 SFT/RL 训练执行器与实验日志。
- 增加人工决策台与节点触发规则配置。
