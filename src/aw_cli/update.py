import subprocess
import shutil
import sys
from . import utilities as ut


REPO_URL = "git+https://github.com/VenomDrake/anime-pad.git@branch-name"

# Configurazione minimalista dei comandi per ogni tool
TOOLS = {
    "uv": {
        "list": ["uv", "tool", "list"],
        "update": ["uv", "tool", "install", REPO_URL.replace("branch-name", "main"), "--force", "--reinstall"],
        "install_git": ["uv", "tool", "install", REPO_URL, "--force"]
    },
    "pipx": {
        "list": ["pipx", "list"],
        "update": ["pipx", "install", REPO_URL.replace("branch-name", "main"), "--force"],
        "install_git": ["pipx", "install", REPO_URL, "--force"]
    },
    "pip": {
        "list": [sys.executable, "-m", "pip", "show", "aw-cli"],
        "update": [sys.executable, "-m", "pip", "install", REPO_URL.replace("branch-name", "main"), "--upgrade", "--force-reinstall"],
        "install_git": [sys.executable, "-m", "pip", "install", REPO_URL, "--force-reinstall"]
    }
}


def check_installation_method() -> str | None:
    """
    Controlla il metodo di installazione dello script.

    Returns:
        str | None: il nome del tool rilevato, o None se non trovato.
    """
    # Un ambiente dedicato con pip va aggiornato con il proprio interprete,
    # anche se sul sistema esistono altre installazioni tramite uv o pipx.
    order = ["pip", "uv", "pipx"] if sys.prefix != sys.base_prefix else ["uv", "pipx", "pip"]
    for tool_name in order:
        commands = TOOLS[tool_name]
        if tool_name == "pip" or shutil.which(tool_name):
            result = subprocess.run(commands["list"], capture_output=True)
            if result.returncode == 0 and "aw-cli" in result.stdout.decode():
                return tool_name
    return None

def update(branch: str) -> None:
    """
    Aggiorna lo script in base al metodo di installazione.

    Args:
        branch (str): il branch da cui aggiornare lo script. Se la stringa è vuota, aggiorna all'ultima versione stabile.
    """
    tool = check_installation_method()
    if not tool:
        ut.console.print("Non è stato possibile trovare un metodo di installazione valido per aggiornare aw-cli", style="error")
        return

    command = TOOLS[tool]["install_git"] if branch else TOOLS[tool]["update"]
    command = [cmd.replace("branch-name", branch) for cmd in command] # sostituisco "branch-name" con il nome del branch
    subprocess.run(command, check=True)
