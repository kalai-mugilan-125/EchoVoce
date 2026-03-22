"""
services/llm_service.py
───────────────────────
LLM inference using llama-cpp-python (GGUF models, CPU + optional GPU).

• Loads a GGUF model (Mistral, LLaMA, Qwen, etc.) via llama-cpp-python
• CPU mode: n_gpu_layers=0 (set in .env)
• GPU mode: n_gpu_layers=-1 to offload all layers
• Supports streaming token generation for low-latency responses
• Automatically formats prompt using the model's chat template

IMPORTANT: llama-cpp-python is NOT thread-safe. A threading.Lock ensures
only one inference runs at a time — prevents the OSError access violation
that occurs when two WebSocket sessions call the LLM concurrently.
"""

import threading
from typing import Generator
from llama_cpp import Llama
from core.config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class LLMService:
    def __init__(self):
        self._model: Llama | None = None
        self._is_loaded = False
        self._lock = threading.Lock()  # serialise all inference calls

    def load(self):
        """Load GGUF model. Called once at startup."""
        if self._is_loaded:
            return

        model_path = str(settings.llm_model_abs)
        logger.info(
            f"Loading LLM: {model_path} | "
            f"n_ctx={settings.LLM_N_CTX} | "
            f"n_gpu_layers={settings.LLM_N_GPU_LAYERS} | "
            f"n_threads={settings.LLM_N_THREADS}"
        )

        self._model = Llama(
            model_path=model_path,
            n_ctx=settings.LLM_N_CTX,
            n_threads=settings.LLM_N_THREADS,
            n_gpu_layers=settings.LLM_N_GPU_LAYERS,  # 0 = pure CPU
            verbose=False,
            chat_format="mistral-instruct",  # works for Mistral, LLaMA 3
        )
        self._is_loaded = True
        logger.info("LLM ready")

    def generate(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> str | Generator:
        """
        Generate a response from conversation history.

        Args:
            messages: List of {role, content} dicts (system + history + user)
            stream:   If True, returns a token generator

        Returns:
            Full response string (stream=False) or token generator (stream=True)
        """
        if not self._is_loaded:
            self.load()

        if stream:
            return self._stream(messages)
        return self._complete(messages)

    def _complete(self, messages: list[dict]) -> str:
        """
        Blocking completion — returns full text at once.
        Acquires the lock so only one thread runs inference at a time.
        """
        with self._lock:
            try:
                response = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                    stream=False,
                )
                text = response["choices"][0]["message"]["content"].strip()
                logger.info(f"LLM response ({len(text)} chars)")
                return text
            except Exception as e:
                logger.error(f"LLM inference error: {e}")
                return "I'm sorry, I encountered an error. Could you please repeat that?"

    def _stream(self, messages: list[dict]) -> Generator[str, None, None]:
        """
        Streaming generator — yields tokens as they are produced.
        Lock held for the entire stream duration.
        """
        with self._lock:
            try:
                stream = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=settings.LLM_MAX_TOKENS,
                    temperature=settings.LLM_TEMPERATURE,
                    stream=True,
                )
                for chunk in stream:
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        yield token
            except Exception as e:
                logger.error(f"LLM stream error: {e}")
                yield "I'm sorry, I encountered an error."

    def generate_stream_sentences(
        self, messages: list[dict]
    ) -> Generator[str, None, None]:
        """
        Yields complete sentences from the LLM stream.
        Buffers tokens until a sentence-ending punctuation is found,
        then yields the full sentence.
        """
        buffer = ""
        sentence_endings = {".", "!", "?"}

        for token in self._stream(messages):
            buffer += token

            for i, char in enumerate(buffer):
                if char in sentence_endings:
                    sentence = buffer[: i + 1].strip()
                    if len(sentence) > 10:
                        yield sentence
                        buffer = buffer[i + 1:]
                        break

        remaining = buffer.strip()
        if remaining:
            yield remaining


# Singleton
llm_service = LLMService()
