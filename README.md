<div align="center">

<div align="center">
  <img height="200"src="img\HaveIT.png"/>
</div>

# 🎵 HaveIT
### The Intelligent Music Gateway

[![Python Version](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat)](https://opensource.org/licenses/MIT)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot-API-2CA5E0?style=flat&logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![Network Layer](https://img.shields.io/badge/Network-Cloudflare%20Warp-F38020?style=flat&logo=cloudflare&logoColor=white)](https://one.one.one.one/)

<p align="center">
  <b>Universal Music Assistant • High-Fidelity Audio • Smart Metadata • Secure Routing</b>
</p>

</div>

---

## 📖 Introduction

**HaveIT** is your personal, self-hosted **Audio Assistant**. Designed as a centralized hub for your music needs, HaveIT acts as an intelligent bridge between web streaming libraries and your personal collection.

Built on a modular and robust architecture, HaveIT integrates a **secure network tunneling layer** to ensure high-speed data transfer and consistent connectivity. Whether processing a soundtrack or a music stream, the assistant delivers crystal-clear **320kbps MP3s** with embedded cover art and rich metadata directly to your chat interface.

## ✨ Features

- **🧠 Smart Engine:** Automatically identifies source URLs and optimizes the extraction process for the best results.
- **🌐 Enhanced Connectivity:** Leverages **Cloudflare Warp** infrastructure to ensure stable, low-latency data streaming and maximum uptime.
- **🎧 Audiophile Standard:** Enforces a strict **320kbps** bitrate encoding for a premium listening experience.
- **🖼️ Intelligent Metadata:** Automatically fetches, processes, and embeds high-resolution album art and ID3 tags.
- **🛡️ Private Ecosystem:** Operates exclusively within your defined `ALLOWED_CHAT_IDS`, ensuring resource privacy.
- **⚡ Live Telemetry:** Provides real-time feedback and progress bars for download and conversion tasks.
- **🧹 Automated Maintenance:** Features an auto-cleanup routine to manage temporary assets and maintain server hygiene.

---

## 🛠️ Prerequisites

To deploy your assistant, ensure your Linux environment (Ubuntu 20.04/22.04 recommended) meets the following requirements:

- **Python 3.10+**
- **FFmpeg** (Core media processing engine)
- **Git**
- **Cloudflare Warp** (Required for network routing layer)

### 1. Install System Dependencies
Update your system and install the necessary packages:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install ffmpeg python3 python3-pip git -y

```

### 2. Configure Network Layer (Cloudflare Warp)

HaveIT relies on a modern network tunnel to handle data streams efficiently and securely. We utilize Cloudflare Warp as the underlying transport layer for optimal performance.

**A) Install the Client:**

```bash
# Add GPG Key
curl -fsSL [https://pkg.cloudflareclient.com/pubkey.gpg](https://pkg.cloudflareclient.com/pubkey.gpg) | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg

# Add Repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] [https://pkg.cloudflareclient.com/](https://pkg.cloudflareclient.com/) $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list

# Install Package
sudo apt-get update && sudo apt-get install cloudflare-warp

```

**B) Initialize Proxy Interface (Port 3420):**
Configure the client to operate in proxy mode on port `3420` to route the assistant's traffic.

```bash
warp-cli registration new
warp-cli mode proxy
warp-cli proxy port 3420
warp-cli connect

```

**C) Verify Network Status:**
Ensure the tunnel is active and routing traffic correctly:

```bash
curl -x socks5://127.0.0.1:3420 ifconfig.me
# Output should reflect the routed network IP.

```

---

## 🚀 Deployment

### 1. Clone the Repository

```bash
git clone [https://github.com/SoroushImanian/HaveIT.git](https://github.com/SoroushImanian/HaveIT.git)
cd HaveIT

```

### 2. Install Python Requirements

```bash
pip install -r requirements.txt

```

*(Core libs: `python-telegram-bot`, `yt-dlp`, `mutagen`, `requests`)*

### 3. Configuration

Open `HaveIT.py` and customize your assistant's settings:

```python
# 1. Access Control: Add your numeric ID (Get it from @userinfobot)
ALLOWED_CHAT_IDS = [123456789, 987654321]

# 2. Network Routing: Match this with your Warp port (Step 2B)
PROXY_URL = 'socks5://127.0.0.1:3420'

```

---

## 🤖 Running as a Service (Recommended)

For a production-grade deployment, run HaveIT as a background system service.

1. **Create Service File:**
```bash
sudo nano /etc/systemd/system/HaveIT.service

```


2. **Paste Configuration:**
*(Replace `YOUR_BOT_TOKEN_HERE` with your actual API token)*
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


3. **Activate the Service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable HaveIT
sudo systemctl start HaveIT

```


4. **Monitor Status:**
```bash
sudo systemctl status HaveIT

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
