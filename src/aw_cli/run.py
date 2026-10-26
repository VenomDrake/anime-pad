import re
import shutil
import subprocess
from time import sleep
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from typing import Callable
from rich.prompt import Prompt, FloatPrompt
from rich.text import Text
from .providers.provider import ProviderError
from . import (
    anilist,
    download,
    providers,
    utilities as ut,
)
from .fzf import Fzf
from .history import History
from .anime import Anime, AnimeStatus
from .arg_parser import (
    args,
    info,
    downl,
    latest,
    offline,
    private,
    hist,
)

def search_anime(provider: providers.Provider) -> list[Anime]:
    """
    Dato in input un nome di un anime inserito dall'utente, restituisce una lista con gli URL degli anime
    relativi alla ricerca.

    Returns:
        list[Anime]: la lista con gli URL degli anime trovati
    """

    def check_search(s: str):
        if s == "exit":
            exit()
        result = provider.search(s)
        if result:
            return result

    ut.console.clear()
    while True:
        query = Prompt.ask("Cerca un anime (exit per uscire)", console=ut.console).strip()
        if not query:
            continue
        try:
            if res := check_search(query):
                return res
        except ProviderError as error:
            ut.console.print(str(error), style="error", markup=False)
            continue
        ut.console.print("La ricerca non ha prodotto risultati", style="error")
        sleep(1)
        ut.console.clear()

def select_episodes(anime: Anime) -> list[Anime.Episode]:
    """
    Fa scegliere all'utente gli episodi dell'anime da guardare.

    Se l'anime ha solo un episodio, questo verrà riprodotto automaticamente.
    In caso contrario, l'utente può scegliere un episodio.

    Args:
        anime (Anime): l'anime di cui scegliere gli episodi.

    Returns:
        str: il numero dell'episodio da riprodurre.
    """


    ut.console.clear()
    ut.console.print(Text(anime.name))
    #se contiene solo 1 ep sarà riprodotto automaticamente
    if len(anime.episodes()) == 1:
        return anime._episodes

    if downl:
        res = Fzf().run(
            list(reversed(anime.episodes())),
            prompt="Scegli episodi: ",
            multi=True,
            filter=True,
        ).split("\n")
    else:
        res = Fzf().run(list(reversed(anime.episodes())), "Scegli un episodio: ").split("\n")


    return [anime.episode(num) for num in res]

def open_syncplay(ep_url: str, ep_name: str, progress: int) -> tuple[bool, int]:
    """
    Avvia Syncplay.

    Args:
        ep_url (str): l'URL dell'episodio da riprodurre.
        ep_name (str): il nome dell'episodio.
        progress (int): il progresso dell'episodio.

    Returns:
        bool: True se l'episodio è stato riprodotto completamente, altrimenti False.
        int: il progresso dell'episodio.
    """

    if "syncplay" not in ut.config_data:
        ut.console.print("Aggiornare il path di syncplay nella configurazione tramite: aw-cli -a", style="error")
        exit()


    player_args = [f"--force-media-title={ep_name}", f"--start={progress}", "--fullscreen", "--keep-open"]
    if ut.config_data.get("player", {}).get("type") == "vlc":
        player_args = ["--meta-title", ep_name, f"--start-time={progress}", "--fullscreen"]

    try:
        command = [ut.config_data["syncplay"]["path"], "-d", "--language", "it", ep_url, "--", *player_args]
        if ut.os_name == "WSL":
            command = ["/mnt/c/Windows/System32/cmd.exe", "/C", *command]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode:
            raise OSError("Syncplay non è riuscito ad avviare la riproduzione")
        out = result.stdout
    except UnicodeDecodeError:
        out = ""

    duration_match = re.findall(r'duration(?:-change)?"?: (\d+)\.?[\d]*', out)
    progress_match = re.findall(r'pos(?:ition"?)?:? (\d+).?\d+', out)
    if not duration_match:
        ut.console.print("Errore, impossibile leggere l'output di Syncplay!", style="error")
        return False, 0

    duration = max(map(int, duration_match))
    progress_match = list(filter(lambda x: x>0, map(int, progress_match)))
    progress = progress_match[-1] if progress_match else 0

    return progress*100// duration >= complete_limit if duration > 0 else False, progress

def open_mpv(ep_url: str, ep_name: str, progress: int) -> tuple[bool, int]:
    """
    Apre MPV per riprodurre il video.

    Args:
        ep_url (str): il link del video o il percorso del file.
        ep_name (str): il nome del video.
        progress (int): il progresso dell'episodio.

    Returns:
        bool: True se l'episodio è stato riprodotto completamente, altrimenti False.
        int: il progresso dell'episodio.
    """


    if (ut.os_name == "Android"):
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", ep_url, "-n", "is.xyz.mpv/.MPVActivity"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False, progress

    command = [ut.config_data["player"]["path"], ep_url, f"--force-media-title={ep_name}", f"--start={progress}", "--fullscreen", "--keep-open"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        raise OSError("MPV non è riuscito ad aprire il video")
    out = result.stdout

    matches = re.findall(r'(\d+):(\d+):(\d+) / [\d:]+ \((\d+)%\)', out)
    if not matches:
        return False, progress
    res = matches[-1]
    progress = (int(res[0]) * 3600) + (int(res[1]) * 60) + int(res[2])

    return int(res[3]) >= complete_limit, progress

def open_vlc(ep_url: str, ep_name: str, progress: int) -> tuple[bool, int]:
    """
    Apre VLC per riprodurre il video.

    Args:
        ep_url (str): il link del video o il percorso del file.
        ep_name (str): il nome del video.
        progress (int): il progresso dell'episodio.

    Returns:
        bool: True se l'episodio è stato riprodotto completamente, altrimenti False.
        int: il progresso dell'episodio.
    """

    if ut.os_name == "Android":
        subprocess.run(["am", "start", "--user", "0", "-a", "android.intent.action.VIEW", "-d", ep_url, "-n", "org.videolan.vlc/.StartActivity", "-e", "title", ep_name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return False, progress

    subprocess.run([ut.config_data["player"]["path"], ep_url, "--meta-title", ep_name, f"--start-time={progress}", "--fullscreen"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # se il file di configurazione di VLC esiste, prendo la posizione dell'ultimo episodio riprodotto
    progress = 0
    vlc_config_path = Path.home() / ".config/vlc/vlc-qt-interface.conf" # Linux
    if vlc_config_path.exists():
        with open(vlc_config_path, "r") as file:
            config = [line.strip() for line in file.readlines()]
        try:
            index = config.index("[RecentsMRL]")
            urls = config[index + 1].split("=", 1)[1].split(", ")
            positions = config[index + 2].split("=", 1)[1].split(", ")
            progress = int(positions[urls.index(ep_url)]) // 1000 if ep_url in urls else 0
        except (ValueError, IndexError):
            progress = 0

    return False, progress


def open_link(ep_url: str, ep_name: str, progress: int) -> tuple[bool, int]:
    """iSH non può eseguire i player iOS come programmi Linux."""
    ut.console.print(Text(ep_name))
    ut.console.print("Apri il link in un player esterno o nel browser; per i file locali usa l'app File:")
    ut.console.print(ep_url, markup=False, soft_wrap=True)
    completed = Prompt.ask("Quando torni: episodio completato?", choices=["s", "n"], default="n", console=ut.console) == "s"
    return completed, 0 if completed else progress

def update_anilist(anime: Anime, episode: Anime.Episode, anilist_rating: float|None, drop: bool = False) -> None:
    """
    Procede ad aggiornare l'anime su AniList.
    Se l'episodio riprodotto è l'ultimo e
    l'utente ha scelto di votare gli anime,
    verrà chiesto il voto da dare.

    Args:
        anime (Anime): l'anime da aggiornare.
        episode (Anime.Episode): l'episodio da aggiornare.
        anilist_rating (float|None): il voto che l'utente ha assegnato all'anime.
        drop (bool, optional): True se l'utente decide di droppare l'anime, altrimenti False.
    """

    if anime.anilist_id == 0:
        ut.console.print("Impossibile aggiornare AniList: id anime non trovato!", style="error")
        return

    rating = 0
    favorite = False
    status_list = 'CURRENT' if not drop else 'DROPPED'
    #se ho finito di vedere l'anime o lo stato è dropped
    if (episode.numeric() == int(anime.last_ep) and anime.status == AnimeStatus.FINISHED) or status_list == 'DROPPED':
        if status_list == 'CURRENT':
            status_list = 'COMPLETED'

        #chiedo di votare
        #chiedo di votare
        if ut.config_data["anilist"]["rating"]:
            prompt_text = "Inserisci un voto per l'anime" + (f" (voto corrente: {anilist_rating})" if anilist_rating else "")
            while True:
                try:
                    rating = FloatPrompt.ask(prompt_text, console=ut.console)
                    if rating < 0: raise ValueError
                    break
                except ValueError:
                    ut.console.print("Seleziona una risposta valida!", style="error")

        #chiedo di mettere tra i preferiti
        if ut.config_data["anilist"]["favorite"] and status_list == 'COMPLETED':
            ut.console.clear()
            ut.console.print(f"Riproduco {anime.name} Ep. {anime.last_ep}", style="info")
            favorite = Fzf().run(["sì","no"], "Mettere l'anime tra i preferiti? ") == "sì"

    Thread(target=anilist.update_anilist, args=(ut.config_data["anilist"]["token"],anime.anilist_id, episode.numeric(), status_list, rating, favorite)).start()

def watch_episode(anime: Anime, episode: Anime.Episode, provider: providers.Provider) -> None:
    """
    Riproduce l'episodio dell'anime e gestisce gli aggiornamenti di stato.
    Se un episodio è già stato scaricato, viene riprodotto dal file scaricato.
    Altrimenti, viene riprodotto in streaming.

    Args:
        anime (Anime): l'anime di cui riprodurre l'episodio.
        episode (Anime.Episode): l'episodio da riprodurre.
        provider (Provider): il provider da cui prendere il link dell'episodio.
    """
    #se il video è già stato scaricato lo riproduco invece di farlo in streaming
    path = download.episode_path(anime, episode)

    if Path(path).exists():
        ep_url = str(path) if ut.os_name in {"Android", "iSH"} else path.resolve().as_uri()
    else:
        try:
            ep_url = provider.episode_link(anime, episode)
        except ProviderError:
            if open_player is not open_link or not episode.ref.startswith(("https://", "http://")):
                raise
            ut.console.print("Link diretto non disponibile: apri la pagina dell'episodio nel browser.", style="warning")
            ep_url = episode.ref

    ut.console.clear()
    ut.console.print(f"Riproduco {episode}...", style="info", markup=False)
    completed, progress = open_player(ep_url, str(episode), episode.progress)

    if not private:
        episode.set_progress(progress)
        if completed:
            episode.mark_completed()
        anime.curr_ep = episode.num
        history.update(anime, episode)
        # Il salvataggio locale deve precedere qualsiasi richiesta opzionale.
        if completed and not offline and "anilist" in ut.config_data and anime.anilist_id:
            try:
                rating = anilist.get_anime_private_rating(ut.config_data["anilist"]["token"], ut.config_data["anilist"]["user_id"], anime.anilist_id)
                update_anilist(anime, episode, rating)
            except Exception:
                ut.console.print("AniList non disponibile: progresso salvato nella cronologia locale.", style="warning")

def setup_config() -> None:
    """
    Crea un file di configurazione chiamato "config.toml"
    nella stessa directory dello script.
    Le informazioni riportate saranno scelte dall'utente.
    Sarà possibile scegliere il Player predefinito,
    se collegare il proprio profilo AniList e
    se inserire il path di syncplay.
    """
    ut.config_data.clear()

    #player predefinito
    ut.console.clear()
    ut.console.print("AW-CLI - CONFIGURAZIONE", style="info")

    ut.config_data["player"] = {}
    ut.config_data["general"] = {}
    ut.config_data["provider"] = {}
    ut.config_data["player"]["type"] = "link" if ut.os_name == "iSH" else Fzf().run(["vlc","mpv", "link"], "Scegli il player predefinito: ")
    if ut.os_name not in {"Android", "iSH"} and ut.config_data["player"]["type"] != "link":
        path = shutil.which(ut.config_data['player']['type'])
        if path is None:
            ut.console.print(f"Player {ut.config_data['player']['type']} non trovato!", style="error")
            ut.config_data["player"]["path"] = Prompt.ask(f"Inserisci il path di {ut.config_data['player']['type']} manualmente se è installato", console=ut.console)
        else:
            ut.config_data["player"]["path"] = path
        ut.console.clear()
        ut.console.print("AW-CLI - CONFIGURAZIONE", style="info")

    ut.config_data["general"]["specials"] = Fzf().run(["sì","no"], "Mostrare gli episodi speciali? ") == "sì"


    #provider preferito
    ut.config_data["provider"]["source"] = Fzf().run(["animeworld", "animeunity"], "Scegli il provider: ")

    #anilist
    if Fzf().run(["sì","no"], "Aggiornare automaticamente la watchlist con AniList? ") == "sì":
        link = "https://anilist.co/api/v2/oauth/authorize?client_id=11388&response_type=token"
        opener = "open" if ut.os_name == "Darwin" else "xdg-open"
        if ut.os_name != "iSH" and shutil.which(opener):
            subprocess.run([opener, link], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        #inserimento token
        ut.console.clear()
        ut.config_data["anilist"] = {}
        ut.config_data["anilist"]["token"] = Prompt.ask(f"Inserire il token di AniList ({link})", console=ut.console, password=True)

        #prendo l'id dell'utente tramite query
        with ThreadPoolExecutor() as executor:
            ut.config_data["anilist"]["rating"], ut.config_data["anilist"]["favorite"], ut.config_data["anilist"]["drop"] = False, False, False
            future = executor.submit(anilist.get_user_id, ut.config_data["anilist"]["token"])
            ut.console.clear()
            ut.console.print("AW-CLI - CONFIGURAZIONE", style="info")
            if Fzf().run(["sì","no"], "Votare l'anime una volta completato? ") == "sì":
                ut.config_data["anilist"]["rating"] = True

            if Fzf().run(["sì","no"], "Chiedere se mettere l'anime tra i preferiti una volta completato? ") == "sì":
                ut.config_data["anilist"]["favorite"] = True

            if Fzf().run(["sì","no"], "Chiedere se droppare l'anime una volta rimosso dalla cronologia? ") == "sì":
                ut.config_data["anilist"]["drop"] = True

            ut.config_data["anilist"]["user_id"]  = future.result()

    #syncplay
    if ut.os_name not in {"Android", "iSH"}:
        syncplay_path = shutil.which("syncplay")
        if syncplay_path is None:
            ut.console.print("Syncplay non trovato!", style="error")
            syncplay = Prompt.ask("Inserisci il path di Syncplay (premere INVIO se non lo si desidera utilizzare)", console=ut.console).replace("Program Files (x86)", "Progra~2")
            if syncplay != "":
                ut.config_data["syncplay"] = {"path": syncplay}
        else:
            ut.config_data["syncplay"] = {"path": syncplay_path}

    # style
    ut.config_data["style"] = ut.DEFAULT_STYLE

    #creo il file
    config = ut.config_path()
    temporary = config.with_suffix(".toml.tmp")
    temporary.touch(mode=0o600, exist_ok=True)
    temporary.chmod(0o600)
    with open(temporary, 'w', encoding="utf-8") as f:
        ut.toml.dump(ut.config_data, f)
    temporary.replace(config)

def list_anime_names(animelist: list[Anime]) -> list[str]:
    """
    Genera una lista di stringhe formattate con i
    nomi degli anime presenti nella lista desiderata.

    Args:
        animelist (list[Anime]): Una lista Anime.

    Return:
        list[str]: lista di stringhe formattate.
    """

    names = []
    for i, a in reversed(list(enumerate(animelist))):
        colour = 2 #2 verde, 1 rosso
        if hist and a.curr_ep == a.last_ep and (not a.has_episode(a.curr_ep) or a.episode(a.curr_ep).is_completed()):
            colour = 1

        name = f"\033[0;3{colour}m{i + 1}  \033[0;37m"

        if hist:
            name += f"{a.name} [Ep {a.curr_ep}/{a.info.get('Episodi', '??')}]"
        elif latest:
            name += f"{a.name} [Ep {a.curr_ep}]"
        else:
            name += f"{a.name}"
        names.append(name)

    return names

def remove_from_history(anime: Anime) -> None:
    """
    Rimuove l'anime selezionato dalla cronologia
    e stampa un menu di scelta per l'utente.

    Args:
        number (int): il numero dell'anime in lista da rimuovere.

    Returns:
        None.
    """

    if Fzf().run(["sì","no"], f"Si è sicuri di voler rimuovere {anime.name} dalla cronologia? ") == "no":
        return

    if "anilist" in ut.config_data and ut.config_data["anilist"]["drop"] and Fzf().run(["sì","no"], f"Droppare {anime.name} su AniList? ") == "sì":
        if anime.anilist_id == 0:
            ut.console.print("Impossibile droppare su AniList: id anime non trovato!", style="error")
            sleep(1)
        else:
            rating = anilist.get_anime_private_rating(ut.config_data["anilist"]["token"], ut.config_data["anilist"]["user_id"], anime.anilist_id)
            update_anilist(anime, anime.episode(anime.curr_ep), rating, drop=True)

    history.remove(anime)

    ut.console.clear()
    if Fzf().run(["esci","continua"]) == "esci":
        exit()

def create_ep_menu(anime: Anime, episode: Anime.Episode) -> dict[str, Callable[[], Anime.Episode|str]]:
    """
    Genera il menu di riproduzione di un episodio,
    con le azioni disponibili in base allo stato dell'anime e dell'episodio.

    Args:
        anime (Anime): l'anime di cui è stato riprodotto l'episodio.
        episode (Anime.Episode): l'episodio riprodotto.

    Returns:
        dict[str, Callable[[], Anime.Episode|str]]: un dizionario che
            associa a ogni azione disponibile una funzione che la esegue.
    """
    actions = {
        "esci": exit,
        "indietro": lambda: "break",
        "seleziona": lambda: select_episodes(anime)[0],
        "antecedente": episode.prev,
        "riguarda": lambda: episode,
        "prossimo": episode.next
    }

    conditions = {
        "seleziona": len(anime.episodes()) > 1 or anime.last_ep != '1',
        "antecedente": episode.has_prev(),
        "prossimo": episode.has_next()
    }

    return {k: v for k, v in actions.items() if conditions.get(k, True)}


def _main():
    global open_player
    global history

    #se il file di configurazione non esiste viene chiesto all'utente di fare il setup
    if args.start_config or not ut.config_path().exists():
        setup_config()

    ut.get_config()
    history = History.read(str(ut.history_dir()))

    if offline:
        from .providers.local import LocalProvider
        provider = LocalProvider(download.path(), history.get())
    else:
        match ut.config_data["provider"]["source"]:
            case "animeunity":
                from .providers.animeunity import Animeunity
                provider = Animeunity()
            case _:
                from .providers.animeworld import Animeworld
                provider = Animeworld()

    open_player = {"vlc": open_vlc, "mpv": open_mpv, "link": open_link}.get(ut.config_data["player"]["type"], open_mpv)
    if ut.os_name == "iSH":
        open_player = open_link
    if ut.os_name not in {"Android", "iSH"} and args.syncpl:
        open_player = open_syncplay

    fzf = Fzf()
    reload = True
    animelist = []
    while True:
        if reload:
            if offline:
                animelist = provider.search("") # Uses offline provider
            elif hist:
                animelist = history.get()
            elif latest:
                animelist = provider.latest(args.latest)
            else:
                animelist = search_anime(provider)

            if not animelist:
                message = "Cronologia vuota!" if hist else "Nessun anime trovato!"
                ut.console.print(message, style="error")
                exit()

        if hist and history.has_ongoing() and args.history != 'r' and not offline:
            def refresh_history():
                history.reload(provider.latest())
            try:
                refresh_history()
            except ProviderError as error:
                ut.console.print(str(error), style="warning", markup=False)

        ut.console.clear()
        prompt = "Scegli un anime: " if args.history != 'r' else "Rimuovi un anime: "
        selected_anime = fzf.run(list_anime_names(animelist), prompt)
        selected_anime = re.sub(r"\x1b\[[0-9;]*m", "", selected_anime)
        selected = int(selected_anime.split("  ")[0]) - 1
        anime = animelist[selected]

        if args.history == 'r':
            remove_from_history(anime)
            continue

        try:
            provider.info_anime(anime)
        except (LookupError, ProviderError) as error:
            ut.console.print(str(error), style="error")
            ut.console.print("Cercarlo manualmente", style="highlight")
            continue

        if info:
            ut.console.clear()
            ut.console.print(anime)
            #stampo piccolo menu per scegliere se guardare l'anime o tornare indietro
            if Fzf().run(["indietro","guardare"]) == "indietro":
                continue

        if len(anime.episodes()) == 0:
            try:
                provider.episodes(anime)
            except ProviderError as error:
                ut.console.print(str(error), style="error", markup=False)
                continue

        if len(anime.episodes()) == 0:
            ut.console.print("Eh, volevi! L'anime non è ancora stato rilasciato", style="error")
            sleep(1)
            reload = False
            continue

        if (hist or latest) and not anime.has_episode(anime.curr_ep):
            anime.curr_ep = anime.episodes()[0]
        if hist and anime.episode(anime.curr_ep).is_completed():
            if not anime.episode(anime.curr_ep).has_next():
                ut.console.print(f"L'episodio {anime.episode(anime.curr_ep).numeric() + 1} di {anime.name} non è ancora stato rilasciato!", style="error")
                sleep(1)
                if len(animelist) == 1:
                    exit()
                reload = False
                continue
            episodes = [anime.episode(anime.curr_ep).next()]
        elif latest or hist:
            episodes = [anime.episode(anime.curr_ep)]
        else:
            episodes = select_episodes(anime)

        episode = episodes[0]

        if downl:
            downloaded = download.episodes(anime, episodes, provider)
            if not downloaded:
                continue
            episode = downloaded[0]

            anime.curr_ep = episode.num
            if not private and not any(anime == a for a in history.get()):
                history.update(anime, episode)

            answer = Fzf().run(["esci","indietro","guarda"])
            if answer == "esci":
                exit()
            if answer == "indietro":
                continue

        if not anime.has_all_episodes() and not offline:
            try:
                provider.episodes(anime)
            except ProviderError as error:
                ut.console.print(str(error), style="warning", markup=False)

        while True:
            try:
                watch_episode(anime, episode, provider)
            except (ProviderError, OSError, subprocess.SubprocessError) as error:
                ut.console.print(str(error), style="error", markup=False)
                break

            # menù che si visualizza dopo aver finito la riproduzione
            menu_actions = create_ep_menu(anime, episode)

            res = menu_actions[Fzf().run(list(menu_actions.keys()))]()
            if not isinstance(res, Anime.Episode):
                break
            episode = res

        reload = True

history = History()
open_player = open_mpv
complete_limit = 90


def main():
    try:
        _main()
    except (KeyboardInterrupt, EOFError):
        return
    except (ProviderError, OSError, ValueError, KeyError, subprocess.SubprocessError, anilist.TokenError) as error:
        ut.console.print(f"Impossibile continuare: {error}", style="error", markup=False)
        ut.console.print("Controlla la connessione e la configurazione con aw-cli -a.")
        raise SystemExit(1)

if __name__ == "__main__":
    main()
