"""Aucun test n'ouvre de carte son : importer le vrai sounddevice initialise déjà PortAudio."""

import sys
import types

fake = types.ModuleType("sounddevice")
fake.PortAudioError = type("PortAudioError", (Exception,), {})
fake.query_devices = lambda device=None: []
fake.query_hostapis = lambda index=None: []
sys.modules["sounddevice"] = fake
