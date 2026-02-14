<div align="center">

<div align="center">
  <img height="480" src="img/HaveIT.png"/>
</div>

# 🎵 HaveIT (v2.0)
### The Intelligent & Secured Music Gateway

[![Python Version](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot-API-2CA5E0?style=flat&logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![Network Layer](https://img.shields.io/badge/Network-Cloudflare%20Warp-F38020?style=flat&logo=cloudflare&logoColor=white)](https://one.one.one.one/)

<p align="center">
  <b>Universal Music Assistant • User Management System • Global Caching • High-Fidelity Audio</b>
</p>

</div>

---

## 📖 Introduction

**HaveIT v2.0** is a massive leap forward. It is no longer just a downloader, but a fully managed **Audio Platform**. 

This version introduces a robust **Authentication System** where users must request access to use the bot. Administrators have full control via a GUI-based **Admin Panel** to approve, deny, or block users. It also features a **Global Caching System** to save bandwidth and **Personal Channel Integration**, allowing users to forward downloads directly to their own Telegram channels.

---

## ✨ New Features (v2.0)

### 🔐 Security & User Management
- **Request-Based Access:** New users must request access. Admins receive a notification with the user's profile and bio to Approve or Deny.
- **🎛️ Graphic Admin Panel:** A dedicated GUI panel for admins to:
  - View real-time statistics (Active, Pending, Blocked users).
  - Manage user permissions with one click.
  - Silent banning/blocking capabilities.
- **🛡️ Real-Time Security:** If a user is blocked while downloading a file, the process is **immediately terminated** to save server resources.

### 💾 Performance & Caching
- **⚡ Global Caching:** Files are uploaded once to a private **Cache Channel**. Subsequent requests for the same song are fetched instantly from Telegram servers (zero download time, zero bandwidth usage).
- **🧠 Smart Engine V6:** Improved fuzzy matching algorithm to find the exact song on YouTube, SoundCloud, or Spotify.

### 📢 User Features
- **📣 Channel Connectivity:** Users can connect their own Telegram Channel in `/settings`. The bot will automatically forward the downloaded music + banner to their channel.
- **📝 Lyrics Fetching:** Fetches synced or plain lyrics from Genius/LrcLib.
- **🎧 Audiophile Quality:** Enforces **320kbps MP3** with embedded high-res cover art and ID3 tags.

---

## 🛠️ Prerequisites

- **Python 3.10+**
- **FFmpeg** (Core media processing engine)
- **Cloudflare Warp** (Required for network routing layer)

### 1. Install Dependencies
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install ffmpeg python3 python3-pip git -y

```

### 2. Configure Cloudflare Warp (Proxy)

HaveIT uses a proxy to bypass restrictions and keep the connection stable.

```bash
# Install Warp
curl -fsSL [https://pkg.cloudflareclient.com/pubkey.gpg](https://pkg.cloudflareclient.com/pubkey.gpg) | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] [https://pkg.cloudflareclient.com/](https://pkg.cloudflareclient.com/) $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt-get update && sudo apt-get install cloudflare-warp

# Configure Port 3420
warp-cli registration new
warp-cli mode proxy
warp-cli proxy port 3420
warp-cli connect

```

---

## 🚀 Installation & Configuration

### 1. Clone the Repository

```bash
git clone [https://github.com/SoroushImanian/HaveIT.git](https://github.com/SoroushImanian/HaveIT.git)
cd HaveIT

```

### 2. Install Python Libraries

```bash
pip install -r requirements.txt

```

### 3. ⚙️ Critical Configuration

You must configure the bot before running it.

#### A. Setup Admin IDs (database.py)

Open `database.py` and set your numeric Telegram ID. Only these IDs will see the Admin Panel.
*(Get your ID from @userinfobot)*

```python
# database.py

# Replace with your numeric ID(s)
ADMIN_IDS = [93365812, 123456789] 

```

#### B. Setup Cache Channel (HaveIT.py)

Create a **Private Channel** on Telegram and add your bot as an **Administrator**.
Get the Channel ID (usually starts with -100).

Open the main bot file (e.g., `HaveIT.py`) and edit the configuration section:

```python
# HaveIT.py (Configuration Section)

# 1. Your Bot Token (Or use Environment Variable)
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# 2. Your Proxy (Cloudflare Warp)
PROXY_URL = 'socks5://127.0.0.1:3420'

# 3. Cache Channel ID (Required for caching system)
# The bot must be admin in this channel!
CACHE_CHANNEL_ID = -1001234567890 

```

---

## 🤖 Usage

1. **Start the Bot:**
Run `python3 HaveIT.py`.
2. **First Interaction:**
Send `/start`. If you are not an Admin, you will see a "Request Access" button.
3. **Approval:**
The Admin receives the request and approves it via the panel.
4. **Download:**
* Send a Name (`Saghie - Hayedeh`)
* Send a Link (Spotify/YouTube/SoundCloud)


5. **Connect User Channel:**
Go to `/settings` -> "Connect New Channel" to forward music to your own channel.

---

## 🖥️ Running as a Service

To keep the bot running 24/7 in the background:

1. **Create Service File:**

```bash
sudo nano /etc/systemd/system/HaveIT.service

```

2. **Paste Configuration:**

```ini
[Unit]
Description=HaveIT Audio Assistant
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/HaveIT
Environment="TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE"
ExecStart=/usr/bin/python3 /root/HaveIT/HaveIT.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

```

3. **Start Service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable HaveIT
sudo systemctl start HaveIT

```

---

## 📜 License

This project is open-source and available under the **MIT License**.

<div align="center">
<p><em>“Power belongs to those who seek it”</em></p>
<p><a href="https://SorBlack.com" target="_blank">Powered by SorBlack</a></p>
</div>

```

```
