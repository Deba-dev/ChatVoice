CHATVOICE YOUTUBE MODERATOR - RAILWAY OR RENDER SETUP

This service is an early hosted-bot MVP. It uses one ChatVoice Google account to read and moderate
live chats where that account has been manually added as a YouTube moderator. Stream registration
is manual for now; the ChatVoice desktop app is not yet connected to this service.

SECURITY FIRST
- The OAuth JSON attached to the chat contains a client secret. Treat it as exposed and reset the
  secret in Google Cloud Console before deployment. Do not commit or upload the replacement JSON.
- Set all secrets in your hosting provider's environment variables. Never put OAuth secrets, refresh tokens, or BOT_ADMIN_KEY
  in this repository, a screenshot, or a public chat.
- This service needs a persistent volume mounted at /data. It stores the bot refresh token
  and registered stream configuration there.
- TEST MODE is on for every new stream. Do not disable it until dry-run behavior has been checked.

GOOGLE CLOUD CONSOLE (shared setup for either host)
1. You have already enabled YouTube Data API v3 and added the bot account as a test user.
2. In APIs & Services > Credentials, open the existing "youtube bot" Web application OAuth client.
   Reset the exposed client secret. Keep the new secret private.
3. Create/deploy the service first to get its public HTTPS domain.
4. Add this Authorized redirect URI to the OAuth client, replacing the domain:
       https://YOUR-HOST-DOMAIN/oauth/callback
   It must match PUBLIC_URL plus /oauth/callback exactly.
5. Leave the bot Google account in the OAuth test-user list while testing. Google can expire
   refresh tokens issued while the app is in Testing after about seven days. Do not rely on it
   long-term without reviewing Google's current verification and publishing requirements.

RAILWAY DEPLOYMENT
1. Push the repository to GitHub (with no credential JSON or secrets in it).
2. Railway > New Project > Deploy from GitHub Repo > choose ChatVoice.
3. In the service Settings, set Root Directory to /youtube-bot.
   Railway will use package.json and run npm start. No external npm packages are required.
4. Add a Railway Volume to the service and mount it at /data.
5. Add these service Variables:
       GOOGLE_CLIENT_ID       OAuth client ID from Google Cloud
       GOOGLE_CLIENT_SECRET   freshly reset OAuth client secret
       BOT_ADMIN_KEY          a random private value of at least 32 characters
       PUBLIC_URL             https://YOUR-RAILWAY-DOMAIN
       DATA_DIR               /data
   Use Railway's generated domain (Settings > Networking > Generate Domain). Include https://
   and no trailing slash in PUBLIC_URL. Railway provides PORT.
6. Deploy/redeploy after setting variables and the volume. Confirm https://YOUR-RAILWAY-DOMAIN/health
   returns {"ok":true,"authorized":false,"streams":0}.
7. Add PUBLIC_URL + /oauth/callback as the OAuth client's authorized redirect URI in Google Cloud,
   save, and redeploy if needed.
8. Open https://YOUR-RAILWAY-DOMAIN/admin, enter BOT_ADMIN_KEY, click "Authorize bot Google account",
   and sign in as the dedicated ChatVoice bot account. Consent to YouTube access. The callback
   stores the refresh token on the Railway volume; it is not shown in the page or logs.
9. Open /health again. "authorized" should be true.

RENDER DEPLOYMENT (always-on setup; paid)
Render's Free web services spin down when idle and have ephemeral filesystems. This bot must poll
YouTube continuously and keep OAuth/config data on disk, so the Free instance is not suitable.
Render persistent disks are available on paid services. Check the current service and disk prices
before deploying; the repository's render.yaml uses the Starter plan and a 1 GB persistent disk.

1. Push the repository to GitHub without any credential JSON or secrets.
2. In Render, choose New > Blueprint, connect the ChatVoice repository, and deploy the Blueprint.
   Render reads render.yaml from the repository root and creates the bot web service with its disk.
3. Set the prompted GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (the newly reset secret), and
   BOT_ADMIN_KEY values in Render. The Blueprint declares these as unsynced secrets.
4. Wait for the first deploy to finish. In the service's Settings, copy its onrender.com URL.
5. In the Blueprint prompt, PUBLIC_URL can temporarily be set to https://example.invalid so the
   first deploy can start. Then in the service's Environment settings, replace it with the actual
   onrender.com URL, including https:// and with no trailing slash. DATA_DIR is already /data.
6. In Google Cloud Console, add exactly:
       https://YOUR-SERVICE.onrender.com/oauth/callback
   as an Authorized redirect URI for the Web application OAuth client. Save it.
7. Redeploy the service, then check https://YOUR-SERVICE.onrender.com/health. It should report
   {"ok":true,"authorized":false,"streams":0}.
8. Open https://YOUR-SERVICE.onrender.com/admin, enter BOT_ADMIN_KEY, click "Authorize bot Google
   account", and sign in as the dedicated ChatVoice bot Google account.
9. Check /health again. "authorized" should be true. Continue with REGISTER A TEST STREAM below.

If deploying without the Blueprint, create a paid Node web service with root directory
youtube-bot, build command "npm install", start command "npm start", health check path /health,
and a persistent disk mounted at /data. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, BOT_ADMIN_KEY,
PUBLIC_URL, and DATA_DIR=/data in the service's Environment settings.

REGISTER A TEST STREAM
1. In YouTube Studio for a channel you control, add the ChatVoice bot channel as a moderator.
2. Start a live stream. Get:
   - the streamer's YouTube channel ID (starts with UC)
   - the live video ID (11 characters, from the live URL after v=)
3. Open /admin and submit a JSON configuration like:
       {
         "channelId": "UC_REPLACE_WITH_REAL_CHANNEL_ID",
         "videoId": "REPLACE",
         "blockedWords": ["example blocked word"],
         "deleteLinks": true,
         "deleteSpam": false,
         "dryRun": true,
         "dailyLimit": 60
       }
   Replace both IDs with real values. A successful response means the configuration was saved.
4. Watch the service logs (Railway or Render). In dry-run mode, it only logs the rule category that would have been acted
   on; it does not delete messages. Add no more than a test channel while checking.
5. Only after verifying expected detections, submit that stream again with "dryRun": false.
   The limit is 60 deletions per stream per Pacific Time quota day by default (maximum configurable: 150).
   Deletions cost YouTube API quota. The bot never times users out in this MVP.

CURRENT LIMITATIONS
- Streams must be registered manually and be live when registered. The app integration and automatic
  detection of a streamer's current live video have not been implemented.
- A single bot OAuth account and YouTube API project are shared. Their API quota is shared too.
- The service caps itself at 8,000 API units per Pacific Time day to leave a buffer below Google's
  default 10,000-unit daily bucket. Live-chat polling can use a substantial share of this quota on a
  long stream; once the safety cap is reached, monitoring pauses until the next quota day. Each
  liveChatMessages.list request costs 1 unit and each deletion costs 50. Check Google Cloud Console >
  Quotas before using it for multiple channels.
- Initial rule support is blocked words, links, and duplicate-message spam. There are no timeouts.
- YouTube API permissions, moderator role, quota, and OAuth policy still apply. A failed API call is
  reported to the hosting service logs; do not assume a message was deleted unless logs show "deleted".
- To remove a configured channel, send DELETE /api/streams/CHANNEL_ID with Authorization:
  Bearer BOT_ADMIN_KEY. All /api endpoints require that private bearer key.

LOCAL TESTS
  npm test
