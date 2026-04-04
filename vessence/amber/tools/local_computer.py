# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0

import asyncio
import io
import subprocess
import os
import re
import time
from urllib.parse import quote
try:
    from PIL import ImageGrab, Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    ImageGrab = Image = None
from typing import Literal, Optional, Sequence
try:
    from pynput.mouse import Button, Controller as MouseController
    from pynput.keyboard import Key, Controller as KeyboardController
    _PYNPUT_AVAILABLE = True
except Exception:
    # Catches ImportError AND pynput.DisplayNameError (no X display available)
    _PYNPUT_AVAILABLE = False
    Button = MouseController = Key = KeyboardController = None
from google.adk.tools.computer_use.base_computer import BaseComputer, ComputerState, ComputerEnvironment
import logging

# New Skills Integration
from agent_skills.omniparser_skill import OmniParserService
from agent_skills.browser_utils import get_compact_html

logger = logging.getLogger('google_adk.local_computer')

class LocalComputer(BaseComputer):
    """A concrete implementation of BaseComputer using pynput and PIL for local computer control.
    Uses xprop and xwininfo for robust window management across multiple desktops.
    """

    def __init__(self):
        try:
            self.mouse = MouseController() if _PYNPUT_AVAILABLE else None
            self.keyboard = KeyboardController() if _PYNPUT_AVAILABLE else None
        except Exception:
            self.mouse = None
            self.keyboard = None
        self.omni_service = None

    def _get_omni(self):
        if self.omni_service is None:
            self.omni_service = OmniParserService()
        return self.omni_service

    def _launch_browser(self, url: str, new_window: bool = False):
        """Helper to launch Chrome. Uses start_new_session to detach from parent process group."""
        cmd = ["google-chrome", "--new-window", url] if new_window else ["google-chrome", url]
        subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def screen_size(self) -> tuple[int, int]:
        screenshot = ImageGrab.grab()
        return screenshot.size

    async def current_state(self) -> ComputerState:
        # Capture screenshot
        screenshot = ImageGrab.grab()
        
        # 1. RUN OMNIPARSER (Semantic Context)
        omni = self._get_omni()
        img_byte_arr_full = io.BytesIO()
        screenshot.save(img_byte_arr_full, format='PNG')
        
        som_description = ""
        try:
            omni_result = omni.parse_screenshot(img_byte_arr_full.getvalue())
            som_description = omni_result.get('parsed_content', '')
            # Log for debugging only - do NOT send in state
            logger.debug(f"OmniParser elements: {len(omni_result.get('elements', []))}")
        except Exception as e:
            logger.error(f"OmniParser error: {e}")
        
        # 2. GET BROWSER CONTEXT
        active_title = self._get_active_window_title()
        current_url = "about:blank"
        
        _env = {**os.environ, "DISPLAY": ":0"}
        if "chrome" in active_title.lower():
            try:
                # Get URL via Clipboard hack
                subprocess.run(["xclip", "-selection", "clipboard", "/dev/null"], env=_env)
                await self.key_combination(["control", "l"])
                await asyncio.sleep(0.3)
                await self.key_combination(["control", "c"])
                await asyncio.sleep(0.3)

                clipboard_url = subprocess.check_output(
                    ["xclip", "-o", "-selection", "clipboard"], env=_env, text=True
                ).strip()
                if clipboard_url.startswith("http"):
                    current_url = clipboard_url
            except Exception:
                pass

        # Resize for the model
        max_size = 1024
        width, height = screenshot.size
        if width > max_size or height > max_size:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            screenshot_resized = screenshot.resize((new_width, new_height))
        else:
            screenshot_resized = screenshot
            
        img_byte_arr = io.BytesIO()
        screenshot_resized.save(img_byte_arr, format='PNG')
        
        # IMPORTANT: Returning a clean URL to satisfy Computer Use model validation.
        return ComputerState(
            screenshot=img_byte_arr.getvalue(), 
            url=current_url
        )

    async def get_crop(self, x: int, y: int) -> ComputerState:
        screenshot = ImageGrab.grab()
        w, h = screenshot.size
        crop_size = 256
        left = max(0, x - crop_size)
        top = max(0, y - crop_size)
        right = min(w, x + crop_size)
        bottom = min(h, y + crop_size)
        zoom_crop = screenshot.crop((left, top, right, bottom))
        img_byte_arr = io.BytesIO()
        zoom_crop.save(img_byte_arr, format='PNG')
        return ComputerState(screenshot=img_byte_arr.getvalue(), url="about:blank")

    async def open_web_browser(self) -> ComputerState:
        self._launch_browser("about:blank", new_window=False)
        await asyncio.sleep(3.0)
        return await self.current_state()

    async def click_at(self, x: int, y: int) -> ComputerState:
        self.mouse.position = (x, y)
        await asyncio.sleep(0.1)
        self.mouse.click(Button.left, 1)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def hover_at(self, x: int, y: int) -> ComputerState:
        self.mouse.position = (x, y)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def type_text_at(self, x: int, y: int, text: str, press_enter: bool = True, clear_before_typing: bool = True) -> ComputerState:
        await self.click_at(x, y)
        if clear_before_typing:
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.press('a')
                self.keyboard.release('a')
            self.keyboard.press(Key.backspace)
            self.keyboard.release(Key.backspace)
        self.keyboard.type(text)
        if press_enter:
            self.keyboard.press(Key.enter)
            self.keyboard.release(Key.enter)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def scroll_document(self, direction: Literal["up", "down", "left", "right"]) -> ComputerState:
        if direction == "up": self.mouse.scroll(0, 2)
        elif direction == "down": self.mouse.scroll(0, -2)
        elif direction == "left": self.mouse.scroll(-2, 0)
        elif direction == "right": self.mouse.scroll(2, 0)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def scroll_at(self, x: int, y: int, direction: Literal["up", "down", "left", "right"], magnitude: int) -> ComputerState:
        self.mouse.position = (x, y)
        steps = max(1, magnitude // 100)
        if direction == "up": self.mouse.scroll(0, steps)
        elif direction == "down": self.mouse.scroll(0, -steps)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def wait(self, seconds: int) -> ComputerState:
        await asyncio.sleep(seconds)
        return await self.current_state()

    async def go_back(self) -> ComputerState:
        with self.keyboard.pressed(Key.alt):
            self.keyboard.press(Key.left)
            self.keyboard.release(Key.left)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def go_forward(self) -> ComputerState:
        with self.keyboard.pressed(Key.alt):
            self.keyboard.press(Key.right)
            self.keyboard.release(Key.right)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def search(self, query: str) -> ComputerState:
        self._launch_browser(f"https://www.google.com/search?q={quote(query)}", new_window=False)
        await asyncio.sleep(3.0)
        return await self.current_state()

    async def navigate(self, url: str) -> ComputerState:
        if not url.startswith("http"):
            url = f"https://{url}"
        self._launch_browser(url, new_window=False)
        await asyncio.sleep(3.0)
        return await self.current_state()

    async def key_combination(self, keys: Sequence[str]) -> ComputerState:
        mapping = {
            "control": Key.ctrl, "ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift,
            "enter": Key.enter, "tab": Key.tab, "esc": Key.esc, "backspace": Key.backspace,
            "delete": Key.delete, "up": Key.up, "down": Key.down, "left": Key.left,
            "right": Key.right, "space": Key.space,
        }
        real_keys = [mapping.get(k.lower(), k) for k in keys]
        for k in real_keys: self.keyboard.press(k)
        for k in reversed(real_keys): self.keyboard.release(k)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def drag_and_drop(self, x: int, y: int, destination_x: int, destination_y: int) -> ComputerState:
        self.mouse.position = (x, y)
        self.mouse.press(Button.left)
        await asyncio.sleep(0.1)
        self.mouse.position = (destination_x, destination_y)
        await asyncio.sleep(0.1)
        self.mouse.release(Button.left)
        await asyncio.sleep(0.5)
        return await self.current_state()

    async def list_windows(self) -> str:
        """Lists the titles of all open windows using xprop."""
        _env = {**os.environ, "DISPLAY": ":0"}
        try:
            output = subprocess.check_output(
                ["xprop", "-root", "_NET_CLIENT_LIST"], env=_env, text=True
            )
            wids = re.findall(r"0x[0-9a-fA-F]+", output)

            titles = []
            for wid in wids:
                try:
                    title_output = subprocess.check_output(
                        ["xprop", "-id", wid, "_NET_WM_NAME"], env=_env, text=True
                    )
                    match = re.search(r'"(.*?)"', title_output)
                    if match:
                        titles.append(match.group(1))
                except Exception:
                    continue

            return "Open windows:\n" + "\n".join([f"- {t}" for t in sorted(set(titles))])
        except Exception as e:
            return f"Error listing windows: {str(e)}"

    async def focus_window(self, title_substring: str) -> str:
        """Attempts to focus a window by title substring."""
        return await self.find_and_focus_window(title_substring)

    async def find_and_focus_window(self, title_substring: str) -> str:
        """Finds and raises a window across desktops using xprop property toggle hack."""
        _env = {**os.environ, "DISPLAY": ":0"}
        try:
            output = subprocess.check_output(
                ["xprop", "-root", "_NET_CLIENT_LIST"], env=_env, text=True
            )
            wids = re.findall(r"0x[0-9a-fA-F]+", output)

            target_wid = None
            for wid in wids:
                try:
                    title_output = subprocess.check_output(
                        ["xprop", "-id", wid, "_NET_WM_NAME"], env=_env, text=True
                    )
                    if title_substring.lower() in title_output.lower():
                        target_wid = wid
                        break
                except Exception:
                    continue

            if not target_wid:
                return f"FAILED: Could not find window matching '{title_substring}'"

            # Raise to front (property toggle hack)
            subprocess.run(["xprop", "-id", target_wid, "-f", "_NET_WM_STATE", "32a",
                            "-set", "_NET_WM_STATE", "_NET_WM_STATE_STAYS_ON_TOP"], env=_env, check=True)
            subprocess.run(["xprop", "-id", target_wid, "-f", "_NET_WM_STATE", "32a",
                            "-remove", "_NET_WM_STATE", "_NET_WM_STATE_STAYS_ON_TOP"], env=_env, check=True)
            subprocess.run(["xprop", "-id", target_wid, "-f", "_NET_WM_USER_TIME", "32c",
                            "-set", "_NET_WM_USER_TIME", str(int(time.time()))], env=_env, check=True)

            return f"SUCCESS: Raised and focused window (ID: {target_wid})"
        except Exception as e:
            return f"ERROR focusing window: {str(e)}"

    def _get_active_window_title(self) -> str:
        _env = {**os.environ, "DISPLAY": ":0"}
        try:
            out = subprocess.check_output(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"], env=_env, text=True
            )
            wid_match = re.search(r"0x[0-9a-fA-F]+", out)
            if not wid_match:
                return "Unknown"
            wid = wid_match.group(0)
            title_output = subprocess.check_output(
                ["xprop", "-id", wid, "_NET_WM_NAME"], env=_env, text=True
            )
            title_match = re.search(r'"(.*?)"', title_output)
            return title_match.group(1) if title_match else "Unknown"
        except Exception:
            return "Unknown"

    async def environment(self) -> ComputerEnvironment:
        return ComputerEnvironment.ENVIRONMENT_BROWSER
