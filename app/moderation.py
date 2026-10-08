"""Basic chat moderation for the reader: decides what is allowed to be spoken."""
import os
import re
import time

from .hinglish import has_devanagari

KNOWN_BOTS = {"nightbot", "streamelements", "streamlabs", "moobot", "fossabot", "wizebot",
              "botrix", "kickbot", "sery_bot", "soundalerts", "serybot", "commanderroot",
              "deepbot", "coebot", "phantombot", "vivbot", "stay_hydrated_bot", "streamlabsbot",
              "ankhbot", "botisimo", "twitchbot"}
LINK_RX = re.compile(r"https?://|www\.|\b[\w-]+\.(?:com|in|net|org|tv|gg|io|me|co)\b", re.I)

BLOCKED_HELP = """# One word or phrase per line. Messages containing them are NOT read aloud.
# Lines starting with # are ignored. Add words in English letters and/or Devanagari.
"""


class Moderator:
    def __init__(self, settings, blocked_path):
        self.s = settings
        self.blocked_path = blocked_path
        self.blocked = []
        self.recent = {}        # (author, text) -> time
        self.last_spoken = {}   # author -> time
        self.reload_blocked()

    def reload_blocked(self):
        words = []
        try:
            if not os.path.exists(self.blocked_path):
                with open(self.blocked_path, "w", encoding="utf-8") as f:
                    f.write(BLOCKED_HELP)
            with open(self.blocked_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith("#"):
                        words.append(line)
        except Exception:
            pass
        self.blocked = words

    def _blocked_hit(self, text):
        low = text.lower()
        for w in self.blocked:
            if has_devanagari(w):
                if w in low:
                    return True
            elif re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low):
                return True
        return False

    def check(self, m, now=None):
        """Return (allowed, reason). Reason is shown in the feed when a message is skipped."""
        now = time.time() if now is None else now
        if m.platform == "test":
            return True, ""
        s, text = self.s, m.text.strip()
        paid = m.kind in ("super", "member")
        if not text and not paid:
            return False, "empty"
        name = m.author.lower()
        if s.get("ignore_bots") and (m.bot or name in KNOWN_BOTS):
            return False, "bot"
        if self._blocked_hit(text):
            return False, "blocked word"
        if paid:
            return (True, "") if s.get("read_super") else (False, "paid messages off")
        if s.get("mods_only") and not m.mod:
            return False, "mods only"
        if s.get("skip_cmds") and text.startswith("!"):
            return False, "command"
        if s.get("skip_links") and LINK_RX.search(text):
            return False, "link"
        if len(text) > 8 and len(set(text.replace(" ", ""))) <= 2:
            return False, "spam"
        key = (name, text.lower())
        if now - self.recent.get(key, -1e9) < s.get("dedupe_secs"):
            return False, "repeat"
        self.recent[key] = now
        if len(self.recent) > 500:
            self.recent = {k: t for k, t in self.recent.items() if now - t < 60}
        if not m.mod and now - self.last_spoken.get(name, -1e9) < s.get("user_cooldown"):
            return False, "too fast"
        self.last_spoken[name] = now
        return True, ""
