# 事件订阅指南

## 目标

领域事件用于把主流程和副作用解耦。通知、统计刷新、审核后处理都应优先走事件总线。

## 步骤

1. 先确认已有事件是否可复用。
2. 在模块定义里补 `EventListenerDefinition`。
3. 监听器内部保持幂等，避免重复消费。
4. 对通知、审计、聚合字段刷新补回归测试。

## 入口

- `apps/core/forum_events.py`
- `apps/core/domain_events.py`
- `apps/core/forum_event_listeners.py`
