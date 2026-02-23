# Ebook Sender Bot

# TODO
- document, easify setup (STKCLIENT_CLIENT_PATH, KINDLE_DEVICE_SERIALS)
- read book meta data using calibre
- check metada using LLM before sending
- show sent metadata in bot
- fix shell.nix to do install venv

A small Telegram bot that accepts ebook files and forwards them to your Kindle devices through the unofficial `stkclient` package. The bot runs on Python and `python-telegram-bot` v20, so everything is asynchronous and easy to host on any machine that can reach Telegram and Amazon.

## Features
- `/start` and `/help` commands with basic instructions.
- Accepts `pdf`, `epub`, `mobi`, `azw3`, and `txt` documents uploaded as Telegram files.
- Streams uploads to a temporary directory and forwards them to any owned Kindle device using `stkclient`.
- Guards against unsupported file types and oversized uploads.
- Structured logging for both Telegram events and Kindle delivery attempts.

## Prerequisites
- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather).
- A serialized `stkclient` client (see **Authorizing stkclient** below) with access to the Kindle account you want to use.

## Configuration
All runtime configuration is handled through environment variables. Copy the example file and fill values:

```bash
cp .env.example .env
```

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token you receive from BotFather. |
| `STKCLIENT_CLIENT_PATH` | Path to the serialized `stkclient` client JSON file. |
| `KINDLE_DEVICE_SERIALS` | Optional comma-separated list of device serial numbers to target. Leave blank to auto-send to all owned devices. |

You can also set the variables directly in your shell or hosting provider (Docker, systemd, etc.).

If the file referenced by `STKCLIENT_CLIENT_PATH` does not exist when the bot starts, it will print an OAuth sign-in URL, prompt you for the final redirect URL, and save a fresh client file automatically. When `KINDLE_DEVICE_SERIALS` is empty, the bot enumerates owned Kindle devices and logs their serial numbers so you can copy/paste the ones you care about.

## Installation

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

If you use Nix, drop into the provided dev shell:

```bash
nix-shell
```

## Running the bot

```bash
uv run python -m ebook_sender
```

By default the bot uses long polling. If you want to run it behind a webhook you can adapt `create_application()` in `src/ebook_sender/bot.py`.

## Running with Docker

Build the image:

```bash
docker build -t ebook-sender-bot .
```

Run it with your `.env` file and a mounted `client.json` (override the path inside the container):

```bash
docker run --rm \
  --env-file .env \
  -e STKCLIENT_CLIENT_PATH=/data/client.json \
  -v $(pwd)/client.json:/data/client.json:ro \
  ebook-sender-bot
```

Adjust the bind mount if your serialized client lives elsewhere. You can pass additional overrides like `LOG_LEVEL` through `-e` flags.

## Authorizing `stkclient`
`stkclient` currently exposes an OAuth2 flow to create a reusable client file. Run the following one-time steps on a trusted machine:

```python
import stkclient

oauth = stkclient.OAuth2()
signin_url = oauth.get_signin_url()
print(signin_url)
# open the URL, finish Amazon's authorization, then copy the final redirect URL
client = oauth.create_client(redirect_url)

with open("client.json", "w") as fh:
    client.dump(fh)
```

Copy the generated `client.json` to your bot host and point `STKCLIENT_CLIENT_PATH` to it. You can refresh/replace the file whenever you re-authorize.

> Tip: You can skip these manual steps and simply run the bot once; it will output the sign-in link, ask for the redirect URL, and create the client file in-place if it does not exist.

## Notes on `stkclient`
The package is reverse-engineered and has changed APIs over time. The helper in `src/ebook_sender/kindle.py` loads your serialized OAuth2 client, fetches owned devices, and calls `client.send_file(...)`. If your installed version exposes different return types or field names, tweak the `KindleSender` class accordingly.

## Development
- Format/lint however you prefer; the project intentionally avoids locking you into a specific toolchain.
- Add tests (e.g., using `pytest`) if you extend the bot beyond a personal script.

## Roadmap ideas
- Persist sent files and throttle resends.
- Support inline queries for previously uploaded titles.
- Add webhook support for production hosting.
