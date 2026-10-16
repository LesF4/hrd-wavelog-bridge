# HRDtoWavelog — contexte du projet

Application Windows (Python 3 + tkinter, empaquetée avec PyInstaller + Inno Setup) qui synchronise
**HRD Logbook** (Ham Radio Deluxe) et **Wavelog** dans les deux sens. Interface et docs en français
(+ anglais). Auteur : F4MAJ / Jean-Bernard, licence MIT, dépôt public `LesF4/hrd-wavelog-bridge`.

## Architecture

- `hrdwl/core.py` : toute la logique, sans interface (testable).
  - **HRD → Wavelog** : HRD envoie chaque nouveau QSO en UDP (QSO Forwarding, envoi UDP, XML
    `<contactinfo>` type N1MM, port 12060 par défaut). `UDPListener` écoute **127.0.0.1** uniquement,
    `contact_from_xml()` convertit en ADIF, `upload_qso()` POST `index.php/api/qso`.
  - **Wavelog → HRD** : `fetch_wavelog()` POST `index.php/api/get_contacts_adif` (clé, `station_id`
    liste, `fetchfromid`) toutes les 2 min ; les QSO inconnus partent vers la réception UDP de HRD
    (ADIF, port 2333) via `send_to_hrd()`.
  - `Syncer` (thread) : file d'attente, reprises, anti-doublons, comparaison des deux logs.
  - `History` : `%APPDATA%\HRDtoWavelog\history.json` (liste affichée + file). Identifiants uniques,
    réparés au chargement.
- `hrdwl/app.py` : fenêtre tkinter, réglages, comparaison, barre de progression, icône (pystray),
  démarrage auto (clé `HKCU\...\Run`), instance unique (mutex).
- `hrdwl/i18n.py` : textes FR/EN (mêmes clés dans les deux langues, vérifié par un test).

## Règles importantes (apprises en conditions réelles)

- **HRD sature** si on lui envoie des QSO trop vite (il fait une recherche à chaque réception) et peut se
  fermer brutalement. On envoie **un QSO à la fois** et on attend de le voir dans le log
  (`HRDReader.has_qso`) avant le suivant ; si HRD se ferme, on s'arrête et on marque le QSO.
- **Anti-boomerang** : un QSO ajouté dans HRD depuis Wavelog revient en écho par l'envoi UDP de HRD ;
  il est ignoré (`History.index("down")`). Un QSO venu de HRD n'est jamais renvoyé à HRD.
- **Anti-doublon** : même indicatif + même bande à 15 min près (règle de Wavelog), **sans comparer le
  mode** (HRD écrit « PSK31 », Wavelog « PSK » + sous-mode). Avant d'ajouter dans HRD, on vérifie aussi
  le log HRD lui-même (import ADIF manuel possible).
- Le log HRD (`.hrdsql`, SQLite) est lu **en lecture seule** (`mode=ro`, repli sur une copie) et
  seulement les champs du QSO (`_DB_FIELDS` : jamais adresse, e-mail, coordonnées, notes).
- La route `api/auth/{clé}` de Wavelog répond en **XML**, les autres en JSON. Cloudflare devant certains
  serveurs refuse l'agent « Python-urllib » : on envoie `User-Agent: HRDtoWavelog/<version>`.
- Les longueurs ADIF comptent des **caractères** (Wavelog utilise `mb_substr`) ; vers HRD on encode en cp1252.
- Rien n'est jamais supprimé, ni dans HRD ni dans Wavelog : l'app ne fait que des ajouts.

## Tests — sécurité

```bash
python -m unittest tests.test_core
```

- `tests/fakes.py` : faux Wavelog (HTTP), faux HRD qui envoie (`send_contact`) et qui reçoit
  (`FakeHRDReceiver`, enregistre dans un faux log, peut simuler un plantage).
- **Ne jamais viser les vrais ports** (12060 / 2333) ni le vrai log en test : les tests prennent des
  ports libres et un `APPDATA` temporaire.
- Avant de livrer, démarrer aussi l'app sur une **copie de l'historique réel** (cas de la 1.2.0 qui
  plantait sur des doublons anciens).
- `tests/demo.py`, `tests/ui_check.py`, `packaging/screenshot.py` : démo et vérification de l'interface
  (ports à part ; `refresh_autostart` neutralisé pour ne pas toucher au démarrage auto réel).

## Antivirus

Bitdefender (Advanced Threat Defense) a mis la 1.0 en quarantaine (« lit une base locale + envoie sur
Internet » = profil de voleur de données). Depuis la 1.1, HRD envoie lui-même les QSO (pas de lecture
du log en continu). Fausse alerte signalée à Bitdefender : reconnue et corrigée dans leurs signatures
(octobre 2026). Ne jamais contourner un antivirus : documenter l'exception à ajouter.

## Lancer l'app depuis un outil

Un programme lancé depuis une application Windows empaquetée (MSIX, ex. l'app Claude desktop) voit son
`%APPDATA%` (et une partie de HKCU) redirigé vers `%LOCALAPPDATA%\Packages\<app>\LocalCache\…`. Les réglages
enregistrés ainsi sont invisibles quand l'utilisateur lance l'app normalement. Depuis la 1.2.4, l'app les
récupère d'elle-même (`migrate_from_packaged_copy`) ; mais ne jamais lancer l'app ni son installeur depuis un
outil pour un vrai utilisateur : c'est lui qui la lance.

## Construire et publier

```bash
pip install pyinstaller pystray pillow
python packaging/build.py --installer   # Inno Setup 6 nécessaire en local
```

Publier : mettre à jour `APP_VERSION` (`hrdwl/core.py`) et `CHANGELOG.md`, commit, tag `vX.Y.Z`, push
du tag → GitHub Actions teste, construit `HRDtoWavelog-Setup-X.Y.Z.exe` et l'attache à la Release
(titre « HRD Logbook ⇄ Wavelog vX — synchro dans les deux sens »).
Avant tout push : vérifier qu'aucune donnée personnelle (clé API, adresse du serveur Wavelog,
indicatifs réels du log de l'utilisateur) n'est dans les fichiers **ni dans l'historique git**.
