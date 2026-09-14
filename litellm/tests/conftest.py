"""Put the litellm/ dir on sys.path so tests can ``import generate`` directly.

``litellm/`` is not a package (it holds the product template + generator, mounted flat
into the stack), so the generator is imported by path, mirroring how the compose init step
runs ``python3 litellm/generate.py``.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
