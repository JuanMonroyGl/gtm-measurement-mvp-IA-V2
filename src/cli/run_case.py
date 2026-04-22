"""Temporary compatibility wrapper that delegates execution to root main.py."""

from __future__ import annotations

from main import main


if __name__ == "__main__":
    main()
