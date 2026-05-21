# Codebase Index

Full module inventory is in `/.claude/rules/architecture.md`. This file is a decision map (where to edit by task type) and a debug index (where to look by symptom).

## Decision Map

Change topic/window routing:

- `src/ccgram/session.py` for bindings + state model.
- `src/ccgram/handlers/callback_helpers.py` for thread/window extraction.
- `src/ccgram/window_resolver.py` for stale ID re-resolution.

Change monitor/event dispatch:

- `src/ccgram/session_monitor.py` for polling + fan-out.
- `src/ccgram/monitor_state.py` for byte-offset persistence.
- `src/ccgram/handlers/hook_events.py` for hook event handling.

Change provider behavior (commands, parsing, capabilities):

- `src/ccgram/providers/base.py` for contract + capabilities.
- `src/ccgram/providers/__init__.py` for per-window resolution.
- `src/ccgram/providers/{claude,codex,gemini,pi,shell}.py` for provider behavior.
- `src/ccgram/providers/pi_discovery.py` + `pi_format.py` for Pi command discovery + transcript parsing.
- `src/ccgram/providers/codex_format.py` for interactive prompt text normalization.

Change shell command generation:

- `src/ccgram/llm/` for backend selection, prompt construction, result parsing.
- `src/ccgram/handlers/shell/shell_commands.py` for approval keyboard + raw `!` execution.

Add a new LLM provider:

- Entry in `src/ccgram/llm/__init__.py` `_PROVIDERS` (`base_url`, `model`, `api_key_env`). Temperature passes through automatically. OpenAI-compatible needs no completer code; otherwise extend `_BaseCompleter` in `httpx_completer.py`.

Change Telegram interactive UX:

- `src/ccgram/handlers/interactive/interactive_ui.py` + `interactive_callbacks.py`.
- `src/ccgram/handlers/callback_data.py` for callback key contracts.
- `src/ccgram/handlers/messaging_pipeline/message_queue.py` for ordering/merge.
- `src/ccgram/handlers/live/live_view.py` for live view sessions.

Change command discovery / menu:

- `src/ccgram/command_catalog.py` for filesystem scan + caching.
- `src/ccgram/cc_commands.py` for Telegram menu registration.
- `src/ccgram/handlers/commands/menu_sync.py` for scoped per-window menu sync.

Change `/commands` failure probe / status snapshot:

- `src/ccgram/handlers/commands/failure_probe.py` for transcript-based failure detection.
- `src/ccgram/handlers/commands/status_snapshot.py` for status snapshot delegation.

Change recovery UX:

- `src/ccgram/handlers/recovery/recovery_banner.py` — dead-window banner UX.
- `src/ccgram/handlers/recovery/resume_picker.py` — resume picker UX + transcript scan.
- `src/ccgram/handlers/recovery/recovery_callbacks.py` is a thin dispatcher only; do not add UX logic here.

Change polling types vs strategies:

- `src/ccgram/handlers/polling/polling_types.py` — contracts only (stdlib + `providers.base.StatusUpdate`).
- `src/ccgram/handlers/polling/polling_state.py` — strategies + module-level singletons.

Change tool-call visibility (hide/show `tool_use`/`tool_result`):

- `src/ccgram/window_state_store.py`: `tool_call_visibility` field (`default`/`shown`/`hidden`).
- `src/ccgram/handlers/messaging_pipeline/message_queue.py` (`_handle_content_task`): visibility gate before batch eligibility; hidden entries dropped before `_tool_msg_ids` registration. Hook events bypass via `StatusUpdateTask`.
- `/toolcalls` command in `src/ccgram/handlers/messaging_pipeline/topic_commands.py` cycles mode via `WindowStateStore`.

Change topic emoji color scheme:

- `src/ccgram/handlers/status/topic_emoji.py` maps internal status (`active`/`idle`/`done`/`dead`) to Telegram color via `CCGRAM_STATUS_MODE`. Add modes by extending the mode→colorname dispatch.

Change PTB handler registration / lifecycle:

- `src/ccgram/handlers/registry.py` for command/message/callback/inline handler wiring.
- `src/ccgram/bootstrap.py` for `post_init` + `post_shutdown`. Respect ordering: `wire_runtime_callbacks` before `start_session_monitor`.
- `src/ccgram/bot.py` is factory + lifecycle delegate only; do not push wiring back into it.

Change Telegram bot API surface:

- `src/ccgram/telegram_client.py`: add Protocol methods only when a handler needs them; mirror in `PTBTelegramClient` (delegation) and `FakeTelegramClient` (recording + default return). Never import `telegram.Bot` from inside `handlers/`.

Change screenshot rendering: `src/ccgram/screenshot.py` only.

Change tmux behavior: `src/ccgram/tmux_manager.py` only.

## Change Mapping by Task Type

Add or change a Telegram command:

1. Wire in `handlers/registry.py` (`command_specs` list).
2. Implement in `handlers/<subpackage>/` (or top-level for cross-cutting).
3. Add callback constants in `handlers/callback_data.py` if needed.
4. Take `client: TelegramClient` (never `bot: Bot`).

Change session binding logic:

- `session.py` + `window_resolver.py`. Validate persistence compatibility in `tests/ccgram/test_state_migration.py`.

Adjust transcript/status parsing:

- Provider-specific in `providers/*.py`. Shared in `transcript_parser.py` / `terminal_parser.py`.

Touch tmux behavior: `tmux_manager.py` only.

Add or change live view:

- `handlers/live/live_view.py` for view sessions + ticking.
- `handlers/polling/periodic_tasks.py` for tick scheduling.
- `handlers/live/screenshot_callbacks.py` for the Live button.

## Contracts You Must Not Break

- Topic-window identity 1:1, window-id keyed.
- tool-use ↔ tool-result pairing + in-order delivery.
- Provider logic behind interfaces/capabilities.
- Parsing full-fidelity; split only in send path.
- `handlers/user_state.py` constants for `context.user_data`; no raw string keys.
- Handlers depend on `TelegramClient` Protocol, not `telegram.Bot`. Runtime `telegram.ext` import allowed only in `bot.py`, `bootstrap.py`, `handlers/registry.py`, `telegram_client.py`, `telegram_request.py`, `telegram_sender.py`.
- `SessionManager` constructs stores via constructor DI; no `_wire_singletons` or `unwired_save`.
- `bot.py` stays a factory + lifecycle delegate. Wiring in `bootstrap.py`; PTB registration in `handlers/registry.py`.

## Debug Index

Symptom: messages routed to wrong topic/window

- Inspect `thread_bindings` and window IDs in `session.py`.
- Confirm callback/thread ID extraction in `handlers/callback_helpers.py`.

Symptom: no new assistant messages

- Inspect `session_monitor.py` byte offsets + session map updates.
- Verify provider parser compatibility for that window/provider.

Symptom: interactive keyboard not shown

- Inspect `handlers/interactive/interactive_ui.py` + provider `parse_terminal_status` output.
- Check hook path (`hook.py` → `handlers/hook_events.py`) for Claude.

Symptom: duplicated or out-of-order status/content messages

- Inspect merge/send behavior in `handlers/messaging_pipeline/message_queue.py`.

Symptom: commands menu missing/wrong

- Check `command_catalog.py` cache TTL + filesystem scan paths.
- Check `cc_commands.py` menu registration + provider scoping.

Symptom: live view not refreshing

- Inspect `handlers/live/live_view.py` active views dict + tick interval.
- Check `handlers/polling/periodic_tasks.py` for tick scheduling.
- Verify screenshot capture in `screenshot.py` and tmux pane availability.

Symptom: `RuntimeError("... not wired")` or `RuntimeError("... already registered")` at startup

- Check `handlers/hook_events.register_stop_callback`, `handlers/status/status_bubble.register_rc_active_provider`, or `handlers/shell/shell_capture.register_approval_callback` — the wire-once/fail-loud contract raises if callee invoked before registration or if registered twice.
- Verify `bootstrap.wire_runtime_callbacks` runs before `bootstrap.start_session_monitor`. Monitor checks `_callbacks_wired`.
- In tests, the autouse fixture `_reset_runtime_callbacks` (in `tests/ccgram/handlers/conftest.py` and `tests/e2e/conftest.py`) resets these between tests; missing fixture is a test-setup bug.

Symptom: import cycle / partial-init from a clean interpreter

- Run `make test-integration` and watch `tests/integration/test_import_no_cycles.py` — parametrizes `python -c "import {module}"` over all 162 modules under `src/ccgram/`; surfaces the offending path.
- Legitimate cycles are annotated `# Lazy: <cycle path>` at the in-function import; do not blindly hoist them — `make lint` runs `lint-lazy` which fails on undocumented late imports.

Symptom: `lint-lazy` fails ("undocumented in-function import")

- The in-function import lacks a `# Lazy: <reason>` comment immediately preceding it. Either hoist (verify with `python -c "import {module}"`) or annotate citing the cycle path or wiring contract. See `scripts/lint_lazy_imports.py`.

Symptom: `test_query_layer_only_for_handlers` fails

- A handler file added a new `session_manager.<attr>` not on the write/admin allow-list. Either route through `window_query` / `session_query`, or add to the allow-list constant if it is genuinely a write/admin call.

Symptom: `test_polling_types_purity` fails

- `polling_types.py` imported a stateful module (likely `polling_state.py` or another non-stdlib besides `ccgram.providers.base`). Move the offending import to `polling_state.py` or to the call site.
