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
│       └── pipeline.py
└── tests/
    └── test_pipeline.py
```

## 快速开始

1. 使用 Python 3.10+。
2. 安装开发依赖（可选）：`pip install pytest`
3. 运行测试：`pytest -q`

## 下一步开发方向

- 接入真实 task generator/verifier。
- 引入可配置 reward policy 与版本管理。
- 打通 SFT/RL 训练执行器与实验日志。
