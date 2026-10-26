import re
from html import unescape
from urllib.parse import quote_plus, urljoin
from ..anime import Anime, AnimeStatus
from .provider import Provider, HTTPError, media_url
from .html import Tags

class Animeworld(Provider):
    """
    Classe che gestisce il collegamento con Animeworld.

    Attributes:
        _url (str): l'url del sito di Animeworld.
        _headers (dict): gli headers da utilizzare per le richieste HTTP.
        _cookies (dict): i cookies da utilizzare per le richieste HTTP.
        _visited (dict): le pagine già visitate.
    """
    def __init__(self):
        super().__init__("https://www.animeworld.ac")
        self._visited = {}

    def _get_html(self, url: str) -> str:
        """
        Ottiene l'html della pagina web `url`.
        Se la pagina non viene trovata o c'è un errore di connessione,
        viene stampato un messaggio di errore e il programma termina.
        Se la pagina viene reindirizzata, vengono aggiornati i `cookies` e viene ripetuta la richiesta.

        Args:
            url (str): la pagina web da cui prendere l'html.

        Returns:
            str: l'html della pagina web selezionata.
        """
        if not re.match(r'^https?://', url):
            raise HTTPError("Errore 404: pagina non trovata")

        response = self.Client.get(url)
        response.raise_for_status()

        if response.status_code == 202:
            match = re.search(r'(SecurityAW-\w+)=(.*) ;', response.text)
            if not match:
                raise HTTPError("Errore: Cookies non trovati")
            self.Client.cookies.set(match.group(1), match.group(2))
            response = self.Client.get(url)
            response.raise_for_status()

        if response.status_code != 200 or "Errore 404" in response.text:
            raise HTTPError("Errore 404: pagina non trovata")

        return response.text

    def _search(self, input: str) -> list[Anime]:
        search_url = self.BASE_URL + "/search?keyword=" + quote_plus(input)
        html = self._get_html(search_url)
        if re.search(r'<div class="alert alert-danger">', html):
            return []

        animes = list[Anime]()
        # prendo i link degli anime relativi alla ricerca
        for attrs, name in Tags(html, "a").items:
            if "name" in attrs.get("class", "").split() and attrs.get("href") and name:
                animes.append(Anime(name, urljoin(self.BASE_URL, attrs["href"])))

        return animes

    def _latest(self, filter: str, specials: bool) -> list[Anime]:
        html = self._get_html(self.BASE_URL)
        animes = list[Anime]()

        for attrs, _ in Tags(html, "a").items:
            match = re.fullmatch(r"(.+) Ep\.? ([\d.-]+)", attrs.get("title", ""))
            if "poster" not in attrs.get("class", "").split() or not match or not attrs.get("href"):
                continue
            name, ep = match.groups()
            url = urljoin(self.BASE_URL, attrs["href"])
            anime = Anime(name, url, ep)
            anime.update_episodes({ep: url}, specials=specials)
            animes.append(anime)

        BLOCK_SIZE = 45
        filter_keys = ['a', 's', 'd', 't']
        multiplier = filter_keys.index(filter[0]) if filter and filter[0] in filter_keys else 0

        start = multiplier * BLOCK_SIZE
        end = (multiplier + 1) * BLOCK_SIZE if multiplier < len(filter_keys) else None

        return animes[start:end]

    def _episodes(self, anime: Anime):
        html = self._get_html(anime.ref)
        episodes_url = dict[str, str]()
        for attrs, _ in Tags(html, "a").items:
            num, url = attrs.get("data-num", ""), attrs.get("href")
            if re.fullmatch(r"\d+(?:\.\d+|-\d+)?", num) and url:
                episodes_url[num] = urljoin(self.BASE_URL, url)
        return episodes_url

    def _episode_link(self, anime: Anime, episode: Anime.Episode) -> str:
        html = self._get_html(episode.ref)
        for attrs, _ in Tags(html, "a").items:
            if attrs.get("id") == "alternativeDownloadLink" and attrs.get("href"):
                return media_url(urljoin(episode.ref, attrs.get("href", "")))
        # Le pagine recenti caricano i link tramite la stessa API usata dal sito.
        token = next((attrs.get("content") for attrs, _ in Tags(html, "meta").items if attrs.get("name") == "csrf-token"), None)
        episode_id = next((attrs.get("data-episode-id") for attrs, _ in Tags(html, "a").items
                           if attrs.get("data-num") == episode.num and urljoin(self.BASE_URL, attrs.get("href", "")) == episode.ref), None)
        if not token or not episode_id or not episode_id.isdigit():
            raise ValueError("Metadati dell'episodio o link video non disponibili")
        response = self.Client.post(
            f"{self.BASE_URL}/api/download/{episode_id}",
            headers={"CSRF-Token": token, "Referer": episode.ref, "X-Requested-With": "XMLHttpRequest"},
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("error"):
            raise ValueError("La fonte non rende disponibile il download di questo episodio")
        links = payload.get("links", {}).get("9", {}).get(episode.num, {})
        link = links.get("alternativeLink") or links.get("link")
        if not link:
            raise ValueError("La fonte non fornisce un link video diretto per questo episodio")
        return media_url(link)

    def _info_anime(self, anime: Anime):
        html = self._get_html(anime.ref)

        anilist_id = 0
        for attrs, _ in Tags(html, "a").items:
            if attrs.get("id") == "anilist-button":
                match = re.search(r"/anime/(\d+)", attrs.get("href", ""))
                anilist_id = int(match.group(1)) if match else 0

        temp = re.findall(r'<dt>(.*?):</dt>[\n\s]*<dd(?: class="[^"]*")?>((?:.|\n)+?)</dd>', html)
        plot_match = re.search(r'<div class="desc">((?:.|\n)+?)</div>', html)
        if plot_match:
            temp.append(("Trama", plot_match.group(1)))

        info = dict[str, str]()
        status = AnimeStatus.UNKNOWN
        for key, value in temp:
            key, value = key.strip(), value.strip()
            if key == "Stato":
                if match := re.search(r'status=(\d+)"', value):
                    status_val = int(match.group(1))
                    if status_val < len(AnimeStatus):
                        status = list(AnimeStatus)[status_val]
            value = re.sub(r'[\s\n]+', ' ', re.sub(r'<.*?>', '', value)).strip()
            info[key] = unescape(value)

        anime.set_info(anilist_id, status, info)
