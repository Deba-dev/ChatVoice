ChatVoice  -  full project (v0.3)
Reads YouTube, Twitch and Kick chat aloud in Hindi / Hinglish / English, with moderation, Discord roles,
payment alerts from the streamer's own Razorpay, and YouTube message deleting.

WHAT IS INSIDE
  main.py, app\           the Windows app (Python + PySide6)
  cloud\                  the free Cloudflare server (Discord roles, payment webhook)
  assets\                 icon and the Poppins font
  tests\                  automatic checks (node test.mjs for the cloud, python tests\test_app.py for the app)
  CLOUD-SETUP.txt         one-time cloud + Discord setup (you, once)
  PAYMENTS-SETUP.txt      Razorpay payment page and webhook
  YT-MODERATION-SETUP.txt Google sign-in for deleting YouTube messages
  GITHUB-BUILD-GUIDE.txt  turn the project into ChatVoice-Setup.exe, free

PAGES IN THE APP
  Connect     paste your YouTube link, Twitch and Kick channel, press Connect (no logins needed to read chat)
  Live chat   combined feed; grey lines were skipped by moderation
  Voice       voices, speed, volume, "different voice per viewer", Hinglish word list
  Moderation  what gets read aloud: link / command / bot / repeat filters, blocked words
  Discord     roles from invite links (recommended), chat-activity roles, announcements
  Payments    Razorpay payment alerts read aloud
  YouTube mod sign in with Google to delete messages and time out repeat offenders
  Sidebar     Theme (4 colour themes) and Lite mode (turns off glow/fade animations for weak PCs or gaming)

RUN IT (easiest)
1. Install Python 3.12 from python.org.
2. Double-click run.bat   (installs the libraries the first time, then opens the app)

GET A REAL ChatVoice-Setup.exe  (free, no command window when it runs)
Your friends only run the finished Setup.exe. They never need Python or any command line.
Option 1 - build it in the cloud, nothing to install on your PC:
  1. Make a free GitHub account, create a repository, upload everything from this folder.
  2. Open the "Actions" tab > "Build ChatVoice" > "Run workflow".
  3. When it finishes (about 5-10 minutes), download "ChatVoice-Setup" from the run page.
  (Public repositories get unlimited free build minutes; private ones get a monthly allowance.)
Option 2 - build it on your PC: install Python 3.12 and the free Inno Setup 6 (jrsoftware.org),
  then double-click build.bat. You get installer\ChatVoice-Setup.exe.

ABOUT WINDOWS WARNINGS AND GAMES
- A new unsigned app shows "Windows protected your PC": click "More info" > "Run anyway". Removing this
  needs a paid code-signing certificate; free signing exists only for open-source projects.
- Some antivirus programs wrongly flag apps made this way. The build keeps the app as a folder (not one
  big file) which reduces this. You can report a false alarm to Microsoft Defender.
- While running, ChatVoice has no console window, runs at below-normal CPU priority so games and OBS
  always come first, and it does not hook into games.

USING IT
- Connect: paste your YouTube live link, Twitch channel, Kick channel. Press Connect.
- Kick: if it says "Kick blocked the lookup", open  https://kick.com/api/v2/channels/YOURNAME  in a browser,
  find  "chatroom":{"id":NUMBER  and paste that number in the box under the Kick channel.
- Voice: voices, speed, volume. Emoji, :emoji_codes: and Twitch emote words are never read aloud.
- Moderation: link / command / bot / repeat filters and your own blocked-words list (what gets READ).
- Discord: roles for viewers, a link page, announcements. Needs the one-time cloud setup: see CLOUD-SETUP.txt.

USING IT WITH OBS
ChatVoice is a normal window that plays sound on your PC. To put the voice on your stream:
1. Start ChatVoice BEFORE you go live and keep it running (minimised is fine).
2. In OBS: Sources > + > "Application Audio Capture", pick the ChatVoice window.
   (Needs Windows 10 version 2004+ and OBS 28 or newer. If it is missing, add "Audio Output Capture" instead,
   or just rely on "Desktop Audio".) If you started it with run.bat, the app may show as python.exe.
3. In the OBS audio mixer you can now raise or lower the voice separately from your game and mic.
4. USE HEADPHONES. With speakers, your microphone picks the voice up again and viewers hear an echo.
5. To show the chat on screen: Sources > + > "Window Capture" > ChatVoice, then open its "Live chat" page.

FILES THE APP KEEPS  (%APPDATA%\ChatVoice)
settings.json, hinglish_words.txt (add short forms: short=how to say it), blocked_words.txt

NOTES
- Neural voices need internet. If they fail, the app falls back to Windows voices.
- YouTube uses the no-login method, Kick uses Kick's unofficial chat connection; either can break if the
  platform changes. Twitch is read anonymously.
- The app only READS chat. Deleting or banning on the platforms needs a login and is a later phase.
