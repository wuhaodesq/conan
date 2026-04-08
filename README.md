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
├── examples/
│   ├── external_evaluator.py
│   ├── external_trainer.py
│   ├── runtime_config.json
│   └── task_dataset.json
├── hybrid_self_improvement_training_plan.md
├── src/
│   └── hybrid_trainer/
│       ├── __init__.py
│       ├── active_learning.py
│       ├── cli.py
│       ├── command_backend.py
│       ├── cost.py
│       ├── curriculum.py
│       ├── decision_console.py
│       ├── engine.py
│       ├── evaluation.py
│       ├── experiment.py
│       ├── failure_analysis.py
│       ├── generation.py
│       ├── human_review.py
│       ├── metrics.py
│       ├── pipeline.py
│       ├── policy_registry.py
│       ├── report.py
│       ├── reward_drift.py
│       ├── reward_policy.py
│       ├── review_consensus.py
│       ├── review_router.py
│       ├── runtime_config.py
│       ├── search.py
│       ├── state.py
│       ├── strategy.py
│       ├── terminal_ui.py
│       ├── training_execution.py
│       ├── triggers.py
│       ├── verifier.py
│       └── web_console.py
└── tests/
    ├── test_cli.py
    ├── test_cli_artifacts.py
    ├── test_cost.py
    ├── test_curriculum.py
    ├── test_dataset_integration.py
    ├── test_decision_console.py
    ├── test_engine.py
    ├── test_external_backends.py
    ├── test_active_learning.py
    ├── test_experiment_tracker.py
    ├── test_failure_analysis.py
    ├── test_human_review_and_metrics.py
    ├── test_pipeline.py
    ├── test_policy_registry.py
    ├── test_review_router.py
    ├── test_search.py
    ├── test_report.py
    ├── test_review_consensus.py
    ├── test_reward_drift.py
    ├── test_reward_policy.py
    ├── test_state.py
    ├── test_strategy.py
    ├── test_terminal_ui.py
    ├── test_training_execution.py
    ├── test_triggers.py
    ├── test_verifier.py
    ├── test_runtime_config.py
    └── test_web_console.py
```

## 快速开始

1. 使用 Python 3.10+。
2. 安装开发依赖（可选）：`pip install pytest`
3. 运行测试：`pytest -q`
4. 运行模拟：`python -m hybrid_trainer.cli --start 1 --end 10`
5. 导出事件/状态：`python -m hybrid_trainer.cli --events-output artifacts/events.jsonl --state-output artifacts/state.json`
6. 使用运行时配置：`python -m hybrid_trainer.cli --config examples/runtime_config.json`
7. 导出人工决策台：`python -m hybrid_trainer.cli --console-output artifacts/decision_console.json`
8. 导出待审批次并回填人工结论：`python -m hybrid_trainer.cli --review-batch-output artifacts/review_batch.json --review-decisions-input artifacts/review_decisions.json`
9. 执行训练器并导出训练工件：`python -m hybrid_trainer.cli --execute-training --training-output artifacts/training_execution.json`
10. 使用任务数据集与参考答案 verifier：`python -m hybrid_trainer.cli --task-dataset examples/task_dataset.json --reference-verifier`
11. 终端交互式人工审批：`python -m hybrid_trainer.cli --print-console --print-review-batch --interactive-review --reviewer alice`
12. 导出可视化 HTML 决策台：`python -m hybrid_trainer.cli --console-html-output artifacts/decision_console.html`
13. 多评审一致性与冲突仲裁：`python -m hybrid_trainer.cli --review-decisions-input artifacts/review_decisions.json --review-consensus-min-reviewers 2 --review-consensus-output artifacts/review_consensus.json`
14. 接入外部评估器与训练后端：`python -m hybrid_trainer.cli --task-dataset examples/task_dataset.json --reference-verifier --external-evaluator-cmd "[\"python\", \"examples/external_evaluator.py\"]" --external-training-cmd "[\"python\", \"examples/external_trainer.py\"]" --execute-training --training-output artifacts/training_execution.json`

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
- 成本分析：支持估算自动评估与人工复核成本并输出到运行摘要。
- Reward 策略注册表：支持策略版本注册与激活切换，便于回溯与灰度。
- 多路径搜索：支持在单轮中采样多条候选路径并选择最优路径。
- 运行时配置：支持通过 JSON/CLI 覆盖 reward policy 与节点触发规则，并将配置写入运行摘要。
- 人工决策台 v1：支持聚合 review 队列、失败诊断、主动学习候选、策略/课程/策略版本与近期事件，并导出 JSON 工件。
- 审批回填流：支持导出 review batch、导入人工结论 JSON，并在决策台与运行摘要中回填 resolved 状态。
- 训练执行器闭环：支持按当前 SFT/RL/DPO 策略执行模拟训练任务，并将结果写入训练工件、运行摘要与实验事件日志。
- 数据接入型 generator/verifier：支持从 JSON/JSONL 任务集加载任务样本，并使用参考答案校验式 verifier 驱动更真实的任务验证。
- 终端交互式决策台：支持将 console/review batch 渲染为人可读文本，并在 CLI 中逐条录入人工审批结论。
- 可视化 HTML 决策台：支持从同一份 decision console 数据导出可离线打开、可分享的 Web 风格运营视图。
- 多评审一致性与仲裁：支持按 iteration 聚合多位 reviewer 的投票结果，输出共识记录，并在冲突时采取保守仲裁。
- 外部命令后端：支持通过 stdin/stdout JSON 协议接入更真实的自动评估器与训练执行器，并保留运行摘要、训练工件与 CLI 工作流。

## 后续可选方向

- 接入真实的任务分发队列、模型服务和异步作业编排。
- 为人工决策台补充 Web 端审批回填与权限管理。
