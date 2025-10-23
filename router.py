# -*- coding: utf-8 -*-
"""
tips/router.py - 个性化体检提示路由

功能：根据用户信息生成个性化的体检前注意事项

并发安全设计：
✅ 已改进：每次请求创建新的Agent实例
- 完全无状态，支持水平扩展
- 避免多用户并发时的状态污染
- 与recom2保持一致的架构设计
"""

from fastapi import APIRouter

from .schemas import TipsBatchIn, TipsBatchOut
from .agent import PersonalizedTipsAgent

router = APIRouter(prefix="/api/v1/tips", tags=["tips"])

# ✅ 已移除全局单例，改为每次请求创建新实例（见下方路由函数）

@router.post("/personalized_batch", response_model=TipsBatchOut)
def tips_batch(payload: TipsBatchIn) -> TipsBatchOut:
    """批量生成个性化体检提示
    
    功能：根据到检名单批量生成个性化注意事项
    
    用户区分：
    - payload.user_id: 业务层面的用户标识
    - 生成的trace_id: 系统追踪ID
    - payload.persons: 多个体检人员信息列表
    
    并发安全：
    - ✅ 每次请求创建新的Agent实例（无状态架构）
    - ✅ 不同用户的请求完全隔离，线程安全
    - ✅ 支持水平扩展，与recom2保持一致
    
    注意事项：
    - 独立于recom2，不依赖推荐结果
    - 基于规则引擎生成提示，非大模型LLM
    """
    # ✅ 并发安全关键：每次请求创建新的Agent实例
    # 优点：
    # - 完全无状态，支持水平扩展
    # - 避免多用户并发时的状态污染
    # - 每个请求独立处理，互不影响
    # - 与 recom2 保持一致的设计模式
    agent = PersonalizedTipsAgent()
    return agent.run_batch(payload)