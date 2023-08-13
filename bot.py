import os
import tempfile
import urllib.request
from contextlib import contextmanager
from typing import Dict, Optional, TypedDict

import openai
import telebot
from telebot.types import Message


class Language(TypedDict):
    code: str
    env_var: str
    prompt: str


LANGUAGES: Dict[str, Language] = {
    "ru": {
        "code": "ru",
        "env_var": "BOT_TOKEN_RU",
        "prompt": "Переведи сообщение с русского языка на сербский.",
    },
    "sr": {
        "code": "sr",
        "env_var": "BOT_TOKEN_SR",
        "prompt": "Переведи сообщение с сербского языка на русский.",
    },
}

SOURCE_LANGUAGE: Optional[Language] = LANGUAGES.get(os.getenv("SOURCE_LANGUAGE") or "")

if not SOURCE_LANGUAGE:
    raise RuntimeError(
        f"Invalid SOURCE_LANGUAGE '{SOURCE_LANGUAGE}' (must be one of: {list(LANGUAGES.keys())})."
    )

TELEGRAM_TOKEN = os.getenv(SOURCE_LANGUAGE["env_var"])
OPENAI_TOKEN = os.getenv("OPENAI_TOKEN")
OPENAI_MODEL = "gpt-3.5-turbo"

PROMPT = (
    SOURCE_LANGUAGE["prompt"]
    + """
Твой ответ должен содержать только переведённый текст, без комментариев.
"""
)


if not TELEGRAM_TOKEN:
    raise RuntimeError(f"Please set {SOURCE_LANGUAGE['env_var']}")

if not OPENAI_TOKEN:
    raise RuntimeError("Please set OPENAI_TOKEN")

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode=None)

openai.api_key = OPENAI_TOKEN


@contextmanager
def handle_errors(chat_id: int):
    try:
        yield
    except Exception as e:
        bot.send_message(chat_id, "‼️" + str(e))


def translate_and_send(chat_id: int, text: str):
    with handle_errors(chat_id):
        completion = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": text},
            ],
        )
        bot.send_message(chat_id, completion.choices[0].message.content)


@bot.message_handler(func=lambda m: True)
def handle_text_message(message: Message):
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, "typing")
    if message.text == "/start":
        bot.send_message(chat_id, "Ну привет")
        return
    if message.text:
        translate_and_send(chat_id, message.text)
        return
    bot.reply_to(message, "чо")


@bot.message_handler(content_types=["voice"])
def handle_voice_message(message: Message):
    assert message.voice
    chat_id = message.chat.id
    bot.send_chat_action(chat_id, "typing")
    with handle_errors(chat_id):
        file_url = bot.get_file_url(message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".oga") as audio_file:
            urllib.request.urlretrieve(file_url, audio_file.name)
            audio_file.seek(0)
            transcript = openai.Audio.transcribe(
                "whisper-1", audio_file, language=SOURCE_LANGUAGE["code"]
            )

    bot.send_message(chat_id, f"Расшифровка: {transcript['text']}\n\nПеревод:")
    translate_and_send(chat_id, transcript["text"])


bot.infinity_polling()
