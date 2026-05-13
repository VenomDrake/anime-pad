````md
# aw-cli per iOS e iPadOS tramite iSH Shell

Porting e adattamento non ufficiale di `aw-cli` per utilizzo su iOS e iPadOS tramite iSH Shell.

Il progetto originale è disponibile qui:  
https://github.com/fexh10/aw-cli

## Installazione su iSH Shell

Esegui questi comandi uno alla volta:
````

```sh
apk update
````

```sh
apk upgrade
```

```sh
apk add python3 py3-pip fzf vlc
```

```sh
python3 -m pip install --upgrade pip
```

```sh
python3 -m pip install aw-cli
```

## Modalità iPadOS

Per forzare la modalità iPadOS, consigliata su iPad:

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

```sh
aw-cli -v
```

## Avvio

```sh
aw-cli
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

Questa versione nasce per riprendere e adattare il progetto all’utilizzo su iOS e iPadOS tramite iSH Shell.

Il progetto originale `aw-cli` è stato creato e mantenuto da fexh10 ed è disponibile su GitHub. Il README originale indica che `aw-cli` permette di guardare anime dal terminale, usando fonti come AnimeWorld e AnimeUnity, con supporto a VLC, MPV e fzf.
Fonte: [https://github.com/fexh10/aw-cli](https://github.com/fexh10/aw-cli)

## Crediti

Progetto originale:
[https://github.com/fexh10/aw-cli](https://github.com/fexh10/aw-cli)

Tutti i crediti principali vanno agli autori originali del progetto `aw-cli`.

```

Ho mantenuto i comandi separati, così restano facili da copiare uno alla volta.
```
