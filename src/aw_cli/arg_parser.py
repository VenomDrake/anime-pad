import argparse
from .utilities import os_name
from importlib.metadata import version, PackageNotFoundError
from .update import update

class Update(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        update(str(values) if values else "")
        parser.exit()


try:
    package_version = version("aw-cli")
except PackageNotFoundError:
    package_version = "versione sorgente"

# args
downl = False
latest = False
offline = False
hist = False
info = False
private = False

# args
parser = argparse.ArgumentParser(
    "aw-cli",
    description="Guarda anime dal terminale e molto altro!",
    add_help=False
)

info_group = parser.add_argument_group("Informazioni")
options_group = parser.add_argument_group("Opzioni")
config_group = parser.add_argument_group("Configurazione")

info_group.add_argument(
    '-h',
    '--help',
    action='help',
    help="mostra questo messaggio"
)

info_group.add_argument(
    '-v',
    '--versione',
    action='version',
    version=package_version, help="stampa la versione del programma"
)

options_group.add_argument(
    '-c',
    '--cronologia',
    nargs='?',
    const=True,
    choices=['r'], dest='history',
    help='continua a guardare un anime dalla cronologia. \'r\' per rimuovere un anime (opzionale)'
)

options_group.add_argument(
    '-l',
    '--lista',
    nargs='?',
    const='a',
    choices=['a', 's', 'd', 't'],
    dest='latest',
    help="lista degli ultimi anime usciti. Filtri: a = all, s = sub, d = dub, t = tendenze. Default 'a'"
)

options_group.add_argument(
    '-i',
    '--info',
    action='store_true',
    dest='info',
    help='visualizza le informazioni e la trama di un anime'
)

if os_name != "Android":
    options_group.add_argument(
        '-s',
        '--syncplay',
        action='store_true',
        dest='syncpl',
        help='usa syncplay per guardare un anime insieme ai tuoi amici'
    )

options_group.add_argument(
    '-d',
    '--download',
    action='store_true',
    dest='download', help='scarica gli episodi che preferisci'
)

options_group.add_argument(
    '-o',
    '--offline',
    action='store_true',
    dest='offline',
    help='apri gli episodi scaricati precedentemente direttamente dal terminale'
)

options_group.add_argument(
    '-p',
    '--privato',
    action='store_true',
    dest='private',
    help="guarda un episodio senza che si aggiorni la cronologia o AniList"
)

options_group.add_argument(
    '-u',
    '--update',
    nargs='?',
    action=Update,
    type=str,
    help='aggiorna il programma',
)

config_group.add_argument(
    '-a',
    '--configurazione',
    action='store_true',
    dest='start_config',
    help='avvia il menu di configurazione'
)

args = parser.parse_args()

offline = args.offline
private = args.private
info = args.info
hist = offline or args.history is not None
latest = not offline and args.latest is not None and args.history != 'r'
downl = args.download and not offline and args.history != 'r'
