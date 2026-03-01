from __future__ import annotations

import argparse
import inspect
import os
from pathlib import Path
import sys
from typing import Any, Callable

import uvicorn

from vibecheck.app import create_app
from vibecheck.bridge import SessionBridge, VibeRuntime, load_vibe_runtime, session_manager
from vibecheck.tui_bridge import TuiBridge

try:
    from vibe.core.autocompletion.path_prompt_adapter import (
        render_path_prompt as _render_path_prompt,
    )
except Exception:  # pragma: no cover - exercised when Vibe is unavailable

    def _render_path_prompt(prompt: str, base_dir: Path) -> str:
        _ = base_dir
        return prompt


def _fallback_vibe_parser(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run vibecheck live attach")
    parser.add_argument("initial_prompt", nargs="?", default=None)
    parser.add_argument("--teleport", action="store_true")
    parser.add_argument("--agent", default="default")
    parser.add_argument("--enabled-tools", action="append", default=None)
    return parser.parse_args(argv)


def parse_launcher_args(argv: list[str] | None = None) -> tuple[argparse.Namespace, int]:
    raw_args = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--ws-port", type=int, default=7870)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--log-file", default="")
    known, remaining = parser.parse_known_args(raw_args)

    try:
        from vibe.cli.entrypoint import parse_arguments as parse_vibe_args

        original_argv = sys.argv
        sys.argv = [original_argv[0], *remaining]
        try:
            vibe_args = parse_vibe_args()
        finally:
            sys.argv = original_argv
    except Exception:
        vibe_args = _fallback_vibe_parser(remaining)

    setattr(vibe_args, "vibecheck_debug", bool(known.debug))
    setattr(vibe_args, "vibecheck_log_file", str(known.log_file or "").strip())
    return vibe_args, known.ws_port


def build_uvicorn_config(app: Any, port: int) -> uvicorn.Config:
    return uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
        ws="websockets",
    )


def _unlock_vibe_config_paths() -> None:
    """Unlock Vibe config path access when running outside vibe.cli.entrypoint.main."""
    try:
        from vibe.core.paths.config_paths import unlock_config_paths
    except Exception:
        return

    try:
        unlock_config_paths()
    except Exception:
        return


def _load_vibe_dotenv_values() -> None:
    """Mirror Vibe's CLI behavior by loading `~/.vibe/.env` into `os.environ`."""
    try:
        from vibe.core.config import load_dotenv_values
    except Exception:
        return

    try:
        load_dotenv_values()
    except Exception:
        return


def _has_model_alias(config: object, alias: str) -> bool:
    models = getattr(config, "models", None)
    if not isinstance(models, list):
        return False
    return any(getattr(model, "alias", None) == alias for model in models)


def _active_model_provider(config: object) -> str | None:
    get_active_model = getattr(config, "get_active_model", None)
    get_provider_for_model = getattr(config, "get_provider_for_model", None)
    if callable(get_active_model) and callable(get_provider_for_model):
        try:
            model = get_active_model()
            provider = get_provider_for_model(model)
        except Exception:
            provider = None
            model = None
        else:
            provider_name = getattr(provider, "name", None)
            if isinstance(provider_name, str) and provider_name:
                return provider_name
            model_provider = getattr(model, "provider", None)
            if isinstance(model_provider, str) and model_provider:
                return model_provider

    active_alias = getattr(config, "active_model", None)
    models = getattr(config, "models", None)
    if not isinstance(active_alias, str) or not isinstance(models, list):
        return None

    for model in models:
        if getattr(model, "alias", None) == active_alias:
            provider_name = getattr(model, "provider", None)
            if isinstance(provider_name, str) and provider_name:
                return provider_name
    return None


def _maybe_prefer_mistral_devstral2(config: object) -> None:
    """Prefer Mistral's Devstral 2 model when an API key is present.

    This avoids surprising llamacpp failures (and avoids needing a local llama-server)
    when the user already has `MISTRAL_API_KEY` available.

    Users can force a specific model by exporting `VIBE_ACTIVE_MODEL`.
    """

    if os.getenv("VIBE_ACTIVE_MODEL"):
        return
    if not os.getenv("MISTRAL_API_KEY"):
        return

    active_alias = getattr(config, "active_model", None)
    if not isinstance(active_alias, str) or not active_alias:
        return

    if active_alias == "devstral-2":
        return

    provider = _active_model_provider(config)
    if provider != "llamacpp":
        return

    if not _has_model_alias(config, "devstral-2"):
        return

    try:
        setattr(config, "active_model", "devstral-2")
    except Exception:
        return


def _resolve_base_css_path() -> str | None:
    base_css = getattr(_BaseVibeApp, "CSS_PATH", None)
    if not isinstance(base_css, str) or not base_css:
        return None

    module_name = getattr(_BaseVibeApp, "__module__", "")
    module = sys.modules.get(module_name)
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str) or not module_file:
        return base_css

    return str(Path(module_file).resolve().with_name(base_css))


try:
    from vibe.cli.textual_ui.app import VibeApp as _BaseVibeApp
except Exception:  # pragma: no cover - covered via tests using fake app class

    class _BaseVibeApp:  # type: ignore[override]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.agent_loop = _kwargs.get("agent_loop")
            self.event_handler = None
            self._loading_widget = None

        def run(self) -> str | None:
            raise RuntimeError("Vibe Textual UI is unavailable")

        def run_worker(self, _worker: Any, *, exclusive: bool = False) -> None:
            _ = exclusive
            if inspect.isawaitable(_worker):
                close = getattr(_worker, "close", None)
                if callable(close):
                    close()


class VibeCheckApp(_BaseVibeApp):
    # Preserve Vibe's stylesheet location when subclassing from a different module.
    CSS_PATH = _resolve_base_css_path()

    def __init__(
        self,
        *,
        agent_loop: object,
        bridge,
        ws_port: int,
        api_app: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(agent_loop=agent_loop, **kwargs)
        self._bridge = bridge
        self._ws_port = ws_port
        self._api_app = api_app
        self._tui_bridge: TuiBridge | None = None
        self._server: uvicorn.Server | None = None
        self._set_approval_callback_original: Callable[[object], object] | None = None
        self._set_user_input_callback_original: Callable[[object], object] | None = None

    @staticmethod
    def _callbacks_match(candidate: object, target: object) -> bool:
        if candidate is target:
            return True
        candidate_func = getattr(candidate, "__func__", None)
        target_func = getattr(target, "__func__", None)
        candidate_self = getattr(candidate, "__self__", None)
        target_self = getattr(target, "__self__", None)
        return (
            candidate_func is not None
            and target_func is not None
            and candidate_func is target_func
            and candidate_self is target_self
        )

    def _bind_bridge_callbacks(self) -> None:
        approval_callback = getattr(self.agent_loop, "approval_callback", None)
        input_callback = getattr(self.agent_loop, "user_input_callback", None)

        self._bridge.attach_to_loop(
            self.agent_loop,
            approval_callback=approval_callback,
            input_callback=input_callback,
        )

    def _install_callback_interceptors(self) -> None:
        if self._set_approval_callback_original is not None:
            return

        set_approval = getattr(self.agent_loop, "set_approval_callback", None)
        set_input = getattr(self.agent_loop, "set_user_input_callback", None)
        if not callable(set_approval) or not callable(set_input):
            return

        self._set_approval_callback_original = set_approval
        self._set_user_input_callback_original = set_input

        def intercepted_set_approval(callback: object) -> object:
            if not self._callbacks_match(callback, self._bridge._approval_callback):  # noqa: SLF001
                self._bridge.configure_local_callbacks(
                    approval_callback=callback if callable(callback) else None,
                    input_callback=self._bridge.local_input_callback,
                )
            return self._set_approval_callback_original(self._bridge._approval_callback)

        def intercepted_set_user_input(callback: object) -> object:
            if not self._callbacks_match(callback, self._bridge._user_input_callback):  # noqa: SLF001
                self._bridge.configure_local_callbacks(
                    approval_callback=self._bridge.local_approval_callback,
                    input_callback=callback if callable(callback) else None,
                )
            return self._set_user_input_callback_original(self._bridge._user_input_callback)

        setattr(self.agent_loop, "set_approval_callback", intercepted_set_approval)
        setattr(self.agent_loop, "set_user_input_callback", intercepted_set_user_input)

    async def on_mount(self) -> None:
        if hasattr(super(), "on_mount"):
            await super().on_mount()

        self._bind_bridge_callbacks()
        self._install_callback_interceptors()
        self._bridge.prime_message_worker()

        if getattr(self, "event_handler", None) is not None:
            self._tui_bridge = TuiBridge(
                self.event_handler,
                loading_state_getter=lambda: getattr(self, "_loading_widget", None) is not None,
                loading_widget_getter=lambda: getattr(self, "_loading_widget", None),
                mount_user_message=self._mount_user_message,
            )
            self._bridge.add_raw_event_listener(self._tui_bridge.on_bridge_raw_event)

        if hasattr(self, "run_worker"):
            self.run_worker(self._run_server(), exclusive=False)

    async def _run_server(self) -> None:
        config = build_uvicorn_config(self._api_app, self._ws_port)
        self._server = uvicorn.Server(config)
        try:
            await self._server.serve()
        finally:
            self._server = None

    async def _mount_user_message(self, content: str) -> None:
        if not content.strip():
            return

        mount_and_scroll = getattr(self, "_mount_and_scroll", None)
        if not callable(mount_and_scroll):
            return

        try:
            from vibe.cli.textual_ui.widgets.messages import UserMessage
        except Exception:
            return

        maybe_awaitable = mount_and_scroll(UserMessage(content))
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    async def _handle_agent_loop_turn(self, prompt: str) -> None:
        # Intentional parity tradeoff: the bridge queue serializes turns, but this
        # bypasses Vibe's native loading widget / interrupt / history refresh path.
        # See docs/ANALYSIS-session-attachment.md (Phase 3 Validation: Gap 3).
        try:
            rendered_prompt = _render_path_prompt(prompt, base_dir=Path.cwd())
        except Exception:
            rendered_prompt = prompt

        injected = self._bridge.inject_message(rendered_prompt)
        if injected:
            if self._tui_bridge is not None:
                self._tui_bridge.mark_local_user_message(rendered_prompt)
            return

        # Keep a visible failure path in the terminal when bridge injection fails.
        if hasattr(self, "notify"):
            self.notify("Bridge failed to inject message", severity="error")

    async def on_unmount(self) -> None:
        if self._tui_bridge is not None:
            self._bridge.remove_raw_event_listener(self._tui_bridge.on_bridge_raw_event)
            self._tui_bridge = None
        if self._server is not None:
            self._server.should_exit = True

        if hasattr(super(), "on_unmount"):
            await super().on_unmount()


def _build_agent_loop(
    vibe_args: argparse.Namespace,
    runtime: VibeRuntime,
    message_observer: Callable[[object], None] | None = None,
):
    _unlock_vibe_config_paths()
    _load_vibe_dotenv_values()
    config = runtime.vibe_config_cls.load()
    _maybe_prefer_mistral_devstral2(config)

    enabled_tools = getattr(vibe_args, "enabled_tools", None)
    if enabled_tools and hasattr(config, "enabled_tools"):
        config.enabled_tools = enabled_tools

    kwargs: dict[str, Any] = {
        "agent_name": getattr(vibe_args, "agent", "default"),
        "enable_streaming": True,
    }
    if message_observer is not None:
        kwargs["message_observer"] = message_observer

    try:
        loop = runtime.agent_loop_cls(config, **kwargs)
    except TypeError:
        loop = runtime.agent_loop_cls(config)

    return loop


def launch(argv: list[str] | None = None) -> None:
    vibe_args, ws_port = parse_launcher_args(argv)

    debug_enabled = bool(getattr(vibe_args, "vibecheck_debug", False))
    log_file = str(getattr(vibe_args, "vibecheck_log_file", "") or "").strip()
    if log_file:
        debug_enabled = True
    if debug_enabled:
        os.environ["VIBECHECK_DEBUG"] = "1"
        os.environ["VIBECHECK_NOTIFICATION_AUDIT_LOG"] = log_file or "/tmp/vibecheck-notification.log"

    runtime = load_vibe_runtime()
    bridge = SessionBridge(
        session_id="live-bootstrap",
        connection_manager=session_manager.connection_manager,
        attach_mode="live",
    )
    agent_loop = _build_agent_loop(vibe_args, runtime, message_observer=bridge._on_message_observed)

    session_id = str(getattr(agent_loop, "session_id", "live-session"))
    bridge.session_id = session_id
    existing = session_manager.sessions.get(session_id)
    if existing is not None and existing is not bridge:
        existing.stop()
    session_manager.sessions[session_id] = bridge
    bridge.attach_to_loop(agent_loop, runtime)

    api_app = create_app()
    app = VibeCheckApp(
        agent_loop=agent_loop,
        bridge=bridge,
        ws_port=ws_port,
        api_app=api_app,
        initial_prompt=getattr(vibe_args, "initial_prompt", None),
        teleport_on_start=getattr(vibe_args, "teleport", False),
    )
    app.run()
