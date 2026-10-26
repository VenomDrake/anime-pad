import subprocess
import sys
import re
import argparse
import ast
import shlex
import shutil
from rich.prompt import Prompt

import aw_cli.utilities as ut


class Fzf:
    """
    Menu fzf, con alternativa numerica compatibile con iSH.
    """

    _DEFAULTS: dict[str, str | bool] = {
        "tac": True,
        "cycle": True,
        "ansi": True,
        "tiebreak": "begin",
    }

    def run(
        self,
        elements: list[str],
        prompt: str = "> ",
        multi: bool = False,
        filter: bool = False,
    ) -> str:
        """
        Avvia fzf e restituisce la selezione dell'utente.

        Args:
            elements: voci da visualizzare in fzf.
            prompt:   testo del prompt.
            multi:    se True abilita la selezione multipla (Ctrl+A = toggle all).
            filter:   se True abilita il filtro per range (formato: inizio-fine).
        """
        cmd = self._build_cmd(elements=elements, prompt=prompt, multi=multi, filter=filter)
        elements = [str(element) for element in elements]
        if not elements:
            raise ValueError("Nessuna voce disponibile nel menu")
        if ut.os_name == "iSH" or not shutil.which("fzf"):
            return self._numbered_menu(elements, prompt, multi)
        try:
            while True:
                process = subprocess.run(
                    cmd,
                    input="\n".join(elements),
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=None,
                )

                if process.returncode in {1, 130}:
                    raise SystemExit(0)

                if process.returncode != 0:
                    ut.console.print("Menu fzf non disponibile: uso il menu numerico.", style="warning")
                    return self._numbered_menu(elements, prompt, multi)

                if process.stdout.strip():
                    return process.stdout.strip()
                raise SystemExit(0)
        except OSError:
            return self._numbered_menu(elements, prompt, multi)
        except KeyboardInterrupt:
            exit()

    def _numbered_menu(self, elements: list[str], prompt: str, multi: bool) -> str:
        page = 0
        size = 20
        while True:
            start = page * size
            for i, element in enumerate(elements[start:start + size], start + 1):
                plain = re.sub(r"\x1b\[[0-9;]*m", "", element)
                ut.console.print(f"{i}) {plain}", markup=False)
            ut.console.print("n: avanti, p: indietro, q: esci" + ("; più voci: 1,3-5 oppure * per tutte" if multi else ""))
            choice = Prompt.ask(prompt, console=ut.console).strip().lower()
            if choice in {"q", "exit"}:
                raise SystemExit(0)
            if choice == "n":
                page = min(page + 1, (len(elements) - 1) // size)
                continue
            if choice == "p":
                page = max(0, page - 1)
                continue
            try:
                if multi and choice == "*":
                    return "\n".join(elements)
                selected = []
                for part in choice.split(","):
                    bounds = part.split("-") if multi else [part]
                    if len(bounds) > 2:
                        raise ValueError
                    first, last = int(bounds[0]), int(bounds[-1])
                    if not 1 <= first <= last <= len(elements):
                        raise ValueError
                    for index in range(first - 1, last):
                        if index not in selected:
                            selected.append(index)
                if not multi and len(selected) != 1:
                    raise ValueError
                return "\n".join(elements[index] for index in selected)
            except ValueError:
                ut.console.print("Selezione non valida.", style="error")

    def _build_cmd(
        self,
        elements: list[str],
        prompt: str,
        multi: bool,
        filter: bool = False,
    ) -> list[str]:
        """Costruisce la lista di argomenti per il processo fzf."""
        cmd = ["fzf"]

        if "height" not in self._DEFAULTS:
            cmd += [f"--height={len(elements) + 2}"]

        for key, value in self._DEFAULTS.items():
            flag = f"--{key}"
            if isinstance(value, bool):
                if value:
                    cmd.append(flag)
            else:
                cmd += [flag, str(value)]

        cmd += [f"--prompt={prompt}"]

        if multi:
            cmd += ["--multi", "--bind", "ctrl-a:toggle-all"]

        if filter:
            reload_cmd = f"{shlex.quote(sys.executable)} -m aw_cli.fzf.fzf --filter {{q}} --episodes {shlex.quote(repr(elements))}"
            cmd += [
                "--phony",
                "--bind", f"change:reload({reload_cmd})",
                "--header=Range: inizio-fine. crtl+A seleziona tutto, tab/shift+tab selezione singola"
            ]

        return cmd


def _filter_episodes(query: str, episodes_raw: str) -> None:
    """
    Filtra gli episodi in base alla query e stampa il risultato su stdout.

    Formati query:
      - "5-10" → episodi con numero nell'intervallo [5, 10]
      - "5-"   → episodi con numero >= 5
      - "7"    → episodi che contengono "7" (sottostringa)

    Un episodio stesso può essere un range (es. "29-30"). Il filtro
    ha successo se i due intervalli si intersecano.
    """

    episodes = ast.literal_eval(episodes_raw)
    if not isinstance(episodes, list) or not all(isinstance(e, str) for e in episodes):
        raise ValueError("Lista episodi non valida")

    if not query:
        print("\n".join(episodes))
        return

    if "-" in query:
        parts = query.split("-", 1)
        try:
            lo = float(parts[0]) if parts[0] else None
            hi = float(parts[1]) if parts[1] else None

            for e in episodes:
                e_lo, e_hi = None, None
                if "-" in e:
                    e_parts = e.split("-", 1)
                    try:
                        e_lo = float(e_parts[0]) if e_parts[0] else None
                        e_hi = float(e_parts[1]) if e_parts[1] else None
                    except ValueError:
                        continue
                else:
                    try:
                        e_lo = e_hi = float(e)
                    except ValueError:
                        continue

                if e_lo is None or e_hi is None:
                    continue

                if lo is not None and hi is not None:
                    if max(lo, e_lo) <= min(hi, e_hi):
                        print(e)
                elif lo is not None:
                    if e_hi >= lo:
                        print(e)
                elif hi is not None:
                    if e_lo <= hi:
                        print(e)
        except ValueError:
            pass
    else:
        for e in episodes:
            try:
                if re.search(query, e):
                    print(e)
            except re.error:
                if query in e:
                    print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter", type=str, default="", help="Query per filtrare gli episodi")
    parser.add_argument("--episodes", type=str, required=True, help="Lista episodi JSON")
    args = parser.parse_args()

    _filter_episodes(args.filter, args.episodes)
