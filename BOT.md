# Janki Discord Bot Usage

## Regiter Bot to Server

Visit ([Discord Bot Registration](https://janki.yuriko-aya.cc/discord-bot))

## Commands

All commands use the `!janki` prefix.

| Command | Description | Permission |
|---------|-------------|------------|
| `!janki register <team-slug>` | Register this channel and link it to a team | Any user |
| `!janki deregister` | Remove this channel's registration | Registrant or mod/admin |
| `!janki record` | Parse and submit all new score messages to the API | Any user |
| `!janki addmember <name>` | Add a member to the registered team | Mod/admin only |
| `!janki standings` | Display the standings URL for this channel's team | Any user |
| `!janki status` | Show registration status for all channels in this server | Any user |
| `!janki help` | Show all available commands | Any user |

## How It Works

### Registration

Running `!janki register <team-slug>` in a channel:

1. Generates a one-time authorization link: `{JANKI_SERVER_URL}/teams/<team-slug>/authorization/<code>`
2. Visiting that link connects the channel to the team on the Janki server

Each channel can be registered to exactly one team. Multiple channels in the same server can each have their own team.

### Recording Scores

Running `!janki record` causes the bot to:

1. Scan the channel history since the last bot message (up to 1000 messages)
2. Parse each message that matches the score format (see below)
3. POST each parsed session to janki server
4. Update the last-bot-message timestamp after each successful submission

### Score Message Format

Each game result should be posted as a single multi-line message with one player per line:

```
PlayerA 35000
PlayerB 28000
PlayerC -5000
PlayerD -12000
```

Lines starting with `match`, `game`, or `riichi` (case-insensitive) are ignored (use them as headers). Chombo penalties can be noted inline:

```
Match 1
PlayerA 35000
PlayerB 28000 chombo 1
PlayerC -5000
PlayerD -12000
```

A message must contain at least 4 valid player lines to be submitted. Sessions are always submitted in chronological order.

### Return message

✅ Session 2026-04-18 12:19: Rin (18900), Amy (38300), Shien (23000), Rudy (39800) has been recorded successfully.
❌ Score recording failed (status 400): {"success":false,"errors":{"scores":[{},{},{},{"member_name":["Member 'Farras' does not exist in team Semarang Riichi Guild"]}]}}
✅ Session 2026-04-18 11:11: Amy (19900), Rudy (27700), Shien (35700), Sun (36700) has been recorded successfully.
❌ Score recording failed (status 409): {"error":"Session 2026-04-11 11:50 already exists. Use PUT to update.","existing_scores":4}
✅ All new scores have been recorded. You can see the updated leaderboard here: https://janki.yuriko-aya.cc/scores/semarang-riichi-guild/standings/