"""Responsive design utilities for Gym Management System.

This module provides:
- Screen size detection and breakpoints
- Responsive layout helpers
- Dynamic font and spacing adjustment
- Mobile/tablet/desktop detection
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Tuple, TypedDict


class Breakpoint(TypedDict):
    """Screen breakpoint configuration."""
    name: str
    min_width: int
    sidebar_width: int
    font_scale: float
    button_padding: Tuple[int, int, int, int]
    card_padding: int

BREAKPOINTS: dict[str, Breakpoint] = {
    "mobile": {
        "name": "mobile",
        "min_width": 0,
        "sidebar_width": 220,
        "font_scale": 0.85,
        "button_padding": (8, 12, 8, 12),
        "card_padding": 8,
    },
    "tablet": {
        "name": "tablet", 
        "min_width": 768,
        "sidebar_width": 180,
        "font_scale": 0.95,
        "button_padding": (10, 16, 10, 16),
        "card_padding": 12,
    },
    "desktop": {
        "name": "desktop",
        "min_width": 1024,
        "sidebar_width": 220,
        "font_scale": 1.0,
        "button_padding": (12, 20, 12, 20),
        "card_padding": 16,
    },
}


class ResponsiveManager:
    """Manages responsive behavior for the application."""
    
    def __init__(self, root: tk.Misc):
        self.root = root
        self.current_breakpoint: str = "desktop"
        self.previous_width: int = 0
        self.callbacks: list[Callable[[str], None]] = []

        self.root.bind("<Configure>", self._on_window_resize)
        
    def _on_window_resize(self, event) -> None:
        """Handle window resize events."""
        if event.widget == self.root:
            width = event.width
            if abs(width - self.previous_width) > 50:
                self.previous_width = width
                self._update_breakpoint(width)
    
    def _update_breakpoint(self, width: int) -> None:
        """Update current breakpoint based on window width."""
        new_breakpoint = self.get_breakpoint(width)
        if new_breakpoint != self.current_breakpoint:
            self.current_breakpoint = new_breakpoint
            self._notify_callbacks()
    
    def get_breakpoint(self, width: int | None = None) -> str:
        """Get the current breakpoint name."""
        if width is None:
            width = self.root.winfo_width()
        
        for name, config in reversed(list(BREAKPOINTS.items())):
            if width >= config["min_width"]:
                return name
        return "mobile"
    
    def get_breakpoint_config(self, breakpoint: str | None = None) -> Breakpoint:
        """Get configuration for current or specified breakpoint."""
        if breakpoint is None:
            breakpoint = self.current_breakpoint
        return BREAKPOINTS[breakpoint]
    
    def is_mobile(self) -> bool:
        """Check if current viewport is mobile size."""
        return self.current_breakpoint == "mobile"
    
    def is_tablet(self) -> bool:
        """Check if current viewport is tablet size."""
        return self.current_breakpoint == "tablet"
    
    def is_desktop(self) -> bool:
        """Check if current viewport is desktop size."""
        return self.current_breakpoint == "desktop"
    
    def get_sidebar_width(self) -> int:
        """Get appropriate sidebar width for current breakpoint."""
        return self.get_breakpoint_config()["sidebar_width"]
    
    def get_font_scale(self) -> float:
        """Get font scaling factor for current breakpoint."""
        return self.get_breakpoint_config()["font_scale"]
    
    def get_button_padding(self) -> Tuple[int, int, int, int]:
        """Get button padding for current breakpoint."""
        return self.get_breakpoint_config()["button_padding"]
    
    def get_card_padding(self) -> int:
        """Get card padding for current breakpoint."""
        return self.get_breakpoint_config()["card_padding"]
    
    def register_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback to be called when breakpoint changes."""
        self.callbacks.append(callback)
    
    def _notify_callbacks(self) -> None:
        """Notify all registered callbacks of breakpoint change."""
        for callback in self.callbacks:
            try:
                callback(self.current_breakpoint)
            except Exception:
                pass



def create_responsive_font(base_font: Tuple, scale: float) -> Tuple:
    """Create a scaled font based on base font and scale factor."""
    family = base_font[0]
    size = int(base_font[1])
    style = base_font[2] if len(base_font) >= 3 else "normal"
    new_size = max(8, int(size * scale))
    return (family, new_size, style)


def get_responsive_table_columns(breakpoint: str) -> dict[str, list[str]]:
    """Get table columns to show based on breakpoint."""
    if breakpoint == "mobile":
        return {
            "members": ["member_code", "first_name", "phone"],
            "payments": ["receipt_number", "member_name", "amount"],
            "subscriptions": ["member_code", "plan_name", "end_date"],
            "attendance": ["member_code", "check_in_time"],
        }
    elif breakpoint == "tablet":
        return {
            "members": ["member_code", "first_name", "phone", "status"],
            "payments": ["receipt_number", "member_name", "amount", "payment_method"],
            "subscriptions": ["member_code", "plan_name", "end_date", "status"],
            "attendance": ["member_code", "check_in_time", "date"],
        }
    else:  # desktop
        return {
            "members": ["member_code", "first_name", "last_name", "phone", "email", "status"],
            "payments": ["receipt_number", "member_name", "amount", "payment_method", "payment_date"],
            "subscriptions": ["member_code", "plan_name", "start_date", "end_date", "status"],
            "attendance": ["member_code", "check_in_time", "date"],
        }


def should_use_cards(breakpoint: str) -> bool:
    """Determine if cards should be used instead of tables."""
    return breakpoint == "mobile"


def get_dialog_size(breakpoint: str) -> Tuple[str, str]:
    """Get appropriate dialog size for breakpoint."""
    if breakpoint == "mobile":
        return ("95%", "80%")
    elif breakpoint == "tablet":
        return ("80%", "70%")
    else:
        return ("600", "500")
