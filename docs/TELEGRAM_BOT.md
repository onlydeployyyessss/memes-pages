# 🤖 Telegram Bot setup

## 1. Create the bot

1. Open [@BotFather](https://t.me/BotFather) → `/newbot`
2. Name: `MEMES PAGES` · username: e.g. `memes_pages_agent_bot`
3. Copy the token → `MEMES_BOT_TOKEN` in your `.env`

## 2. Authorize yourself

- Send any message to the bot, or use [@userinfobot](https://t.me/userinfobot),
  to find your numeric Telegram ID.
- Put it (comma-separated list supported) into `MEMES_ADMIN_TELEGRAM_IDS`.
- Only these IDs (plus `users` rows flagged `is_admin`) can use the bot.

## 3. Run

```bash
python -m telegram_bot.bot     # polling (default)
# or webhook behind HTTPS:
MEMES_WEBHOOK_URL=https://your-domain  python -m telegram_bot.bot   # serves :8080/telegram/webhook
```

## 4. Main menu

```
🤖 MEMES PAGES
📊 Dashboard    📱 Accounts    🔥 Trending    🎬 Content
📥 Queue        📅 Schedule    📝 Captions    🖼 Covers
📈 Analytics    📄 Reports     ⚙️ Settings    🟢 Automation
⬆️ Upload Video
```

| Section | What you can do |
|---|---|
| 📊 Dashboard | full network snapshot (accounts, queue, published, followers, automation state) |
| 📱 Accounts | list with followers + automation status; tap to toggle automation ON/OFF; per-account metrics |
| 🔥 Trending | top-5 scored candidates with score bars; per item: 👁 Preview · 📊 Analytics · 🚫 Disable Source · 📥 Force Queue |
| 🎬 Content | library status counters + recent items |
| 📥 Queue | upcoming jobs with times & targets |
| 📅 Schedule | active batch-scheduler configuration |
| 📝 Captions | list captions/templates |
| 🖼 Covers | cover inventory & assignments |
| 📈 Analytics | 7-day performance summary |
| 📄 Reports | latest generated reports |
| ⚙️ Settings | rule-engine & publishing-mode summary |
| 🟢 Automation | Start / Pause / Resume / Stop / Run Now + last run, next run, queue size, active jobs, failed jobs |

## 5. Upload flow

1. Send any video file (≤ 500 MB) to the bot
2. Send a caption (or `/default`)
3. Pick destination accounts (multi-select, ☑ / ☐, **All**)
4. Choose **🚀 Publish Now**, **🕐 1 h** or **🗓 6 h**

The video runs through the same pipeline as automated content:
validation → duplicate detection → ffmpeg processing → cover → queue.

## 6. Automatic notifications

The worker pushes to all authorized admins (with notifications enabled):

- 🟢 publishing successful · 🔴 publishing failed
- ⚠️ rate-limit alerts (publishing paused)
- 🔥 high trend score detected (score ≥ configurable threshold)
- 📈 growth milestones · ⚠️ automation errors
- 📊 daily report (21:05 UTC)
