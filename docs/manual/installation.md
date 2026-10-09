# Installation

## Ce qu'il faut

| Élément | Pourquoi |
|---|---|
| Linux avec PipeWire, `pipewire-pulse` et `pipewire-jack` | lecture, capture et enregistrement |
| `uv` | installe Python 3.11 et les dépendances |
| `ffmpeg`, `portaudio` | conversions audio, accès à la carte son |
| une carte Intel Arc avec ses pilotes (`intel-compute-runtime`, `level-zero-loader`, `vulkan-intel`) | séparation en pistes, transcription, prises |
| environ 6 Go de disque | modèles et moteurs |

`arr` est développé et vérifié sur une Intel Arc A770 de 16 Go. Sans cette carte, `arr
doctor` échoue ; les commandes qui n'utilisent aucun modèle (projet, mix, lecture, capture,
enregistrement) restent utilisables.

## Installer

```
git clone https://github.com/cedricbou/music-arranger.git ~/dev/music-arranger
cd ~/dev/music-arranger
uv sync
ln -s ~/dev/music-arranger/.venv/bin/arr ~/.local/bin/arr   # ~/.local/bin doit être dans le PATH
arr --install-completion                                    # complétion par Tab ; ouvrir un nouveau terminal
```

Utilisez un lien et non un alias : la complétion appelle `arr` hors du shell et ne
trouverait pas un alias.

## Installer les modèles

```
arr models pull
arr doctor
```

`arr models pull` est la seule commande qui télécharge des modèles. Elle installe :

| Élément | Rôle | Commandes qui s'en servent |
|---|---|---|
| Demucs | sépare un morceau en pistes | `arr split` |
| beat_this | trouve les temps et les mesures | `arr analyze`, `arr transcribe`, `arr split tNNN` |
| SheetSage2 | écrit la partition du morceau | `arr transcribe` |
| YuE2 et le moteur audio.cpp | rend une prise complète | `arr render` |

`arr doctor` doit afficher `xpu: disponible` et « présent » pour chaque moteur.

## Où sont rangées les choses

| Quoi | Où | Pour le déplacer |
|---|---|---|
| modèles et moteurs | `~/.local/share/arr` | variable d'environnement `ARR_HOME` |
| réglages audio | `~/.config/arr/audio.toml` | variable d'environnement `ARR_AUDIO` |
| vos projets | où vous lancez `arr init` ou `arr capture` | ce sont de simples dossiers |

## Réseau et vie privée

Aucun son ne quitte la machine. Deux commandes seulement utilisent le réseau :

- `arr models pull` télécharge les modèles ;
- `arr lyrics fetch` envoie l'artiste et le titre à lrclib.net pour trouver les paroles.

## Mettre à jour

```
cd ~/dev/music-arranger
git pull
uv sync
arr models pull      # seulement si les notes de version le demandent
```

## Licence des modèles

YuE2 et SheetSage2 sont publiés sous CC BY-NC 4.0 : usage non commercial.
