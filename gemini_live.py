from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import threading
import time
import traceback
from pathlib import Path

from google import genai
from google.genai import types

from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.youtube_video     import youtube_video
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater

BASE_DIR        = Path(__file__).resolve().parent
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL      = "models/gemini-2.5-flash-native-audio-preview-12-2025"

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)


def _clean_transcript(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are EDI, Tony Stark's AI assistant running on Android. "
            "Be concise, direct, and always use the provided tools to complete tasks."
        )


TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": "Opens any application on the phone.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "App name or package name"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a reminder.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "datetime": {"type": "STRING", "description": "Date and time"},
                "message":  {"type": "STRING", "description": "Reminder text"}
            },
            "required": ["datetime", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": "Searches or controls YouTube.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | search"},
                "query":  {"type": "STRING", "description": "Search query"}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": "Controls browser: go_to, search, click, scroll, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | scroll | back | new_tab"},
                "url":         {"type": "STRING", "description": "URL for go_to"},
                "query":       {"type": "STRING", "description": "Search query"},
                "selector":    {"type": "STRING", "description": "CSS selector for click"},
                "text":        {"type": "STRING", "description": "Text to click"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct control: type, click, hotkey, scroll, etc.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | click | hotkey | scroll | press"},
                "text":        {"type": "STRING", "description": "Text to type"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. ctrl+c"},
                "key":         {"type": "STRING", "description": "Single key e.g. enter"},
                "direction":   {"type": "STRING", "description": "up | down"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run"},
                "description": {"type": "STRING", "description": "What the code should do"},
                "language":    {"type": "STRING", "description": "Programming language"},
                "file_path":   {"type": "STRING", "description": "Path to existing file"},
                "code":        {"type": "STRING", "description": "Raw code string"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete projects from scratch.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "game_updater",
        "description": "Checks or updates games from Steam/Epic.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING", "description": "update | install | list"},
                "game_name": {"type": "STRING", "description": "Game name"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights for best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING", "description": "Departure city"},
                "destination": {"type": "STRING", "description": "Arrival city"},
                "date":        {"type": "STRING", "description": "Departure date"},
                "return_date": {"type": "STRING", "description": "Return date"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_edi",
        "description": "Shuts down the assistant completely.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "save_memory",
        "description": "Save an important personal fact about the user to long-term memory.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "description": "identity | preferences | projects | notes"},
                "key":   {"type": "STRING", "description": "Short snake_case key"},
                "value": {"type": "STRING", "description": "Concise value in English"},
            },
            "required": ["category", "key", "value"]
        }
    },
]


class GeminiLiveEngine:
    def __init__(self, ui):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self._turn_done_event: asyncio.Event | None = None
        self._audio = None

    def set_audio(self, audio):
        self._audio = audio

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if self._audio:
            self._audio.set_speaking(value)
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime
        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()
        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = f"[CURRENT DATE & TIME]\nRight now it is: {time_str}\n\n"
        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})
        print(f"[EDI] {name} {args}")
        self.ui.set_state("THINKING")
        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )
        loop   = asyncio.get_event_loop()
        result = "Done."
        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."
            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."
            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."
            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."
            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."
            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."
            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "shutdown_edi":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")
                def _shutdown():
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()
            else:
                result = f"Unknown tool: {name}"
        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)
        if not self.ui.muted:
            self.ui.set_state("LISTENING")
        print(f"[EDI] {name} -> {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[EDI] Mic started")
        loop = asyncio.get_event_loop()
        while True:
            try:
                chunk = await asyncio.wait_for(self.out_queue.get(), timeout=0.1)
                await self.session.send_realtime_input(media=chunk)
            except asyncio.TimeoutError:
                continue

    async def _receive_audio(self):
        print("[EDI] Recv started")
        out_buf, in_buf = [], []
        while True:
            async for response in self.session.receive():
                if response.data:
                    if self._turn_done_event and self._turn_done_event.is_set():
                        self._turn_done_event.clear()
                    self.audio_in_queue.put_nowait(response.data)
                if response.server_content:
                    sc = response.server_content
                    if sc.output_transcription and sc.output_transcription.text:
                        txt = _clean_transcript(sc.output_transcription.text)
                        if txt:
                            out_buf.append(txt)
                    if sc.input_transcription and sc.input_transcription.text:
                        txt = _clean_transcript(sc.input_transcription.text)
                        if txt:
                            in_buf.append(txt)
                    if sc.turn_complete:
                        if self._turn_done_event:
                            self._turn_done_event.set()
                        full_in = " ".join(in_buf).strip()
                        if full_in:
                            self.ui.write_log(f"You: {full_in}")
                        in_buf = []
                        full_out = " ".join(out_buf).strip()
                        if full_out:
                            self.ui.write_log(f"Edi: {full_out}")
                        out_buf = []
                if response.tool_call:
                    fn_responses = []
                    for fc in response.tool_call.function_calls:
                        print(f"[EDI] {fc.name}")
                        fr = await self._execute_tool(fc)
                        fn_responses.append(fr)
                    await self.session.send_tool_response(
                        function_responses=fn_responses
                    )

    async def _play_audio(self):
        print("[EDI] Play started")
        while True:
            try:
                chunk = await asyncio.wait_for(
                    self.audio_in_queue.get(),
                    timeout=0.1
                )
            except asyncio.TimeoutError:
                if (self._turn_done_event and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()):
                    self.set_speaking(False)
                    self._turn_done_event.clear()
                continue
            self.set_speaking(True)
            await asyncio.to_thread(self._audio.play_chunk, chunk)

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )
        while True:
            try:
                print("[EDI] Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()
                self.audio_in_queue = asyncio.Queue()
                self.out_queue      = asyncio.Queue(maxsize=10)
                self._turn_done_event = asyncio.Event()
                if self._audio:
                    self._audio.start(self.out_queue, self.audio_in_queue)
                async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                    self.session = session
                    self._loop   = asyncio.get_event_loop()
                    print("[EDI] Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: EDI online.")
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._send_realtime())
                        tg.create_task(self._receive_audio())
                        tg.create_task(self._play_audio())
            except Exception as e:
                print(f"[EDI] {e}")
                traceback.print_exc()
            self.set_speaking(False)
            self.ui.set_state("THINKING")
            print("[EDI] Reconnecting in 3s...")
            await asyncio.sleep(3)
