# Slack Application Setup Guide

This guide details step-by-step instructions to configure and run the Slack AI Assistant using Slack Bolt in Socket Mode.

---

## 1. Create a New Slack App

1. Navigate to the [Slack API App Console](https://api.slack.com/apps).
2. Click **Create New App** $\to$ choose **From scratch**.
3. Name your app (e.g. `ProposalAI-Assistant`) and select your target development Slack Workspace.
4. Click **Create App**.

---

## 2. Enable Socket Mode & App-Level Token

Socket Mode allows the backend to communicate bi-directionally over WebSockets without exposing a public HTTPS URL or configuring ngrok.

1. In the left navigation menu, click **Socket Mode**.
2. Toggle the switch to **Enable Socket Mode**.
3. A modal will prompt you to create an **App-Level Token**:
   - Token Name: `app-token`
   - Scope: `connections:write`
4. Click **Generate**.
5. Copy the generated token starting with `xapp-...` and save it to your `.env` as `SLACK_APP_TOKEN`.

---

## 3. Configure OAuth Scopes (Bot Token Scopes)

1. In the left navigation menu, select **OAuth & Permissions**.
2. Scroll down to **Scopes** $\to$ **Bot Token Scopes**.
3. Click **Add an OAuth Scope** and add each of the following required scopes:
   - `app_mentions:read` — Receive mentions of the bot in channels.
   - `chat:write` — Send threaded messages, Block Kit cards, and notifications.
   - `files:read` — Download transcripts and attached documents.
   - `files:write` — Upload generated proposal DOCX files directly into threads.
   - `channels:history` — Read message context in public channels the bot is added to.
   - `im:history` — Read messages and follow-ups in direct messages.
   - `assistant:write` — Set thread status and assistant thread context (`assistant.threads.setStatus`).
   - `commands` — Support slash commands if invoked.

---

## 4. Subscribe to Bot Events

1. In the left navigation menu, select **Event Subscriptions**.
2. Toggle **Enable Events** to **On**.
3. Expand **Subscribe to bot events** $\to$ click **Add Bot User Event** and add:
   - `app_mention` — Triggers when the bot is tagged (@ProposalAI).
   - `message.im` — Triggers on direct messages with the bot.
   - `file_shared` — Triggers when a file is uploaded to a channel/DM where the bot is present.
4. Click **Save Changes** at the bottom right.

---

## 5. Enable Interactivity & Shortcuts

1. In the left navigation menu, select **Interactivity & Shortcuts**.
2. Toggle **Interactivity** to **On**.
3. Because Socket Mode is enabled, no Request URL is needed — Slack automatically routes button clicks, modals, and block actions through the WebSocket connection.
4. Click **Save Changes**.

---

## 6. Install to Workspace & Retrieve Bot Tokens

1. Navigate to **Install App** in the left sidebar.
2. Click **Install to Workspace** and authorize the permissions.
3. Copy the **Bot User OAuth Token** (starts with `xoxb-...`) and set it in your `.env` as `SLACK_BOT_TOKEN`.
4. In **Basic Information**, scroll to **App Credentials** and copy the **Signing Secret** to `SLACK_SIGNING_SECRET`.

---

## 7. Environment Configuration Summary

Set the following variables in `.env`:
```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
```

---

## 8. Verification & Test Run

1. Invite the bot to your target channel: `/invite @ProposalAI-Assistant`.
2. Mention the bot: `@ProposalAI-Assistant hello`.
3. The bot will respond with an interactive greeting card.
4. Upload `client_transcript.txt` to the channel. The bot will detect the upload, spawn a threaded analysis, and guide you through the proposal generation lifecycle.

