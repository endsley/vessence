#!/usr/bin/env python3
import argparse
import asyncio
import contextlib
import logging
import os
import pty
import re
import shutil
import signal
import sys
import termios
import time
from typing import Optional, TYPE_CHECKING

_REQUIRED_PYTHON = os.environ.get("ADK_VENV_PYTHON", "")
if _REQUIRED_PYTHON and os.path.exists(_REQUIRED_PYTHON) and sys.executable != _REQUIRED_PYTHON:
	os.execv(_REQUIRED_PYTHON, [_REQUIRED_PYTHON] + sys.argv)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(CURRENT_DIR)
if REPO_ROOT not in sys.path:
	sys.path.insert(0, REPO_ROOT)

from jane.config import (
	JANE_WRAPPER_LOG_BATCH_BYTES,
	JANE_WRAPPER_LOG_FLUSH_INTERVAL,
	JANE_WRAPPER_RAW_LOG,
	GEMINI_READY_TIMEOUT,
	PROCESS_KILL_GRACE,
	TTS_VOICE,
	VESSENCE_DATA_HOME,
)
from jane.tts import TTSEngine

if TYPE_CHECKING:
	from memory.v1.conversation_manager import ConversationManager

logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
	handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("JaneWrapper")

SKILLS_PATH = os.path.join(REPO_ROOT, 'agent_skills')
if SKILLS_PATH not in sys.path:
	sys.path.append(SKILLS_PATH)

ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
DEFAULT_PROMPT_PATTERNS = [
	re.compile(r'Type your message or @path/to/file'),
	re.compile(r'Press / for commands'),
]
NOISE_INDICATORS = [
	"Waiting for auth...",
	"Gemini CLI update available!",
	"Automatic update failed",
	"Ready (user)",
	"Logged in with Google",
	"screen reader-friendly view",
	"YOLO mode",
	"~ no sandbox",
	"Logging in...",
	"Logged in.",
	"Updated successfully",
	"update manually",
]


class JaneSessionWrapper:
	def __init__(self, debug: bool = False, session_id: Optional[str] = None):
		self.debug = debug
		self.session_id = session_id or f"session_{int(time.time())}"
		self.conv_manager: Optional[ConversationManager] = None
		self.process: Optional[asyncio.subprocess.Process] = None
		self.master_fd: Optional[int] = None
		self.loop = asyncio.get_running_loop()

		self.exiting = False
		self.last_sigint_time = 0.0
		self.reader_task: Optional[asyncio.Task] = None

		self.memory_lock = asyncio.Lock()
		self.restart_lock = asyncio.Lock()
		self.signal_lock = asyncio.Lock()
		self.ready_event = asyncio.Event()
		self.process_generation = 0
		self.pending_summary: Optional[str] = None
		self.pending_commit_tasks: set[asyncio.Task] = set()
		self.shutdown_task: Optional[asyncio.Task] = None
		self.log_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
		self.log_writer_task: Optional[asyncio.Task] = None
		self.tts = TTSEngine()

		self.raw_log_path = JANE_WRAPPER_RAW_LOG
		os.makedirs(os.path.dirname(self.raw_log_path), exist_ok=True)
		with open(self.raw_log_path, "a", encoding="utf-8") as f:
			f.write(f"\n--- SESSION START: {self.session_id} ---\n")

		if self.debug:
			logger.setLevel(logging.DEBUG)

	async def initialize(self):
		gemini_path = shutil.which("gemini")
		if not gemini_path:
			logger.error("The 'gemini' command was not found in your PATH.")
			sys.exit(1)

		db_path = os.path.join(VESSENCE_DATA_HOME, 'memory/v1/vector_db', 'sessions', self.session_id)
		if os.path.exists(db_path):
			shutil.rmtree(db_path)

		try:
			from memory.v1.conversation_manager import ConversationManager
			self.conv_manager = await self.loop.run_in_executor(None, ConversationManager, self.session_id)
		except Exception as e:
			logger.error(f"Failed to initialize ConversationManager: {e}")
			sys.exit(1)

		for sig in (signal.SIGINT, signal.SIGTERM):
			self.loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.handle_signal(s)))

		logger.info(f"Initialized Session: {self.session_id} | Mode: {'DEBUG' if self.debug else 'NORMAL'}")
		self.log_writer_task = asyncio.create_task(self._log_writer_loop())

	async def handle_signal(self, sig: signal.Signals):
		async with self.signal_lock:
			if self.exiting:
				return

			if sig == signal.SIGINT:
				now = time.time()
				if now - self.last_sigint_time < 1.0:
					logger.info("\n[Signal] Double Ctrl+C detected. Shutting down...")
					await self.shutdown()
					return

				self.last_sigint_time = now
				if self.process and self.process.returncode is None:
					logger.info("\n[Signal] Forwarding interrupt to Gemini...")
					self.process.send_signal(signal.SIGINT)
				else:
					logger.info("\n[Signal] Gemini is not running. Use Ctrl+C again within 1s to exit.")
			else:
				logger.info(f"\n[Signal] Received {sig.name}. Shutting down...")
				await self.shutdown()

	def _log_raw(self, text: str):
		if text:
			self.log_queue.put_nowait(text)

	async def _append_raw_log(self, text: str):
		def _write():
			with open(self.raw_log_path, "a", encoding="utf-8") as f:
				f.write(text)
				f.flush()

		await asyncio.to_thread(_write)

	async def _log_writer_loop(self):
		buffer: list[str] = []
		buffer_bytes = 0

		while True:
			try:
				item = await asyncio.wait_for(self.log_queue.get(), timeout=JANE_WRAPPER_LOG_FLUSH_INTERVAL)
			except asyncio.TimeoutError:
				item = None

			if item is None:
				if buffer:
					await self._append_raw_log("".join(buffer))
					buffer.clear()
					buffer_bytes = 0
				if self.exiting and self.log_queue.empty():
					return
				continue

			buffer.append(item)
			buffer_bytes += len(item.encode("utf-8", errors="ignore"))
			if buffer_bytes >= JANE_WRAPPER_LOG_BATCH_BYTES:
				await self._append_raw_log("".join(buffer))
				buffer.clear()
				buffer_bytes = 0

	def _is_meaningful_text(self, text: str) -> bool:
		stripped = text.strip()
		if len(stripped) <= 5:
			return False
		for indicator in NOISE_INDICATORS:
			if indicator in stripped and len(stripped) < len(indicator) + 20:
				return False
		return True

	def _extract_prompt_split(self, text: str):
		for pattern in DEFAULT_PROMPT_PATTERNS:
			match = pattern.search(text)
			if match:
				return text[:match.start()], text[match.end():], match.group(0)
		return None, None, None

	def _normalize_output(self, text: str) -> str:
		return ANSI_ESCAPE_RE.sub('', text).replace('\r\n', '\n').replace('\r', '\n').strip()

	def _schedule_commit(self, role: str, content: str):
		if self.exiting:
			return

		task = asyncio.create_task(self._commit_message(role, content))
		self.pending_commit_tasks.add(task)

		def _discard(done_task: asyncio.Task):
			self.pending_commit_tasks.discard(done_task)

		task.add_done_callback(_discard)

	async def write_to_master(self, data: str):
		fd = self.master_fd
		if fd is None:
			raise RuntimeError("No PTY master FD available.")
		try:
			self._log_raw(f"\n[USER_INPUT] {repr(data)}\n")
			os.write(fd, data.encode())
		except OSError as e:
			logger.error(f"Write error: {e}")
			raise

	async def close_process(self):
		proc = self.process
		fd = self.master_fd
		self.process = None
		self.master_fd = None
		self.ready_event.clear()

		if proc and proc.returncode is None:
			proc.terminate()
			try:
				await asyncio.wait_for(proc.wait(), timeout=PROCESS_KILL_GRACE)
			except asyncio.TimeoutError:
				proc.kill()
				try:
					await asyncio.wait_for(proc.wait(), timeout=PROCESS_KILL_GRACE)
				except asyncio.TimeoutError:
					logger.warning("Gemini process did not exit cleanly after kill().")

		if fd is not None:
			try:
				os.close(fd)
			except OSError:
				pass

	async def spawn_gemini(self):
		await self.close_process()

		master_fd, slave_fd = pty.openpty()
		try:
			attr = termios.tcgetattr(slave_fd)
			attr[3] = attr[3] & ~termios.ECHO
			termios.tcsetattr(slave_fd, termios.TCSANOW, attr)
		except Exception as e:
			logger.debug(f"Could not disable ECHO: {e}")

		os.set_blocking(master_fd, False)
		self.ready_event.clear()

		logger.info("Spawning gemini CLI process...")
		proc = await asyncio.create_subprocess_exec(
			"gemini", "--approval-mode=yolo", "--output-format", "text", "--screen-reader",
			stdin=slave_fd,
			stdout=slave_fd,
			stderr=slave_fd,
			cwd=os.path.expanduser("~"),
		)
		os.close(slave_fd)

		self.master_fd = master_fd
		self.process = proc
		self.process_generation += 1
		logger.debug(f"Spawned Gemini generation {self.process_generation} pid={proc.pid}")

	async def restart_gemini(self, summary_text: Optional[str] = None):
		async with self.restart_lock:
			if self.exiting:
				return

			await self.spawn_gemini()
			try:
				await asyncio.wait_for(self.ready_event.wait(), timeout=GEMINI_READY_TIMEOUT)
			except asyncio.TimeoutError:
				logger.error("Gemini did not become ready after restart.")
				return

			if summary_text:
				logger.info("Injecting context summary into new Gemini session...")
				await self.write_to_master(f"CONTEXT SUMMARY:\n{summary_text}\n\n")
				await self.write_to_master("Please acknowledge internally and continue.\n")

	async def _commit_message(self, role: str, content: str):
		if not self.conv_manager:
			return

		summary = None
		async with self.memory_lock:
			try:
				summary = await self.loop.run_in_executor(
					None,
					self.conv_manager.add_message,
					{"role": role, "content": content},
				)
			except Exception as e:
				logger.error(f"Memory sync error for {role}: {e}")
				return

			if self.debug:
				try:
					stats = self.conv_manager.get_stats()
					logger.debug(f"Context: {stats['usage_percent']}% ({stats['current_tokens']} tokens)")
				except Exception as e:
					logger.debug(f"Could not fetch stats: {e}")

		if summary and not self.exiting:
			logger.info("Context threshold reached. Restarting Gemini with summary...")
			self.pending_summary = summary
			try:
				await self.restart_gemini(summary_text=summary)
			finally:
				if self.pending_summary == summary:
					self.pending_summary = None

	async def read_from_gemini(self):
		response_buffer = ""
		local_generation = self.process_generation

		while not self.exiting:
			if self.master_fd is None:
				await asyncio.sleep(0.1)
				continue

			if local_generation != self.process_generation:
				response_buffer = ""
				local_generation = self.process_generation

			try:
				try:
					data_bytes = os.read(self.master_fd, 4096)
				except (BlockingIOError, InterruptedError):
					data_bytes = None
				except OSError as e:
					if self.exiting:
						return
					logger.debug(f"PTY read OSError: {e}")
					await asyncio.sleep(0.1)
					continue

				if not data_bytes:
					await asyncio.sleep(0.05)
					continue

				data = data_bytes.decode(errors='ignore')
				self._log_raw(data)
				sys.stdout.write(data)
				sys.stdout.flush()
				response_buffer += data

				assistant_turn_raw, remainder, matched_prompt = self._extract_prompt_split(response_buffer)
				if matched_prompt is None:
					continue

				self.ready_event.set()
				response_buffer = remainder or ""

				clean_text = self._normalize_output(assistant_turn_raw)

				if self._is_meaningful_text(clean_text):
					logger.info(f"Captured response ({len(clean_text)} chars). Committing to memory...")
					await self._commit_message("assistant", clean_text)
					await self.tts.speak(clean_text)
			except asyncio.CancelledError:
				raise
			except Exception as e:
				if not self.exiting:
					logger.error(f"Read loop error: {e}")
				await asyncio.sleep(0.25)

	async def run_loop(self):
		await self.restart_gemini()
		print("--- Jane Pro-Wrapper Started ---")
		print("Ctrl+C to interrupt, double Ctrl+C to quit.")
		print("Commands: /exit /quit /debug /restart /status /tts")
		if self.tts.enabled:
			print(f"TTS enabled (voice: {TTS_VOICE}). Use /tts to toggle, /tts stop to interrupt.")

		self.reader_task = asyncio.create_task(self.read_from_gemini())

		while not self.exiting:
			try:
				user_input = await self.loop.run_in_executor(None, input, "You: ")
			except EOFError:
				logger.warning("No interactive terminal found. Waiting for external interaction or exit.")
				while not self.exiting:
					await asyncio.sleep(10)
				break

			text = user_input.strip()
			if not text:
				continue

			if user_input.startswith('\x1b') or len(user_input) > 5000:
				if self.debug:
					logger.debug(f"Ignoring likely terminal noise in input: {user_input[:80]}...")
				continue

			if text.lower() in ['/exit', '/quit']:
				break

			if text.lower() == '/debug':
				self.debug = not self.debug
				logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
				print(f"--- Debug Mode: {'ON' if self.debug else 'OFF'} ---")
				continue

			if text.lower() == '/tts':
				self.tts.enabled = not self.tts.enabled
				print(f"--- TTS: {'ON' if self.tts.enabled else 'OFF'} ---")
				continue

			if text.lower() == '/tts stop':
				await self.tts.stop()
				print("--- TTS: stopped current speech ---")
				continue

			if text.lower() == '/restart':
				await self.restart_gemini(summary_text=self.pending_summary)
				continue

			if text.lower() == '/status':
				proc_state = "running" if self.process and self.process.returncode is None else "stopped"
				print(f"process={proc_state} generation={self.process_generation} ready={self.ready_event.is_set()}")
				continue

			if not self.process or self.process.returncode is not None:
				logger.error("Gemini process is not running. Restarting...")
				await self.restart_gemini(summary_text=self.pending_summary)

			try:
				await asyncio.wait_for(self.ready_event.wait(), timeout=GEMINI_READY_TIMEOUT)
			except asyncio.TimeoutError:
				logger.error("Gemini is not ready to accept input. Restarting...")
				await self.restart_gemini(summary_text=self.pending_summary)
				try:
					await asyncio.wait_for(self.ready_event.wait(), timeout=GEMINI_READY_TIMEOUT)
				except asyncio.TimeoutError:
					logger.error("Gemini failed to become ready after retry.")
					continue

			try:
				await self.write_to_master(user_input + "\n")
			except Exception:
				logger.error("Failed to send input. Restarting Gemini...")
				await self.restart_gemini(summary_text=self.pending_summary)
				continue

			self._schedule_commit("user", user_input)

		await self.shutdown()

	async def shutdown(self):
		if self.shutdown_task:
			await self.shutdown_task
			return

		self.shutdown_task = asyncio.create_task(self._shutdown_impl())
		try:
			await self.shutdown_task
		finally:
			self.shutdown_task = None

	async def _shutdown_impl(self):
		if self.exiting:
			return
		self.exiting = True

		if self.reader_task and not self.reader_task.done():
			self.reader_task.cancel()
			try:
				await self.reader_task
			except asyncio.CancelledError:
				pass

		if self.pending_commit_tasks:
			results = await asyncio.gather(*list(self.pending_commit_tasks), return_exceptions=True)
			for result in results:
				if isinstance(result, Exception):
					logger.error(f"Pending memory sync failed during shutdown: {result}")

		if self.conv_manager:
			logger.info("Running end-of-session archival and cleanup...")
			try:
				await self.loop.run_in_executor(None, self.conv_manager.close)
				logger.info("Archival and cleanup complete.")
			except Exception as e:
				logger.error(f"Archival failed: {e}")

		await self.tts.shutdown()
		await self.close_process()
		if self.log_writer_task and not self.log_writer_task.done():
			self.log_queue.put_nowait(None)
			with contextlib.suppress(asyncio.CancelledError):
				await self.log_writer_task
		logger.info("Session closed.")


async def main():
	parser = argparse.ArgumentParser(description="Jane Pro-Wrapper")
	parser.add_argument("--debug", action="store_true")
	parser.add_argument("--session-id")
	args = parser.parse_args()

	wrapper = JaneSessionWrapper(debug=args.debug, session_id=args.session_id)
	await wrapper.initialize()
	await wrapper.run_loop()


if __name__ == "__main__":
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		pass
