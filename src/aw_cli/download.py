import asyncio
from pathlib import Path
from httpx import AsyncClient
from rich.progress import Progress, BarColumn, TextColumn, TaskID, DownloadColumn, TransferSpeedColumn
from . import utilities as ut
from .anime import Anime
from .providers import Provider

from functools import lru_cache

@lru_cache
def path(create: bool = True) -> Path:
    """
    Restituisce il percorso di download dell'anime, a seconda del sistema operativo in uso.
    Se create è True (valore predefinito) e il percorso non esiste, viene creato.

    Args:
        create (bool, optional): se impostato a True, crea il percorso se non esiste. Valore predefinito: True.

    Returns:
        Path: il percorso di download dell'anime.
    """

    configured = ut.config_data.get("general", {}).get("download-path")
    if configured:
        path = Path(configured).expanduser()
    elif ut.os_name == "iSH":
        path = Path.home() / "Documents/Anime"
    elif ut.os_name == "Android":
        path = Path("/sdcard/Movies/Anime")
    else:
        path = Path.home() / "Videos/Anime"

    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path

def episode_path(anime: Anime, episode: Anime.Episode) -> Path:
    return path(create=False) / ut.sanitize_filename(anime.name) / (ut.sanitize_filename(str(episode)) + ".mp4")


def episodes(anime: Anime, episodes: list[Anime.Episode], provider: Provider) -> list[Anime.Episode]:
    """
    Scarica più episodi in modo concorrente (max concurrent_downloads).

    Args:
        anime (Anime): l'anime di cui scaricare gli episodi.
        episodes (list[Anime.Episode]): la lista degli episodi da scaricare.
        provider (Provider): il provider da cui scaricare gli episodi.
    """
    async def download_worker(ep: Anime.Episode, task_id: TaskID, progress: Progress, sem: asyncio.Semaphore):
        async with sem:
            filename = episode_path(anime, ep)
            if filename.exists():
                progress.update(task_id, completed=100, total=100, description=f"[green]Ep. {ep.num} (Esistente)")
                return ep

            filename.parent.mkdir(parents=True, exist_ok=True)
            try:
                url = await asyncio.to_thread(provider.episode_link, anime, ep)
            except Exception as e:
                progress.console.print(f"[red]Errore link Ep. {ep.num}: {e}")
                return

            temp_filename = filename.with_name(f"{filename.name}.temp")
            try:
                async with AsyncClient(follow_redirects=True, timeout=30) as client:
                    async with client.stream("GET", url, headers=provider.Client.headers) as response:
                        response.raise_for_status()
                        if "text/html" in response.headers.get("content-type", "").lower():
                            raise ValueError("La fonte ha restituito una pagina HTML anziché un video")
                        total = int(response.headers.get('content-length', 0))
                        progress.update(task_id, total=total)

                        downloaded = 0
                        with open(temp_filename, "wb") as f:
                            async for chunk in response.aiter_bytes(1024):
                                if chunk:
                                    n = f.write(chunk)
                                    downloaded += n
                                    progress.update(task_id, advance=n)

                        if downloaded == 0:
                            raise ValueError("Il video scaricato è vuoto")

                temp_filename.rename(filename)
                progress.update(task_id, description=f"[success]Ep. {ep.num} (Completato)[/]")
                return ep
            except Exception as e:
                temp_filename.unlink(missing_ok=True)
                progress.console.print(f"[error]Errore download Ep. {ep.num}: {e}[/]")

    async def _download_all():
        concurrent_downloads = max(1, min(8, int(ut.config_data["general"].get("parallel-downloads", 1 if ut.os_name == "iSH" else 3))))
        semaphore = asyncio.Semaphore(concurrent_downloads)
        ordered_eps = sorted(episodes, key=lambda e: e.numeric())

        with Progress(
            TextColumn("[info]{task.description}[/]", style="info"),
            BarColumn(bar_width=None),
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            console=ut.console,
        ) as progress:
            tasks = []
            for ep in ordered_eps:
                task_id = progress.add_task(str(ep), total=None, start=True)
                tasks.append(asyncio.create_task(download_worker(ep, task_id, progress, semaphore)))

            results = await asyncio.gather(*tasks)
            return [ep for ep in results if ep is not None]

    return asyncio.run(_download_all())
