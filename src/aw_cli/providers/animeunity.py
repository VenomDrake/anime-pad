import re
import json
from html import unescape
from ..anime import Anime, AnimeStatus
from .provider import Provider, HTTPError, media_url
from .html import Tags

class Animeunity(Provider):
    """
    Classe che gestisce il collegamento con Animeworld.
    
    Attributes:
        _url (str): l'url del sito di Animeworld.
        _headers (dict): gli headers da utilizzare per le richieste HTTP.
        _cookies (dict): i cookies da utilizzare per le richieste HTTP.
        _visited (dict): le pagine già visitate.
    """
    def __init__(self):
        super().__init__("https://www.animeunity.so")
        self.html = ""

    
    def _get_token(self) -> None:
        # Send a GET request to the specified URL
        response = self.Client.get(self.BASE_URL)
        response.raise_for_status()
        self.html = response.text
        # Regex to find the meta tag with csrf-token and extract the content
        csrf_token = next((attrs.get("content") for attrs, _ in Tags(self.html, "meta").items if attrs.get("name") == "csrf-token"), None)
        if not csrf_token:
            raise ValueError("CSRF token not found in the HTML")
        self.Client.headers['x-csrf-token'] = csrf_token


    def _search(self, input: str) -> list[Anime]:
        if not self.html:
            self._get_token()
        search_url = f"{self.BASE_URL}/livesearch"
        response = self.Client.post(
            url=search_url,
            data={"title": input}
        )
        if response.status_code == 419:
            self._get_token()
            response = self.Client.post(search_url, data={"title": input})
        response.raise_for_status()

        results = response.json()['records']
        if not isinstance(results, list):
            raise ValueError("Risposta di ricerca non valida")
        animes = list[Anime]()
        for result in results:
            title, last_ep, anilist_id, status, info = self._parse_info(result)
            anime = Anime(title, str(result['id']), last_ep=last_ep)
            anime.set_info(anilist_id, status, info)
            animes.append(anime)

        return animes


    def _latest(self, filter, specials) -> list[Anime]:
        self._get_token()
        regex = re.search(r'<layout-items[^>]*items-json="([^"]*)"', self.html)
        if not regex:
            raise ValueError("Errore nel parsing della pagina principale")

        data_attribute = unescape(regex.group(1))
        json_data = json.loads(data_attribute)['data']
        animes = list[Anime]()
        for data in json_data:
            result = data['anime']
            title, _, anilist_id, status, info = self._parse_info(result)
            if filter == "d" and info["Audio"] != "Italiano":
                continue
            if filter == "s" and info["Audio"] == "Italiano":
                continue
            anime = Anime(title, str(result['id']), curr_ep=str(data['number']))
            anime.update_episodes({str(data['number']): str(data['id'])}, specials=specials)
            anime.set_info(anilist_id, status, info)
            animes.append(anime)
        return animes

    def _episodes(self, anime: Anime) -> dict[str, str]:
        episodes = {}
        start_range = 0
        counts = [str(anime.last_ep), str(anime.info.get("Episodi", "0"))]
        episode_count = max((int(count) for count in counts if count.isdigit()), default=0)
        # Fetch episodes in chunks
        while start_range <= episode_count:
            end_range = min(start_range + 119, episode_count)
            search_url = f"{self.BASE_URL}/info_api/{anime.ref}/1"
            response = self.Client.get(
                url=search_url,
                params={
                    "start_range": start_range,
                    "end_range": end_range
                }
            )
            response.raise_for_status()
            episodes.update({str(episode['number']): str(episode['id']) for episode in response.json()['episodes']})
            start_range = end_range + 1
        return episodes

    def _episode_link(self, anime: Anime, episode: Anime.Episode) -> str:
        embed_url = f"{self.BASE_URL}/embed-url/{episode.ref}"
        response = self.Client.get(embed_url)
        response.raise_for_status()
        iframe_src = media_url(response.text.strip())

        # Fetch the video page
        video_response = self.Client.get(iframe_src)
        video_response.raise_for_status()

        # Usa una regex per estrarre il link video MP4 dallo script
        match = re.search(r'''window\.downloadUrl\s*=\s*(["'])(.*?)\1''', video_response.text)
        if not match:
            raise ValueError("Link video non trovato nella pagina")
        return media_url(unescape(match.group(2)))

    def _info_anime(self, anime: Anime):
        if not anime.ref.isdigit():
            raise HTTPError("Errore 404: pagina non trovata")
        search_url = f"{self.BASE_URL}/info_api/{anime.ref}/"
        response = self.Client.get(search_url)
        response.raise_for_status()
        data = response.json()
        match data.get('status'):
            case "In Corso":
                anime.status = AnimeStatus.ONGOING
            case "Terminato":
                anime.status = AnimeStatus.FINISHED
            case "Non Rilasciato":
                anime.status = AnimeStatus.NOT_RELEASED
            case _:
                anime.status = AnimeStatus.UNKNOWN
        anime.last_ep = str(data.get('episodes_count') or anime.last_ep)
        anime.info["Genere"] = ', '.join(data.get('genres') or [])
        # anime.info["Correlati"] = data['related']

    def _parse_info(self, data: dict) -> tuple[str, str, int, AnimeStatus, dict[str, str]]:
        title = data.get('title_eng') or data.get('title') or data.get('title_it')
        if not isinstance(title, str) or not title.strip():
            raise ValueError("Titolo mancante nella risposta della fonte")
        last_ep = str(data.get('real_episodes_count') or "0")
        anilist_id = int(data.get('anilist_id') or 0)
        match data.get('status'):
            case "In Corso":
                status = AnimeStatus.ONGOING
            case "Terminato":
                status = AnimeStatus.FINISHED
            case "Non Rilasciato":
                status = AnimeStatus.NOT_RELEASED
            case _:
                status = AnimeStatus.UNKNOWN
        data = {key: data.get(key) or "" for key in (
            'type', 'dub', 'date', 'season', 'studio', 'score', 'episodes_length',
            'episodes_count', 'visite', 'plot'
        )}
        info = {
            "Categoria": data['type'],
            "Audio": "Italiano" if data['dub'] else "??",
            "Data di Uscita": data['date'],
            "Stagione": data['season'],
            "Studio": data['studio'],
            "Voto": data['score'],
            "Durata": f"{data['episodes_length']} min", # potrebbe non essere in minuti"
            "Episodi": str(data['episodes_count'] or "??"),
            "Visualizzazioni": data['visite'],
            "Trama": data['plot'],
        }
        return title, last_ep, anilist_id, status, {key: str(value) for key, value in info.items()}
