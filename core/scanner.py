"""
Scanner module - Entry point for the modular scanning engine.
This file maintains backward compatibility by exporting functions from the new modular structure.
"""
import logging
from .engine import run_scan_once, start_scheduler, scan_lock

log = logging.getLogger("CyberIntel")

__all__ = ["run_scan_once", "start_scheduler", "scan_lock"]
