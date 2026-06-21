from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
from pathlib import Path

import psutil

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import get_color_from_hex

from gemini_live import GeminiLiveEngine, _get_api_key, _load_system_prompt
from hud_widget import HudWidget, C

try:
    from audiomanager import AndroidAudioManager as AudioManager
    IS_ANDROID = True
except Exception:
    IS_ANDROID = False

BASE_DIR    = Path(__file__).resolve().parent
CONFIG_DIR  = BASE_DIR / "config"
API_FILE    = CONFIG_DIR / "api_keys.json"


class EdiApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._engine: GeminiLiveEngine | None = None
        self._muted = False
        self._on_text_command_cb = None

    def build(self):
        self.title = "E.D.I \u2014 MARK XL"
        Window.clearcolor = get_color_from_hex(C.BG)
        Window.size = (dp(420), dp(700))

        root = FloatLayout()

        self.hud = HudWidget("face.png")
        self.hud.size_hint = (1, 0.55)
        self.hud.pos_hint = {"x": 0, "y": 0.45}
        root.add_widget(self.hud)

        bottom = BoxLayout(orientation="vertical", size_hint=(1, 0.45),
                            pos_hint={"x": 0, "y": 0})
        root.add_widget(bottom)

        self.file_lbl = Label(
            text="", size_hint=(1, None), height=dp(24),
            font_name="Courier New", font_size=dp(8),
            color=get_color_from_hex("#3a8a9a"),
            halign="center", valign="middle",
        )
        bottom.add_widget(self.file_lbl)

        scroll = ScrollView(size_hint=(1, 1))
        self.log_lbl = Label(
            text="", size_hint=(1, None), height=dp(200),
            font_name="Courier New", font_size=dp(9),
            color=get_color_from_hex(C.TEXT),
            halign="left", valign="top",
            text_size=(Window.width - dp(20), None),
            markup=True,
        )
        self.log_lbl.bind(texture_size=lambda inst, val: setattr(inst, "height", val))
        scroll.add_widget(self.log_lbl)
        bottom.add_widget(scroll)

        input_row = BoxLayout(size_hint=(1, None), height=dp(40), spacing=dp(4))
        self.input_field = TextInput(
            size_hint=(1, 1), font_name="Courier New", font_size=dp(10),
            hint_text="Type a command or question...",
            background_color=get_color_from_hex("#000d14"),
            foreground_color=get_color_from_hex("#d8f8ff"),
            cursor_color=get_color_from_hex("#00d4ff"),
            multiline=False,
        )
        self.input_field.bind(on_text_validate=self._send_text)
        input_row.add_widget(self.input_field)

        send_btn = Button(
            text="\u25b8", size_hint=(None, 1), width=dp(40),
            font_name="Courier New", font_size=dp(14), bold=True,
            background_color=get_color_from_hex(C.PRI),
            color=get_color_from_hex("#00060a"),
        )
        send_btn.bind(on_press=self._send_text)
        input_row.add_widget(send_btn)
        bottom.add_widget(input_row)

        ctrl_row = BoxLayout(size_hint=(1, None), height=dp(36), spacing=dp(6))
        self.mute_btn = Button(
            text="\U0001f399  MICROPHONE ACTIVE",
            font_name="Courier New", font_size=dp(8), bold=True,
            background_color=get_color_from_hex("#00140a"),
            color=get_color_from_hex("#00ff88"),
        )
        self.mute_btn.bind(on_press=self._toggle_mute)
        ctrl_row.add_widget(self.mute_btn)

        cfg_btn = Button(
            text="\u2699  CONFIGURE", size_hint=(0.3, 1),
            font_name="Courier New", font_size=dp(7),
            background_color=get_color_from_hex("#010d14"),
            color=get_color_from_hex("#3a8a9a"),
        )
        cfg_btn.bind(on_press=self._show_config)
        ctrl_row.add_widget(cfg_btn)
        bottom.add_widget(ctrl_row)

        Clock.schedule_once(self._init_engine, 0.5)
        return root

    def _init_engine(self, dt):
        if not API_FILE.exists() or not _get_api_key():
            self._show_setup()
            return
        self._start_engine()

    def _start_engine(self):
        audio = AudioManager() if IS_ANDROID else None
        self._engine = GeminiLiveEngine(self)
        self._engine.set_audio(audio)
        Clock.schedule_once(lambda dt: self._run_async_engine(), 0)

    def _run_async_engine(self):
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._engine.run())

    def _toggle_mute(self, btn=None):
        self._muted = not self._muted
        self.hud.muted = self._muted
        if self._muted:
            self.mute_btn.text = "\U0001f507  MICROPHONE MUTED"
            self.mute_btn.background_color = get_color_from_hex("#140006")
            self.mute_btn.color = get_color_from_hex("#ff3366")
        else:
            self.mute_btn.text = "\U0001f399  MICROPHONE ACTIVE"
            self.mute_btn.background_color = get_color_from_hex("#00140a")
            self.mute_btn.color = get_color_from_hex("#00ff88")

    def _send_text(self, instance):
        text = self.input_field.text.strip()
        if not text:
            return
        self.input_field.text = ""
        if self._on_text_command_cb:
            threading.Thread(target=self._on_text_command_cb, args=(text,), daemon=True).start()

    def _show_setup(self, btn=None):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
        content.add_widget(Label(
            text="\u25c8  INITIALISATION REQUIRED",
            font_name="Courier New", font_size=dp(12), bold=True,
            color=get_color_from_hex(C.PRI),
        ))
        content.add_widget(Label(
            text="Enter your Gemini API key:", size_hint=(1, None), height=dp(20),
            font_name="Courier New", font_size=dp(8),
            color=get_color_from_hex("#3a8a9a"),
        ))
        key_input = TextInput(
            hint_text="Gemini API key",
            font_name="Courier New", font_size=dp(10),
            size_hint=(1, None), height=dp(36),
            password=True,
        )
        content.add_widget(key_input)
        err_lbl = Label(
            text="", size_hint=(1, None), height=dp(20),
            font_name="Courier New", font_size=dp(8),
            color=get_color_from_hex("#ff3355"),
        )
        content.add_widget(err_lbl)

        popup = Popup(
            title="E.D.I Setup", content=content,
            size_hint=(0.85, 0.45),
        )

        def save(btn):
            key = key_input.text.strip()
            if not key:
                err_lbl.text = "API key cannot be empty!"
                return
            os.makedirs(CONFIG_DIR, exist_ok=True)
            API_FILE.write_text(json.dumps({"gemini_api_key": key}), encoding="utf-8")
            popup.dismiss()
            self._start_engine()

        save_btn = Button(
            text="\u25b8  INITIALISE SYSTEMS", size_hint=(1, None), height=dp(40),
            font_name="Courier New", font_size=dp(10), bold=True,
            background_color=get_color_from_hex("#010d14"),
            color=get_color_from_hex(C.PRI),
        )
        save_btn.bind(on_press=save)
        content.add_widget(save_btn)
        popup.open()

    def _show_config(self, btn=None):
        from kivy.uix.popup import Popup
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.textinput import TextInput
        from kivy.uix.button import Button
        current = ""
        try:
            current = json.loads(API_FILE.read_text(encoding="utf-8")).get("gemini_api_key", "")
        except Exception:
            pass
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(16))
        content.add_widget(Label(
            text="\u25c8  CONFIGURATION",
            font_name="Courier New", font_size=dp(12), bold=True,
            color=get_color_from_hex(C.PRI),
        ))
        content.add_widget(Label(
            text="GEMINI API KEY", size_hint=(1, None), height=dp(16),
            font_name="Courier New", font_size=dp(7),
            color=get_color_from_hex("#3a8a9a"),
            halign="left",
        ))
        key_input = TextInput(
            text=current, hint_text="Gemini API key",
            font_name="Courier New", font_size=dp(10),
            size_hint=(1, None), height=dp(36),
            password=True,
        )
        content.add_widget(key_input)
        popup = Popup(
            title="E.D.I Config", content=content,
            size_hint=(0.85, 0.4),
        )

        def save(btn):
            key = key_input.text.strip()
            if not key:
                return
            os.makedirs(CONFIG_DIR, exist_ok=True)
            API_FILE.write_text(json.dumps({"gemini_api_key": key}), encoding="utf-8")
            popup.dismiss()

        save_btn = Button(
            text="\u25b8  APPLY CHANGES", size_hint=(1, None), height=dp(40),
            font_name="Courier New", font_size=dp(10), bold=True,
            background_color=get_color_from_hex("#010d14"),
            color=get_color_from_hex(C.PRI),
        )
        save_btn.bind(on_press=save)
        content.add_widget(save_btn)
        popup.open()

    def set_state(self, state: str):
        self.hud.state = state
        self.hud.speaking = (state == "SPEAKING")

    def write_log(self, text: str):
        Clock.schedule_once(lambda dt: self._append_log(text))

    def _append_log(self, text: str):
        current = self.log_lbl.text
        prefix = ""
        tl = text.lower()
        if tl.startswith("you:"):
            prefix = "[color=d8f8ff]"
        elif tl.startswith("edi:"):
            prefix = "[color=00d4ff]"
        elif tl.startswith("err"):
            prefix = "[color=ff3355]"
        elif tl.startswith("sys:"):
            prefix = "[color=ffcc00]"
        else:
            prefix = "[color=8ffcff]"
        self.log_lbl.text = current + prefix + text + "[/color]\n"

    @property
    def muted(self) -> bool:
        return self._muted

    @property
    def on_text_command(self):
        return self._on_text_command_cb

    @on_text_command.setter
    def on_text_command(self, cb):
        self._on_text_command_cb = cb

    def wait_for_api_key(self):
        while not (API_FILE.exists() and _get_api_key()):
            time.sleep(0.1)

    def show_startup_panel(self):
        pass

    def mark_startup_ready(self, key: str, error: bool = False):
        pass

    def set_startup_status(self, text: str):
        pass

    def hide_startup_panel(self):
        pass

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self._muted:
            self.set_state("LISTENING")


def main():
    EdiApp().run()


if __name__ == "__main__":
    main()
