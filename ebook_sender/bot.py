from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings, load_settings
from .kindle import KindleSender
from .metadata import EbookMetadata, extract_metadata

LOGGER = logging.getLogger(__name__)
ALLOWED_EXTENSIONS: set[str] = {"pdf", "epub", "mobi", "azw3", "txt"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB
BOT_DATA_KINDLE_KEY = "kindle_sender"


def _extension_from_name(name: str | None) -> str:
    if not name:
        return ""
    return Path(name).suffix.lower().lstrip(".")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send me an ebook file (PDF, EPUB, MOBI, AZW3, TXT) and I will forward it "
        "to your Kindle devices."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Upload a supported ebook document. Make sure you authorized stkclient for your "
        "Amazon account and that your Kindle device shows up in the client file."
    )


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.document:
        return

    document = message.document
    extension = _extension_from_name(document.file_name)

    if extension not in ALLOWED_EXTENSIONS:
        await message.reply_text("Unsupported file type. Allowed: " + ", ".join(sorted(ALLOWED_EXTENSIONS)))
        return

    if document.file_size and document.file_size > MAX_FILE_SIZE:
        await message.reply_text("File is too large. Please keep it under 200 MB.")
        return

    kindle_sender: KindleSender = context.bot_data[BOT_DATA_KINDLE_KEY]

    await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)
    downloading_msg = await message.reply_text("Downloading your document...")

    try:
        temp_path = await _download_document(context, document, extension)
    except Exception as exc:  # pragma: no cover - defensive guard
        LOGGER.exception("Failed to download document")
        await downloading_msg.edit_text(f"Download failed: {exc}")
        return

    try:
        metadata = await asyncio.to_thread(extract_metadata, temp_path, extension.upper())
        await _maybe_show_metadata(message, metadata)

        await downloading_msg.edit_text("Uploading to Kindle...")
        await kindle_sender.send(temp_path, metadata)
    except Exception as exc:  # pragma: no cover - defensive guard
        LOGGER.exception("Failed to send document to Kindle")
        await downloading_msg.edit_text(f"Delivery failed: {exc}")
    else:
        await downloading_msg.edit_text("Delivered to Kindle ✅")
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            LOGGER.warning("Could not delete temp file %s", temp_path)


def create_application(settings: Settings) -> Application:
    kindle_sender = KindleSender(
        client_path=settings.stkclient_client_path,
        device_serials=settings.device_serials,
    )

    application = ApplicationBuilder().token(settings.telegram_token).build()
    application.bot_data[BOT_DATA_KINDLE_KEY] = kindle_sender

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, document_handler))

    application.add_error_handler(error_handler)
    return application


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.error("Telegram error", exc_info=context.error)


async def _download_document(
    context: ContextTypes.DEFAULT_TYPE,
    document,
    extension: str,
) -> Path:
    telegram_file = await context.bot.get_file(document.file_id)

    suffix = f".{extension}" if extension else ""
    fd, temp_path_str = tempfile.mkstemp(prefix="ebook-sender-", suffix=suffix)
    os.close(fd)
    temp_path = Path(temp_path_str)

    await telegram_file.download_to_drive(custom_path=temp_path_str)
    return temp_path


async def _maybe_show_metadata(message, metadata: EbookMetadata) -> None:
    if not message:
        return

    lines: list[str] = []
    if metadata.title:
        lines.append(f"Title: {metadata.title}")
    if metadata.authors:
        lines.append("Author(s): " + ", ".join(metadata.authors))

    if lines:
        await message.reply_text("Metadata:\n" + "\n".join(lines))


def run() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    settings = load_settings()
    application = create_application(settings)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    run()
