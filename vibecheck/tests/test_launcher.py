from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest

from vibecheck.bridge import SessionManager, VibeRuntime
from vibecheck import launcher


class FakeVibeConfig:
    def __init__(self) -> None:
        self.enabled_tools: list[str] = []
        self.active_model = "local"
        self.models = [
            SimpleNamespace(alias="devstral-2", provider="mistral"),
            SimpleNamespace(alias="local", provider="llamacpp"),
        ]

    def get_active_model(self):
        for model in self.models:
            if model.alias == self.active_model:
                return model
        raise ValueError("active model missing")

    def get_provider_for_model(self, model):
        return SimpleNamespace(name=getattr(model, "provider", ""))

    @classmethod
    def load(cls):
        return cls()


class FakeAgentLoop:
    last_kwargs: dict | None = None
    last_config: object | None = None

    def __init__(self, config, **kwargs) -> None:
        self.config = config
        self.session_id = "live-session"
        self.message_observer = kwargs.get("message_observer")
        self.approval_callback = None
        self.user_input_callback = None
        FakeAgentLoop.last_kwargs = kwargs
        FakeAgentLoop.last_config = config

    def set_approval_callback(self, callback) -> None:
        self.approval_callback = callback

    def set_user_input_callback(self, callback) -> None:
        self.user_input_callback = callback


class FakeVibeCheckApp:
    last_instance: "FakeVibeCheckApp | None" = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.run_called = False
        FakeVibeCheckApp.last_instance = self

    def run(self):
        self.run_called = True
        return "live-session"


@pytest.fixture
def fake_runtime() -> VibeRuntime:
    return VibeRuntime(
        agent_loop_cls=FakeAgentLoop,
        vibe_config_cls=FakeVibeConfig,
        approval_yes="yes",
        approval_no="no",
        ask_result_cls=None,
        answer_cls=None,
    )


def test_build_uvicorn_config_uses_warning_log_level() -> None:
    config = launcher.build_uvicorn_config(app=object(), port=7870)

    assert config.host == "0.0.0.0"
    assert config.port == 7870
    assert config.log_level == "warning"


def test_parse_launcher_args_accepts_debug_and_log_file_flags() -> None:
    vibe_args, ws_port = launcher.parse_launcher_args(
        ["--ws-port", "8787", "--debug", "--log-file", "/tmp/vibecheck-debug.log", "hello"]
    )

    assert ws_port == 8787
    assert getattr(vibe_args, "vibecheck_debug", False) is True
    assert getattr(vibe_args, "vibecheck_log_file", "") == "/tmp/vibecheck-debug.log"
    assert getattr(vibe_args, "initial_prompt", None) == "hello"


def test_build_agent_loop_passes_message_observer(fake_runtime: VibeRuntime) -> None:
    fake_args = SimpleNamespace(agent="default", enabled_tools=None)

    def observer(_message) -> None:
        return None

    loop = launcher._build_agent_loop(fake_args, fake_runtime, message_observer=observer)

    assert loop.message_observer is observer
    assert FakeAgentLoop.last_kwargs is not None
    assert FakeAgentLoop.last_kwargs["message_observer"] is observer


def test_build_agent_loop_prefers_mistral_devstral2_when_key_present(
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: VibeRuntime,
) -> None:
    fake_args = SimpleNamespace(agent="default", enabled_tools=None)

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.delenv("VIBE_ACTIVE_MODEL", raising=False)

    loop = launcher._build_agent_loop(fake_args, fake_runtime)

    assert loop.config.active_model == "devstral-2"


def test_build_agent_loop_does_not_override_active_model_when_env_is_explicit(
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: VibeRuntime,
) -> None:
    fake_args = SimpleNamespace(agent="default", enabled_tools=None)

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("VIBE_ACTIVE_MODEL", "local")

    loop = launcher._build_agent_loop(fake_args, fake_runtime)

    assert loop.config.active_model == "local"


def test_build_agent_loop_does_not_switch_models_without_mistral_key(
    monkeypatch: pytest.MonkeyPatch,
    fake_runtime: VibeRuntime,
) -> None:
    fake_args = SimpleNamespace(agent="default", enabled_tools=None)

    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    monkeypatch.delenv("VIBE_ACTIVE_MODEL", raising=False)

    loop = launcher._build_agent_loop(fake_args, fake_runtime)

    assert loop.config.active_model == "local"


def test_launch_creates_live_bridge_and_runs_app(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_runtime: VibeRuntime,
) -> None:
    manager = SessionManager(logs_root=tmp_path / "logs")
    fake_args = SimpleNamespace(
        initial_prompt="hello",
        teleport=False,
        agent="default",
        enabled_tools=None,
        vibecheck_debug=False,
        vibecheck_log_file="",
    )

    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")
    monkeypatch.setattr(launcher, "session_manager", manager)
    monkeypatch.setattr(launcher, "parse_launcher_args", lambda argv=None: (fake_args, 9001))
    monkeypatch.setattr(launcher, "load_vibe_runtime", lambda: fake_runtime)
    monkeypatch.setattr(launcher, "create_app", lambda: object())
    monkeypatch.setattr(launcher, "VibeCheckApp", FakeVibeCheckApp)

    launcher.launch([])

    bridge = manager.get("live-session")
    assert bridge.attach_mode == "live"
    assert bridge.controllable is True
    assert FakeVibeCheckApp.last_instance is not None
    assert FakeVibeCheckApp.last_instance.run_called is True
    assert FakeVibeCheckApp.last_instance.kwargs["ws_port"] == 9001


def test_launch_sets_notification_debug_env_and_log_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_runtime: VibeRuntime,
) -> None:
    manager = SessionManager(logs_root=tmp_path / "logs")
    fake_args = SimpleNamespace(
        initial_prompt=None,
        teleport=False,
        agent="default",
        enabled_tools=None,
        vibecheck_debug=True,
        vibecheck_log_file="/tmp/custom-vibecheck.log",
    )

    monkeypatch.setenv("VIBECHECK_PSK", "dev-psk")
    monkeypatch.delenv("VIBECHECK_DEBUG", raising=False)
    monkeypatch.delenv("VIBECHECK_NOTIFICATION_AUDIT_LOG", raising=False)
    monkeypatch.setattr(launcher, "session_manager", manager)
    monkeypatch.setattr(launcher, "parse_launcher_args", lambda argv=None: (fake_args, 9001))
    monkeypatch.setattr(launcher, "load_vibe_runtime", lambda: fake_runtime)
    monkeypatch.setattr(launcher, "create_app", lambda: object())
    monkeypatch.setattr(launcher, "VibeCheckApp", FakeVibeCheckApp)

    launcher.launch([])

    assert os.getenv("VIBECHECK_DEBUG") == "1"
    assert os.getenv("VIBECHECK_NOTIFICATION_AUDIT_LOG") == "/tmp/custom-vibecheck.log"


@pytest.mark.asyncio
async def test_on_mount_rebinds_callbacks_and_intercepts_future_rebinds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Loop:
        def __init__(self) -> None:
            self.approval_callback = None
            self.user_input_callback = None

        def set_approval_callback(self, callback) -> None:
            self.approval_callback = callback

        def set_user_input_callback(self, callback) -> None:
            self.user_input_callback = callback

    class Bridge:
        def __init__(self) -> None:
            self.attach_calls: list[dict] = []
            self._local_approval_callback = None
            self._local_input_callback = None

        @property
        def local_approval_callback(self):
            return self._local_approval_callback

        @property
        def local_input_callback(self):
            return self._local_input_callback

        async def _approval_callback(self, *_args):
            return ("yes", None)

        async def _user_input_callback(self, *_args):
            return {"response": "ok"}

        def configure_local_callbacks(self, *, approval_callback, input_callback) -> None:
            self._local_approval_callback = approval_callback
            self._local_input_callback = input_callback

        def attach_to_loop(self, agent_loop, *_args, approval_callback=None, input_callback=None, **_kwargs) -> None:
            self.attach_calls.append(
                {
                    "approval_callback": approval_callback,
                    "input_callback": input_callback,
                }
            )
            self.configure_local_callbacks(
                approval_callback=approval_callback,
                input_callback=input_callback,
            )
            agent_loop.set_approval_callback(self._approval_callback)
            agent_loop.set_user_input_callback(self._user_input_callback)

        def add_raw_event_listener(self, _listener) -> None:
            return None

        def remove_raw_event_listener(self, _listener) -> None:
            return None

        def prime_message_worker(self) -> None:
            return None

    async def fake_super_on_mount(self) -> None:
        self.agent_loop.set_approval_callback(lambda *_args: ("yes", None))
        self.agent_loop.set_user_input_callback(lambda *_args: {"response": "ok"})

    def fake_super_init(self, *_args, **kwargs) -> None:
        self.agent_loop = kwargs.get("agent_loop")
        self.event_handler = None
        self._loading_widget = None

    def fake_run_worker(self, worker, *, exclusive: bool = False) -> None:
        _ = exclusive
        close = getattr(worker, "close", None)
        if callable(close):
            close()

    monkeypatch.setattr(launcher._BaseVibeApp, "__init__", fake_super_init, raising=False)
    monkeypatch.setattr(launcher._BaseVibeApp, "on_mount", fake_super_on_mount, raising=False)
    monkeypatch.setattr(launcher.VibeCheckApp, "run_worker", fake_run_worker, raising=False)

    loop = Loop()
    bridge = Bridge()
    app = launcher.VibeCheckApp(
        agent_loop=loop,
        bridge=bridge,
        ws_port=9001,
        api_app=object(),
    )
    await app.on_mount()

    assert bridge.attach_calls
    assert loop.approval_callback.__func__ is bridge._approval_callback.__func__
    assert loop.user_input_callback.__func__ is bridge._user_input_callback.__func__

    initial_local_approval = bridge.local_approval_callback
    initial_local_input = bridge.local_input_callback
    loop.set_approval_callback(bridge._approval_callback)
    loop.set_user_input_callback(bridge._user_input_callback)
    assert bridge.local_approval_callback is initial_local_approval
    assert bridge.local_input_callback is initial_local_input

    loop.set_approval_callback(lambda *_args: ("no", None))
    loop.set_user_input_callback(lambda *_args: {"response": "later"})
    assert loop.approval_callback.__func__ is bridge._approval_callback.__func__
    assert loop.user_input_callback.__func__ is bridge._user_input_callback.__func__


@pytest.mark.asyncio
async def test_handle_agent_loop_turn_renders_prompt_before_bridge_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Loop:
        pass

    mark_calls: list[str] = []

    class Bridge:
        def __init__(self) -> None:
            self.injected: list[str] = []

        def inject_message(self, prompt: str) -> bool:
            assert mark_calls == []
            self.injected.append(prompt)
            return True

    class FakeTuiBridge:
        def mark_local_user_message(self, content: str) -> None:
            mark_calls.append(content)

    render_calls: list[tuple[str, Path]] = []

    def fake_render(prompt: str, base_dir: Path) -> str:
        render_calls.append((prompt, base_dir))
        return f"rendered:{prompt}"

    def fake_super_init(self, *_args, **kwargs) -> None:
        self.agent_loop = kwargs.get("agent_loop")

    monkeypatch.setattr(launcher._BaseVibeApp, "__init__", fake_super_init, raising=False)
    monkeypatch.setattr(launcher, "_render_path_prompt", fake_render, raising=False)

    bridge = Bridge()
    app = launcher.VibeCheckApp(
        agent_loop=Loop(),
        bridge=bridge,
        ws_port=9001,
        api_app=object(),
    )
    app._tui_bridge = FakeTuiBridge()  # type: ignore[assignment]

    await app._handle_agent_loop_turn("check @README.md")

    assert bridge.injected == ["rendered:check @README.md"]
    assert render_calls == [("check @README.md", Path.cwd())]
    assert mark_calls == ["rendered:check @README.md"]


@pytest.mark.asyncio
async def test_handle_agent_loop_turn_does_not_mark_prompt_when_bridge_injection_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Loop:
        pass

    class Bridge:
        def inject_message(self, _prompt: str) -> bool:
            return False

    class UserMessageEvent:
        def __init__(self, content: str) -> None:
            self.content = content
            self.message_id = "m1"

    mounted: list[str] = []

    async def mount_user_message(content: str) -> None:
        mounted.append(content)

    def fake_super_init(self, *_args, **kwargs) -> None:
        self.agent_loop = kwargs.get("agent_loop")

    monkeypatch.setattr(launcher._BaseVibeApp, "__init__", fake_super_init, raising=False)

    bridge = Bridge()
    app = launcher.VibeCheckApp(
        agent_loop=Loop(),
        bridge=bridge,
        ws_port=9001,
        api_app=object(),
    )
    setattr(app, "notify", lambda *_args, **_kwargs: None)

    handler = SimpleNamespace(handle_event=lambda *_args, **_kwargs: None)
    tui_bridge = launcher.TuiBridge(handler, mount_user_message=mount_user_message)
    app._tui_bridge = tui_bridge

    await app._handle_agent_loop_turn("hello")

    await tui_bridge.on_bridge_raw_event(UserMessageEvent("hello"))

    assert mounted == ["hello"]


@pytest.mark.asyncio
async def test_on_mount_primes_bridge_message_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Loop:
        def __init__(self) -> None:
            self.approval_callback = None
            self.user_input_callback = None

        def set_approval_callback(self, callback) -> None:
            self.approval_callback = callback

        def set_user_input_callback(self, callback) -> None:
            self.user_input_callback = callback

    class Bridge:
        def __init__(self) -> None:
            self.prime_calls = 0

        @property
        def local_approval_callback(self):
            return None

        @property
        def local_input_callback(self):
            return None

        async def _approval_callback(self, *_args):
            return ("yes", None)

        async def _user_input_callback(self, *_args):
            return {"response": "ok"}

        def configure_local_callbacks(self, *, approval_callback, input_callback) -> None:
            _ = approval_callback, input_callback

        def attach_to_loop(self, agent_loop, *_args, **_kwargs) -> None:
            agent_loop.set_approval_callback(self._approval_callback)
            agent_loop.set_user_input_callback(self._user_input_callback)

        def add_raw_event_listener(self, _listener) -> None:
            return None

        def remove_raw_event_listener(self, _listener) -> None:
            return None

        def prime_message_worker(self) -> None:
            self.prime_calls += 1

    async def fake_super_on_mount(self) -> None:
        return None

    def fake_super_init(self, *_args, **kwargs) -> None:
        self.agent_loop = kwargs.get("agent_loop")
        self.event_handler = None
        self._loading_widget = None

    def fake_run_worker(self, worker, *, exclusive: bool = False) -> None:
        _ = exclusive
        close = getattr(worker, "close", None)
        if callable(close):
            close()

    monkeypatch.setattr(launcher._BaseVibeApp, "__init__", fake_super_init, raising=False)
    monkeypatch.setattr(launcher._BaseVibeApp, "on_mount", fake_super_on_mount, raising=False)
    monkeypatch.setattr(launcher.VibeCheckApp, "run_worker", fake_run_worker, raising=False)

    loop = Loop()
    bridge = Bridge()
    app = launcher.VibeCheckApp(
        agent_loop=loop,
        bridge=bridge,
        ws_port=9001,
        api_app=object(),
    )

    await app.on_mount()

    assert bridge.prime_calls == 1


def test_vibecheck_vibe_script_registered() -> None:
    pyproject = Path("pyproject.toml").read_bytes()
    parsed = tomllib.loads(pyproject.decode("utf-8"))
    scripts = parsed["project"]["scripts"]

    assert scripts["vibecheck-vibe"] == "vibecheck.launcher:launch"
