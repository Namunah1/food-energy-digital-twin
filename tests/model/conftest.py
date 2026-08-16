"""
Adds model/src to sys.path so these test files' existing same-directory
import convention (sys.path.insert(0, '.'); import model, agent, scenarios,
...) resolves correctly when run via pytest from any working directory,
without needing to copy files into model/src/ first (as manual runs during
development did) or restructure the model package (out of scope for this
consolidation pass — see LIMITATIONS.md).
"""
import sys
import os

MODEL_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "model", "src")
if MODEL_SRC not in sys.path:
    sys.path.insert(0, MODEL_SRC)
