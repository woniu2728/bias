# ADR: Content Foundation Boundary

Status: accepted
Date: 2026-06-29

## Context

Bias was split into `bias`, `bias_core`, and `bias-ext-*` packages to move toward a Flarum-like architecture. The first split made `discussions` and `posts` independent feature extensions.

Runtime evidence shows that this boundary is wrong for the forum content domain:

- `posts` has a manifest dependency on `discussions`.
- `discussions` creates, updates, approves, rejects, resubmits, serializes, and deletes first posts through runtime facades owned by `posts`.
- Adding `posts` to the `discussions` manifest would create `discussions -> posts -> discussions`.
- `inspect_extension_imports --check-runtime-facades` now reports this as `runtime_facade_dependency_cycle`.

Flarum keeps `Discussion`, `Post`, discussion state, post numbering, first/last post metadata, visibility, policy, and search-facing content contracts in `flarum-core`. Tags, likes, flags, subscriptions, notifications, and approval behavior extend those core models.

## Decision

Bias should not keep `discussions` and `posts` as ordinary optional extensions.

The target structure is:

```text
bias_core
  Extension system, runtime host, SDK, resource registry, permission/policy infrastructure.

bias_content or bias_forum_foundation
  Required forum content domain:
  Discussion, Post, first post, replies, discussion user state, read state,
  post numbering, counted-content metadata, baseline visibility, baseline moderation lifecycle.

bias-users or protected bias-ext-users
  Required system user domain:
  User, group, permission assignment, preferences, suspension, account security,
  and user-facing identity/runtime services.

bias-ext-*
  Optional or feature extensions:
  tags, approval, notifications, likes, flags, subscriptions, uploads, mentions,
  search adapters, realtime adapters, and third-party extensions.
```

`bias_core` must stay a platform kernel. The forum content domain is product foundation, not extension infrastructure, so it should be a required foundation package rather than being absorbed into the platform kernel.

The user domain follows the same rule. Flarum keeps `User` in core, but Bias keeps `bias_core` smaller than Flarum core. User records, groups, permissions, preferences, and suspension are product/system domain behavior, so they should stay in a required protected system package (`bias-ext-users` today, potentially `bias-users` later) instead of moving into `bias_core`.

Search and realtime are infrastructure extensions, not foundation data domains. They may be auto-installed, protected, or bundled, but content and user hot paths should not depend on them for base behavior. They should attach through registered search targets, event listeners, and realtime transports.

## Performance Rationale

Discussion list and discussion detail paths need coherent query planning across discussion and post data:

- first post, last post, most relevant post;
- last posted user and discussion author;
- comment count and participant count;
- unread/read state;
- visibility and private-content filters;
- approval and hidden state.

Keeping these in separate ordinary extensions pushes query planning through runtime facades and makes preload ownership ambiguous. The foundation package should own the default ORM joins, prefetches, counters, and cache invalidation for these paths. Optional extensions can add resource fields, filters, lifecycle hooks, and event listeners without owning the base query plan.

## Migration Direction

1. Create a required content foundation package or module.
2. Move `Discussion`, `DiscussionUser`, `Post`, baseline post types, and first-post lifecycle into that foundation.
3. Replace `discussion.posts` runtime service with direct foundation-domain service calls.
4. Keep extension-facing public contracts stable where possible:
   - `discussions.service`;
   - `posts.service`;
   - event aliases such as `discussions.discussion.created` and `posts.post.created`;
   - resource names `discussion` and `post`.
5. Convert current `bias-ext-discussions` and `bias-ext-posts` into compatibility/feature layers only if they still own non-foundation behavior.
6. Then fix optional extension declarations for `approval`, `notifications`, `tags`, `search`, `flags`, and related integrations.

## Non-Goals

- Do not solve the cycle by adding reciprocal manifest dependencies.
- Do not move tags into the foundation. Flarum Tags is an extension and should remain one.
- Do not move all forum business into `bias_core`; that would make the platform SDK harder to reuse and test.

## Current Evidence

Run from `D:\files\project\tmp\bias`:

```powershell
python manage.py inspect_extension_imports --extensions-path D:\files\project\tmp --internal --check-runtime-facades --format json
```

The expected current result is failure while migration is incomplete. The important errors are:

- `runtime_facade_dependency_cycle` for `discussions -> posts -> discussions`;
- additional runtime cycles involving `discussions`, `search`, `tags`, and `flags`;
- undeclared optional/public contract dependencies in `approval` and `notifications`.

The `discussions/posts` cycle is the priority because it is the base content lifecycle. The other cycles should be fixed after the foundation boundary is corrected.
