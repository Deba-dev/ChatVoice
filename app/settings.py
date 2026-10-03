"""Settings stored as JSON in %APPDATA%/ChatVoice."""
import json
import os

from .secure import protect, unprotect

SECRET_KEYS = ("cloud_token", "g_client_secret")   # stored encrypted on Windows


def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    d = os.path.join(base, "ChatVoice")
    os.makedirs(d, exist_ok=True)
    return d


DEFAULTS = {
    "youtube": "", "twitch": "", "kick": "", "kick_room": "",
    "engine": "neural", "hi_voice": "hi-IN-SwaraNeural", "en_voice": "hi-IN-MadhurNeural",
    "per_viewer": False, "rate": 0, "volume": 100, "read_name": True, "muted": False,
    "skip_links": True, "skip_cmds": True, "ignore_bots": True, "mods_only": False,
    "read_super": True, "max_len": 150,
    "theme": "Neon Violet", "lite_mode": False,
    "inv_youtube": "", "inv_twitch": "", "inv_kick": "", "inv_role_youtube": "", "inv_role_twitch": "", "inv_role_kick": "",
    "cloud_url": "", "cloud_token": "", "guild_id": "", "guild_name": "", "webhook_url": "",
    "announce_auto": False, "announce_text": "I'm live! Come hang out", "post_super": False,
    "pay_gateway": "razorpay", "ov_port": 8765, "ov_seconds": 8, "ov_show_message": True, "ov_sound": False, "ov_chat_seconds": 20,
    "update_repo": "Deba-dev/ChatVoice", "auto_update_check": True, "update_last": 0, "tips_on": False, "tip_min": 20, "tip_cursor": None, "g_client_id": "", "g_client_secret": "",
    "mod_del_blocked": True, "mod_del_links": True, "mod_del_spam": False, "mod_dry_run": True, "mod_budget": 60,
    "mod_timeout_after": 3, "mod_timeout_secs": 300, "yt_actions_date": "", "yt_actions_count": 0,
    "role_verified": "", "role_regular": "", "role_supporter": "", "regular_msgs": 50, "dedupe_secs": 20, "user_cooldown": 4, "queue_max": 6,
}


class Settings:
    def __init__(self, path=None):
        self.path = path or os.path.join(data_dir(), "settings.json")
        self.data = dict(DEFAULTS)
        try:
            with open(self.path, encoding="utf-8") as f:
                loaded = json.load(f)
            for k in SECRET_KEYS:
                if k in loaded:
                    loaded[k] = unprotect(loaded[k])
            self.data.update(loaded)
        except Exception:
            pass

    def get(self, key):
        return self.data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self.data[key] = value
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                out = dict(self.data)
                for k in SECRET_KEYS:
                    out[k] = protect(out.get(k, ""))
                json.dump(out, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
