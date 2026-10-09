# Développement et construction

## Lancer depuis les sources

```bash
pip install pystray pillow
python HRDtoWavelog.pyw
```

L'app fonctionne aussi sans `pystray`/`pillow`, mais sans icône dans la zone de notification.

## Tests

```bash
python -m unittest tests.test_core
```

Les tests utilisent un **faux Wavelog** (serveur HTTP local qui imite l'API), un **faux HRD** qui envoie
des QSO en UDP au format XML de HRD, et un **faux log HRD** (base SQLite avec la même table) :
voir `tests/fakes.py`. Rien ne touche à un vrai log.

Pour voir l'app tourner sans risque :

```bash
python tests/demo.py C:\Temp\demo-hrdwl
```

Le script crée un faux Wavelog et la config correspondante, puis envoie un QSO toutes les 3 s
en UDP (port 12099 par défaut), comme le ferait HRD. Lance ensuite l'app avec `APPDATA=C:\Temp\demo-hrdwl`. Ajoute aussi le dossier
`site-packages` utilisateur à `PYTHONPATH` si `pystray`/`pillow` y sont installés.

## Construire l'exécutable et l'installeur

```bash
pip install pyinstaller pystray pillow
python packaging/build.py --installer
```

Résultat dans `packaging/dist/` :
- `HRDtoWavelog/` : l'application en dossier (c'est ce que l'installeur embarque) ;
- `HRDtoWavelog-Setup-<version>.exe` : l'installeur (nécessite [Inno Setup 6](https://jrsoftware.org/isdl.php)).

## Publier une version

1. Mettre à jour `APP_VERSION` dans `hrdwl/core.py` et `CHANGELOG.md`.
2. Commit, puis tag : `git tag v1.2.3 && git push origin v1.2.3`.
3. GitHub Actions (`.github/workflows/build.yml`) lance les tests, construit l'installeur, puis
   l'attache à la Release.

## Captures d'écran de la doc

`packaging/screenshot.py fr|en sortie.png [délai_ms]` capture la fenêtre (à lancer avec la démo).
