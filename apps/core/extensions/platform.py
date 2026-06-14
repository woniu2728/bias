from __future__ import annotations

from apps.core.audit import log_admin_action
from apps.core.auth import AuthBearer, get_optional_user
from apps.core.authorization import (
    AuthorizationDecision,
    AuthorizationPolicy,
    allow,
    assert_can,
    can,
    deny,
    force_allow,
    force_deny,
)
from apps.core.domain_events import (
    DomainEvent,
    DomainEventBus,
    dispatch_forum_event_after_commit,
    get_forum_event_bus,
)
from apps.core.api_errors import api_error
from apps.core.extension_settings_service import (
    build_extension_settings_defaults,
    get_extension_settings,
    save_extension_settings,
    serialize_extension_settings_schema,
)
from apps.core.extensions.policy_runtime_service import evaluate_extension_policy
from apps.core.email_service import EmailService
from apps.core.file_service import FileUploadService
from apps.core.forum_permissions import has_forum_permission
from apps.core.jwt_auth import (
    ACCESS_TOKEN_COOKIE_NAME,
    ACCESS_TOKEN_COOKIE_PATH,
    REFRESH_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_COOKIE_PATH,
    AccessTokenAuth,
    access_token_max_age,
    refresh_token_max_age,
)
from apps.core.resource_api import (
    ResourceQueryOptions,
    apply_resource_preloads,
    merge_resource_includes,
    parse_csv_param,
    parse_resource_query_options,
)
from apps.core.resource_errors import (
    BadJsonApiRequest,
    JsonApiConflict,
    JsonApiError,
    JsonApiErrorItem,
    JsonApiForbidden,
    JsonApiValidationError,
    jsonapi_error_response,
)
from apps.core.mail_drivers import can_mail_driver_send, send_with_extension_mail_driver
from apps.core.markdown_service import MarkdownService
from apps.core.queue_service import QueueService
from apps.core.services import PaginationService
from apps.core.settings_service import (
    get_advanced_settings,
    get_advanced_settings_defaults,
    get_mail_settings_defaults,
    get_setting_group,
)
from apps.core.storage_service import get_storage_backend
from apps.core.visibility import (
    apply_model_visibility_scope,
    apply_related_model_visibility_subquery,
    can_view_model_instance,
)

__all__ = [
    "AccessTokenAuth",
    "ACCESS_TOKEN_COOKIE_NAME",
    "ACCESS_TOKEN_COOKIE_PATH",
    "AuthBearer",
    "AuthorizationDecision",
    "AuthorizationPolicy",
    "BadJsonApiRequest",
    "DomainEvent",
    "DomainEventBus",
    "EmailService",
    "FileUploadService",
    "JsonApiConflict",
    "JsonApiError",
    "JsonApiErrorItem",
    "JsonApiForbidden",
    "JsonApiValidationError",
    "MarkdownService",
    "PaginationService",
    "QueueService",
    "REFRESH_TOKEN_COOKIE_NAME",
    "REFRESH_TOKEN_COOKIE_PATH",
    "ResourceQueryOptions",
    "access_token_max_age",
    "allow",
    "api_error",
    "apply_model_visibility_scope",
    "apply_related_model_visibility_subquery",
    "apply_resource_preloads",
    "assert_can",
    "build_extension_settings_defaults",
    "can",
    "can_view_model_instance",
    "can_mail_driver_send",
    "deny",
    "dispatch_forum_event_after_commit",
    "evaluate_extension_policy",
    "force_allow",
    "force_deny",
    "get_extension_settings",
    "get_advanced_settings",
    "get_advanced_settings_defaults",
    "get_forum_event_bus",
    "get_mail_settings_defaults",
    "get_optional_user",
    "get_setting_group",
    "get_storage_backend",
    "has_forum_permission",
    "jsonapi_error_response",
    "log_admin_action",
    "merge_resource_includes",
    "parse_csv_param",
    "parse_resource_query_options",
    "refresh_token_max_age",
    "save_extension_settings",
    "send_with_extension_mail_driver",
    "serialize_extension_settings_schema",
]
