import toml
import subprocess
import os
import shutil
from pathlib import Path
from rich.console import Console
from rich.theme import Theme
from collections import defaultdict

config_data = defaultdict(dict)

DEFAULT_STYLE = {
    "error": "bold red",
    "prompt": "bold light_sky_blue3",
    "warning": "bold yellow",
    "success": "bold green",
    "info": "bright_yellow",
    "highlight": "cyan",
    "general": "white"
}

console = Console(theme=Theme(DEFAULT_STYLE), highlight=False)

# controllo il tipo del dispositivo
def get_os() -> str:
    if os.environ.get("ISPAD", "").lower() in {"1", "true", "yes"} or Path("/proc/ish").exists():
        return "iSH"
    result = subprocess.run(["uname", "-a"], capture_output=True, text=True, check=False)
    out = result.stdout.strip().split()
    if not out:
        return "Unknown"
    os_name = out[0]
    if os_name == "Linux":
        if "Android" == out[-1]:
            os_name = "Android"
        elif len(out) > 2 and "WSL" in out[2]:
            os_name = "WSL"
    return os_name

os_name = get_os()

DATA_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "anime-pad"


def config_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / "config.toml"
    old = Path(__file__).parent / "config.toml"
    if not target.exists() and old.exists():
        shutil.copy2(old, target)
    if target.exists():
        target.chmod(0o600)
    return target


def history_dir() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    old = Path(__file__).parent / "history.json"
    target = DATA_DIR / "history.json"
    if not target.exists() and old.exists():
        shutil.copy2(old, target)
    return DATA_DIR

def sanitize_filename(filename: str) -> str:
    """
    Sanitizza il nome del file rimuovendo i caratteri non validi.

    Args:
        filename (str): il nome del file da sanitizzare.

    Returns:
        str: il nome del file sanitizzato.
    """
    forbidden_char = '"*/:<>?\\|'
    replace_char = '”⁎∕꞉‹›︖＼⏐'
    for a, b in zip(forbidden_char, replace_char):
        if os_name != "Android" and a != "/":
            continue
        filename = filename.replace(a, b)
    filename = "".join(c for c in filename if ord(c) >= 32 and ord(c) != 127).strip()
    return filename if filename not in {"", ".", ".."} else "Anime"

def get_config() -> None:
    """
    Prende le impostazioni scelte dall'utente
    dal file di configurazione.

    Returns:
        None
    """
    global config_data

    with open(config_path(), 'r', encoding="utf-8") as f:
        config_data = toml.load(f)

    # Merge with default styles if missing
    if "style" not in config_data:
        config_data["style"] = DEFAULT_STYLE.copy()
    else:
        for key, value in DEFAULT_STYLE.items():
            if key not in config_data["style"]:
                config_data["style"][key] = value

    global console
    console = Console(theme=Theme(config_data["style"]), highlight=False)

    if os_name == "WSL":
        player = config_data.get("player", {})
        if player.get("path"):
            player["path"] = subprocess.run(["wslpath", player["path"]], capture_output=True, text=True, check=True).stdout.strip()

    config_data.setdefault("general", {}).setdefault("specials", False)
    config_data.setdefault("provider", {}).setdefault("source", "animeworld")
    config_data.setdefault("player", {}).setdefault("type", "mpv")
