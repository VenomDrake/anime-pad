from pathlib import Path
import re
from .provider import Provider, Anime

class LocalProvider(Provider):
    """
    Provider locale per la gestione degli anime scaricati.
    Permette di cercare, elencare e ottenere informazioni sugli anime presenti localmente.
    - search: cerca tra gli anime scaricati
    - latest: non implementata
    - episodes: carica gli episodi scaricati
    - episode_link: restituisce il path locale
    - info_anime: carica info dalla cronologia
    """
    def __init__(self, path, history: list[Anime]):
        super().__init__(path)
        self.history = history

    def _search(self, input: str) -> list[Anime]:
        """Restituisce gli anime scaricati localmente, ignorando l'input di ricerca."""
        animes = []
        base_path = Path(self.BASE_URL)
        if not base_path.exists():
            return []

        for item in base_path.iterdir():
            if not item.is_dir():
                continue
            name = item.name
            anime = Anime(name, "local")
            if anime in self.history:
                self.episodes(anime)
                self.info_anime(anime)
                if not anime.episodes():
                    continue
                anime.curr_ep = anime.episodes()[0]
                animes.append(anime)
        return animes

    def _latest(self, filter: str, specials: bool) -> list[Anime]:
        for anime in (res :=self.search("")):
            anime.curr_ep = anime.episodes()[-1]
        return res

    def _episodes(self, anime: Anime) -> dict[str, str]:
        base_path = Path(self.BASE_URL) / anime.name
        if not base_path.exists():
            return {}

        filenames = [p.name for p in base_path.iterdir() if p.is_file() and p.suffix == ".mp4" and "Ep. " in p.name]
        if len(filenames) == 0:
            return {}

        episodes = dict[str, str]()
        for filename in filenames:
            num = filename.rsplit("Ep. ", 1)[1][:-4]
            if re.fullmatch(r"\d+(?:\.\d+|-\d+)?", num):
                episodes[num] = filename
        return episodes

    def _episode_link(self, anime: Anime, episode: Anime.Episode) -> str:
        return str(Path(self.BASE_URL) / anime.name / episode.ref)

    def _info_anime(self, anime: Anime):
        other = self.history[self.history.index(anime)]
        anime.ref = other.ref
        anime.set_info(other.anilist_id, other.status, other.info.copy())
