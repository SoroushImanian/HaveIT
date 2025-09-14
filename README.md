# 🎵 HaveIT - Your Personal YouTube to MP3 Gateway

[![Python Version](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-6.8-blue)](https://core.telegram.org/bots/api)

**HaveIT** is a powerful, self-hosted Telegram bot that allows you to quickly convert and download any YouTube video into a high-quality 320kbps MP3 audio file. The bot operates independently and automatically embeds the original video thumbnail as cover art into the audio file.

This project is designed for private, controlled use, giving you complete authority over who can use the bot and what its operational limits are.

## ✨ Features

- **Superior Audio Quality:** All output files are high-bitrate **320kbps MP3s**.
- **Automatic Cover Art:** The original video thumbnail is automatically embedded into the audio file's metadata.
- **Access Control:** Only users and channels specified in your `ALLOWED_CHAT_IDS` list can interact with the bot.
- **Video Duration Limit:** The bot will not download videos longer than a preset limit (default is 10 minutes) to prevent excessive resource consumption.
- **Cancel Operation:** Users can cancel an ongoing download process via an inline button.
- **User Cooldown:** Each user has a short cooldown period after a successful download before they can request another.
- **High Stability:** Designed to run continuously as a `systemd` service, automatically restarting on failure or server reboot.

## 🚀 Setup and Installation

Follow these steps to set up the bot on your Linux server (Debian/Ubuntu recommended).

### 1. Prerequisites

First, install the necessary system dependencies. `ffmpeg` is essential for audio processing.

```bash
sudo apt update
sudo apt install ffmpeg git python3 python3-pip -y
```

### 2\. Clone the Project

Clone the repository from GitHub and navigate into the project directory.

```bash
git clone https://github.com/SoroushImanian/HaveIT.git
cd HaveIT
```

### 3\. Install Python Libraries

It is highly recommended to use a Python virtual environment.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4\. Configuration

Before running the bot, you must configure a few critical variables.

#### A) Allowed Chat IDs

Open the `HaveIT.py` file and populate the `ALLOWED_CHAT_IDS` list with your numeric user ID and any other authorized user or channel IDs.

  - To find your personal `chat_id`, send a message to [@userinfobot](https://t.me/userinfobot) (info bot).
  - To find a channel's `chat_id`, forward a message from the channel to the info bot.

<!-- end list -->

```python
# In your main Python file
ALLOWED_CHAT_IDS = [123456789, -1001234567890] 
```

#### B) YouTube Cookies (Most Important Step)

To prevent being blocked by YouTube, you must use cookies from a logged-in Google account.

1.  Install the [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) extension on your browser.
2.  Log in to your Google account and visit `youtube.com`.
3.  Click on the extension, press **Export**, then **Export as Netscape**.
4.  Create a file named `youtube-cookies.txt` in the same directory as your script (e.g., `/root/youtube-cookies.txt`) and paste the copied content into it.

### 5\. Running the Bot

For the bot to run permanently in the background and start automatically on reboot, setting up a `systemd` service is the best method.

#### A) Create the Service File

Create a new service file using a text editor like `nano`:

```bash
sudo nano /etc/systemd/system/HaveIT.service
```

Paste the following configuration into the file. **Make sure to replace the placeholder token and verify the file paths.**

```ini
[Unit]
Description=HaveIT - Telegram YouTube Music Downloader Bot
After=network.target

[Service]
# The user that will run the script (e.g., root)
User=root

# The directory where your HaveIT.py and youtube-cookies.txt are located
WorkingDirectory=/root/

# IMPORTANT: Set your Telegram Bot Token here (in YOUR_TELEGRAM_BOT_TOKEN_HERE)
Environment="TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN_HERE"

# The command to execute the bot
# Use `which python3` to find the full path to your python executable
ExecStart=/usr/bin/python3 /root/HaveIT/HaveIT.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save and exit the editor (Ctrl+X, then Y, then Enter).

#### B) Manage the Service

Now, use these commands to enable and run your new service:

```bash
# Reload systemd to recognize the new service file
sudo systemctl daemon-reload

# Enable the service to start automatically on boot
sudo systemctl enable HaveIT.service

# Start the service immediately
sudo systemctl start HaveIT.service
```

Your bot is now running as a persistent background service\!

#### C) Useful Service Commands

  - **Check the status:** `sudo systemctl status HaveIT.service`
  - **View live logs:** `sudo journalctl -u HaveIT.service -f`
  - **Restart the bot:** `sudo systemctl restart HaveIT.service`
  - **Stop the bot:** `sudo systemctl stop HaveIT.service`

## (Usage)

Once set up, simply add the bot as an administrator to your channel or send it a private message.

  - **Send a Link:** Send a YouTube video link to the bot.
  - **Wait:** The bot will display the current processing status.
  - **Receive the File:** Get your high-quality MP3 file, complete with cover art.

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](https://github.com/SoroushImanian/HaveIT/blob/main/LICENSE) file for more details.

---
<div align="center">
  <p><em>“Power belongs to those who seek it”</em></p>
  <br/>
  <p><a href="https://SorBlack.com" target="_blank">Powered by SorBlack</a></p>
</div>
