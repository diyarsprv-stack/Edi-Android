from __future__ import annotations

import asyncio
import threading
import time

SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHANNELS            = 1
CHUNK_SIZE          = 1024
FORMAT_PCM          = 2  # AudioFormat.ENCODING_PCM_16BIT


class AndroidAudioManager:
    def __init__(self):
        self._recorder  = None
        self._track     = None
        self._recording = False
        self._playing   = False
        self._rec_thread: threading.Thread | None = None
        self._play_thread: threading.Thread | None = None
        self.out_queue: asyncio.Queue | None = None
        self.in_queue: asyncio.Queue | None = None
        self._is_speaking = False
        self._is_muted    = False

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def set_speaking(self, v: bool):
        self._is_speaking = v

    def set_muted(self, v: bool):
        self._is_muted = v

    def _create_recorder(self) -> object:
        from jnius import autoclass
        MediaRecorder_AudioSource = autoclass("android.media.MediaRecorder$AudioSource")
        AudioFormat = autoclass("android.media.AudioFormat")
        AudioRecord = autoclass("android.media.AudioRecord")
        BUFFER_SIZE = AudioRecord.getMinBufferSize(
            SEND_SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, FORMAT_PCM
        )
        recorder = AudioRecord(
            MediaRecorder_AudioSource.VOICE_RECOGNITION,
            SEND_SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            FORMAT_PCM,
            max(BUFFER_SIZE, CHUNK_SIZE * 4),
        )
        return recorder

    def _recorder_loop(self):
        import numpy as np
        self._recorder = self._create_recorder()
        self._recorder.startRecording()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ba = bytearray(CHUNK_SIZE * 2)
        buf = (c_short * CHUNK_SIZE).from_buffer(ba)
        while self._recording:
            if not self._is_speaking and not self._is_muted:
                read = self._recorder.read(buf, 0, CHUNK_SIZE)
                if read > 0:
                    loop.call_soon_threadsafe(
                        self.out_queue.put_nowait,
                        {"data": bytes(ba[:read * 2]), "mime_type": "audio/pcm"}
                    )
            else:
                time.sleep(0.01)
        self._recorder.stop()
        self._recorder.release()
        self._recorder = None

    def _create_track(self) -> object:
        from jnius import autoclass
        AudioFormat = autoclass("android.media.AudioFormat")
        AudioTrack = autoclass("android.media.AudioTrack")
        BUFFER_SIZE = AudioTrack.getMinBufferSize(
            RECEIVE_SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, FORMAT_PCM
        )
        track = AudioTrack(
            AudioTrack.STREAM_MUSIC,
            RECEIVE_SAMPLE_RATE,
            AudioFormat.CHANNEL_OUT_MONO,
            FORMAT_PCM,
            max(BUFFER_SIZE, CHUNK_SIZE * 8),
            AudioTrack.MODE_STREAM,
        )
        return track

    def _track_loop(self):
        import numpy as np
        self._track = self._create_track()
        self._track.play()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        fut = asyncio.run_coroutine_threadsafe(self._play_from_queue(), loop)
        try:
            fut.result()
        except Exception:
            pass

    async def _play_from_queue(self):
        while self._playing:
            try:
                chunk = await asyncio.wait_for(self.in_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            self._is_speaking = True
            ba = bytes(chunk)
            arr = (c_short * (len(ba) // 2)).from_buffer_copy(ba)
            self._track.write(arr, 0, len(arr))
        self._track.stop()
        self._track.release()
        self._track = None

    def start(self, out_q: asyncio.Queue, in_q: asyncio.Queue):
        self.out_queue = out_q
        self.in_queue  = in_q
        self._recording = True
        self._playing   = True
        self._rec_thread = threading.Thread(target=self._recorder_loop, daemon=True)
        self._play_thread = threading.Thread(target=self._track_loop, daemon=True)
        self._rec_thread.start()
        self._play_thread.start()

    def stop(self):
        self._recording = False
        self._playing   = False
        if self._rec_thread:
            self._rec_thread.join(timeout=2)
        if self._play_thread:
            self._play_thread.join(timeout=2)


from ctypes import c_short
