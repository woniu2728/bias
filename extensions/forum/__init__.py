"""
论坛领域类型命名空间 —— 便捷导入入口。

论坛领域类型（PostType、DiscussionSort 等）当前定义在
``apps.core.forum_registry_types`` 中，以确保 core 不依赖 extensions 的架构约束。
长期方向是将这些类型下沉到本扩展中，届时可反转此导入方向。

用法::

    from extensions.forum import PostTypeDefinition, DiscussionSortDefinition
"""

from apps.core.forum_registry_types import (  # noqa: F401
    DiscussionListFilterApplier,
    DiscussionListFilterDefinition,
    DiscussionListQueryApplier,
    DiscussionListQueryDefinition,
    DiscussionSortApplier,
    DiscussionSortDefinition,
    PostTypeDefinition,
    SearchFilterApplier,
    SearchFilterDefinition,
    SearchFilterParser,
)
