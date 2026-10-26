# anime-pad

Adattamento non ufficiale di [aw-cli](https://github.com/fexh10/aw-cli) per iOS e iPadOS tramite iSH Shell. Supporta anche Linux, macOS e Android.

## Correzioni principali

- Gli errori delle fonti non fanno più fallire la ricerca su `None`: puoi riprovare oppure scrivere `exit`.
- Menu numerici su iSH, disponibili anche sugli altri sistemi se `fzf` manca o non funziona.
- AnimeWorld supporta sia i link nell'HTML sia i link caricati tramite API. AnimeUnity rinnova una volta il token CSRF scaduto.
- I download seguono i reindirizzamenti e rifiutano errori HTTP, pagine HTML e risposte vuote. Solo i download riusciti diventano file `.mp4`.
- Configurazione e cronologia restano in `~/.config/anime-pad`, oppure sotto `XDG_CONFIG_HOME`. I vecchi file presenti nella cartella del pacchetto vengono copiati al primo avvio senza cancellare gli originali.
- L'aggiornamento integrato usa questo repository.

## Installazione su iSH

Serve Python **3.10 o successivo**. Esegui un comando alla volta.

Aggiorna l'indice dei pacchetti:

```sh
apk update
```

Installa gli strumenti:

```sh
apk add python3 py3-pip git
```

Controlla la versione di Python. Se è inferiore a 3.10, occorre prima aggiornare l'ambiente Alpine di iSH:

```sh
python3 --version
```

Crea un ambiente dedicato:

```sh
python3 -m venv ~/anime-pad-env
```

Attivalo:

```sh
. ~/anime-pad-env/bin/activate
```

Installa il programma:

```sh
python -m pip install git+https://github.com/VenomDrake/anime-pad.git@main
```

Forza la modalità iSH se il rilevamento automatico tramite `/proc/ish` non è disponibile:

```sh
export ISPAD=1
```

Avvia:

```sh
aw-cli
```

Nelle sessioni successive riattiva l'ambiente prima di usare `aw-cli`. `ISPAD=1` vale per la sessione corrente; puoi inserirlo nel tuo `~/.profile` se necessario.

## Menu e riproduzione su iPad

Digita il numero accanto alla voce e premi Invio. `n` e `p` cambiano pagina; `q` chiude il programma. Nei menu di download puoi selezionare più **posizioni del menu** con `1,3-5`, oppure `*` per tutte. Questi numeri sono gli indici visualizzati, non necessariamente i numeri degli episodi.

iSH non esegue le app iOS VLC/MPV come programmi Linux. La modalità iPad mostra il link da aprire manualmente in un player esterno. Per i file scaricati usa l'app File, abilitando la posizione iSH. Il programma chiede se l'episodio è stato completato: il semplice avvio di un player esterno non viene registrato come visione completata.

Quando la fonte non fornisce un link diretto e l'indirizzo della pagina è disponibile, la modalità link mostra la pagina dell'episodio da aprire nel browser. Questo non rende disponibile il download.

## Comandi principali

| Comando | Funzione |
| --- | --- |
| `aw-cli` | Cerca un anime |
| `aw-cli -d` | Seleziona e scarica episodi |
| `aw-cli -c` | Apri la cronologia |
| `aw-cli -o` | Consulta gli episodi scaricati presenti in cronologia |
| `aw-cli -l` | Mostra le ultime uscite |
| `aw-cli -a` | Ripeti la configurazione e cambia provider |
| `aw-cli -h` | Mostra tutte le opzioni |

Su iSH i download vanno in `~/Documents/Anime`. Su Android viene usata `/sdcard/Movies/Anime`; sugli altri sistemi `~/Videos/Anime`. Puoi scegliere un'altra directory aggiungendo `download-path = "/percorso/Anime"` alla sezione `[general]` del file di configurazione. Su iSH i download sono sequenziali per impostazione predefinita.

## Aggiornamento

Con l'ambiente dedicato attivo:

```sh
aw-cli -u
```

In alternativa:

```sh
python -m pip install --upgrade --force-reinstall git+https://github.com/VenomDrake/anime-pad.git@main
```

## Problemi di ricerca

Un errore HTTP, un timeout o una pagina cambiata sono diversi da una ricerca senza risultati. Il programma mostra il nome della fonte e il problema rilevato. Puoi riprovare; per cambiare fonte esci con `exit` e avvia `aw-cli -a`.

Le fonti esterne possono essere temporaneamente non disponibili o cambiare formato. La gestione degli errori non garantisce la disponibilità dei siti. Per chiedere assistenza invia il messaggio completo, il provider scelto e la versione mostrata da `aw-cli -v`; non condividere il token AniList.

## Sviluppo e verifiche

I test usano risposte HTTP simulate e le pagine di esempio del repository; non scaricano video e non dipendono dai siti esterni.

```sh
uv run --locked pytest -q
```

Controllo dei tipi:

```sh
uv run --locked pyright
```

GitHub Actions esegue i test con Python 3.10 e 3.13.

## Crediti e licenza

Progetto originale: [fexh10/aw-cli](https://github.com/fexh10/aw-cli). Adattamento: [VenomDrake/anime-pad](https://github.com/VenomDrake/anime-pad). Licenza GPL-3.0; vedere [LICENSE](LICENSE) e [disclaimer.md](disclaimer.md).
