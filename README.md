# Slot Bot

A Discord bot for managing slot channels, with features for timed access, slot revocation, hold/unhold, and rule enforcement. Built using `discord.py` and slash commands for modern Discord compatibility.

## Features
- Create slot channels for users with timed durations
- Automatically revoke or hold slots based on rules
- Enforce ping and message limits
- Admin commands for managing slots
- Slash command interface for easy use
- Persistent storage in JSON

## Commands
- `/slot [user] [duration]` — Create a slot channel for a user
- `/revokeslot [channel] [reason]` — Revoke a slot channel
- `/hold [channel]` — Put a slot on hold (user cannot send messages)
- `/unhold [channel]` — Remove hold from a slot
- `/srules [channel]` — Send slot rules in a channel
- `/help` — Show help for all commands

## Setup
1. **Clone the repository**
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Create a `config.json` file with your bot token and replace the current category ID:
   ```json
   {
     "token": "YOUR_BOT_TOKEN",
     "category_id": 1300517967783661700
   }
   ```
4. Run the bot:
   ```sh
   python main.py
   ```

## Requirements
- Python 3.8+

## Notes
- All slot data is stored in `database.json`.
- Only users with administrator permissions can use management commands.
- The bot uses slash commands (type `/` in Discord to see them).