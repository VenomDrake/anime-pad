Ecco il `README.md` aggiornato con i nuovi comandi per la tua repo `VenomDrake/anime-pad`.

````md
# anime-pad per iOS e iPadOS tramite iSH Shell

Porting e adattamento non ufficiale di `aw-cli` per utilizzo su iOS e iPadOS tramite iSH Shell.

Il progetto originale è disponibile qui:  
https://github.com/fexh10/aw-cli

Questa versione modificata è disponibile qui:  
https://github.com/VenomDrake/anime-pad

## Installazione su iSH Shell

Esegui questi comandi uno alla volta:
````
```sh
apk update
```

```sh
apk upgrade
```

```sh
apk add python3 py3-pip git fzf
```

```sh
python3 -m pip install --upgrade pip
```

```sh
python3 -m pip install git+https://github.com/VenomDrake/anime-pad.git
```

## Modalità iPadOS

Per forzare la modalità iPadOS:

```sh
export ISPAD=1
```

Per renderla permanente ad ogni avvio di iSH:

```sh
echo 'export ISPAD=1' >> ~/.profile
```

```sh
. ~/.profile
```

## Verifica installazione

```sh
aw-cli -h
```

## Avvio

```sh
aw-cli
```

## Aggiornamento futuro

Per aggiornare il programma dalla repo online:

```sh
python3 -m pip install --upgrade git+https://github.com/VenomDrake/anime-pad.git
```

## Download su iPad e iSH

Con la patch dedicata, gli episodi scaricati vengono salvati in:

```sh
~/Documents/Anime
```

Per controllare i file scaricati:

```sh
ls ~/Documents/Anime
```

## Note

Questa versione nasce per riprendere e adattare il progetto originale all’utilizzo su iOS e iPadOS tramite iSH Shell.

Il progetto originale `aw-cli` è stato creato e mantenuto da fexh10 ed è disponibile su GitHub. Il README originale indica che `aw-cli` permette di guardare anime dal terminale, usando fonti come AnimeWorld e AnimeUnity.

Fonte:  
https://github.com/fexh10/aw-cli

## Crediti

Progetto originale:  
https://github.com/fexh10/aw-cli

Versione modificata:  
https://github.com/VenomDrake/anime-pad

Tutti i crediti principali vanno agli autori originali del progetto `aw-cli`.
