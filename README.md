# HRD Logbook → Wavelog

[![Dernière version](https://img.shields.io/github/v/release/LesF4/hrd-wavelog-bridge?label=version&color=2e7d32)](https://github.com/LesF4/hrd-wavelog-bridge/releases/latest)
[![Téléchargements](https://img.shields.io/github/downloads/LesF4/hrd-wavelog-bridge/total?label=t%C3%A9l%C3%A9chargements&color=2e7d32)](https://github.com/LesF4/hrd-wavelog-bridge/releases)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-green)](LICENSE)

🇫🇷 Français · [🇬🇧 English](README.en.md)

**Envoie automatiquement dans ton [Wavelog](https://www.wavelog.org) chaque QSO enregistré dans HRD Logbook** (Ham Radio Deluxe).
Tu loggues dans HRD comme d'habitude, que ce soit à la main, depuis WSJT-X ou depuis JS8Call : le contact apparaît tout seul dans ton log web.

Créée par **F4MAJ / Jean-Bernard** pour la communauté [Les F4](https://github.com/LesF4).

![HRD Logbook → Wavelog : liste des QSO envoyés, voyants HRD et Wavelog](docs/img/app-fr.png)

## En bref

- **Pour qui ?** Les OM qui tiennent leur log dans **HRD Logbook** et veulent le retrouver dans leur **Wavelog**, hébergé chez eux ou en ligne.
- **Tous les modes :** phonie, CW, FT8, JS8… tout ce qui entre dans HRD part vers Wavelog.
- **Sans toucher à ton log :** c'est HRD qui envoie chaque nouveau QSO à l'app (sa fonction *QSO Forwarding*). L'app n'ouvre pas ton fichier de log, sauf si tu lui demandes d'envoyer tout l'historique.
- **Respect de la vie privée :** seules les informations du QSO partent vers Wavelog. L'adresse, l'e-mail et les notes de tes correspondants restent dans HRD.
- **Rien ne se perd :** si Internet est coupé, les QSO attendent et partent dès le retour de la connexion.
- **Pas de doublons :** Wavelog ignore les QSO qu'il a déjà.
- **Ton historique aussi :** un bouton envoie tout ton log HRD existant.
- **Bilingue** français / anglais, **gratuit et libre** (licence MIT).

## Téléchargement

Va dans les [**Releases**](https://github.com/LesF4/hrd-wavelog-bridge/releases/latest) et prends **`HRDtoWavelog-Setup-x.y.z.exe`**. C'est un installeur classique : menu Démarrer, icône sur le bureau, lancement avec Windows, désinstallation propre. Pas besoin d'être administrateur.

> **Premier lancement :** Windows peut afficher « Windows a protégé votre ordinateur », parce que l'application n'est pas signée. Clique sur **Informations complémentaires** puis **Exécuter quand même**. Le code source est entièrement visible ici.

## Installation pas à pas

### 1. Installer l'application

Lance `HRDtoWavelog-Setup-x.y.z.exe` et laisse cochées **Créer une icône sur le bureau** et **Lancer HRDtoWavelog au démarrage de Windows**.

### 2. Créer une clé API dans Wavelog

Dans ton navigateur, connecte-toi à ton Wavelog. Ouvre le **menu de ton compte** (en haut à droite), puis **API Keys**. Crée une clé avec les droits **Read & Write** et copie-la.

### 3. Activer l'envoi des QSO dans HRD Logbook

Dans HRD Logbook, menu **Tools → Configure → QSO Forwarding**, partie **envoi UDP** (*UDP Send*) :
- coche l'envoi des QSO par UDP ;
- adresse **`127.0.0.1`** (ou `localhost`), port **`12060`** ;
- **OK**.

> C'est cette fonction qui envoie chaque nouveau QSO à l'application. Elle est indépendante de la *réception* UDP utilisée par WSJT-X ou JS8Call : les deux peuvent être activées en même temps.

### 4. Régler l'application

Au premier lancement, la fenêtre **Réglages** s'ouvre :
- **Port UDP** : `12060`, le même que dans HRD.
- **Fichier du log** : trouvé tout seul. Il ne sert qu'au bouton *Envoyer tout le log HRD…*.
- **Adresse** : l'adresse de ton Wavelog, par exemple `https://wavelog.monsite.fr`.
- **Clé API** : colle la clé de l'étape 2.
- Clique sur **Tester et charger les stations**, choisis ta **station**, puis **Enregistrer**.

L'app te demande alors si tu veux **aussi envoyer les QSO déjà présents dans HRD**. Wavelog ignore ceux qu'il a déjà, tu peux donc répondre *Oui* sans risque de doublons.

### 5. Vérifier

Les **deux voyants en haut de la fenêtre doivent être verts**. Enregistre un QSO dans HRD : quelques secondes plus tard, il apparaît dans la liste ✔ et dans ton Wavelog.

> L'application doit être **lancée au moment où tu enregistres le QSO** : HRD ne l'envoie qu'une fois. C'est pourquoi le lancement avec Windows est recommandé. Si un jour des QSO ont été enregistrés pendant que l'app était fermée, le bouton *Envoyer tout le log HRD…* les rattrape (Wavelog ignore ceux qu'il a déjà).

## Utilisation

| Statut | Signification |
|---|---|
| ✔ **Envoyé à Wavelog** | Le QSO est dans ton Wavelog. |
| ✔ **Déjà dans Wavelog** | Wavelog l'avait déjà, rien n'a été ajouté. |
| ⏳ **En attente** | Wavelog injoignable (Internet coupé…) ou réglages incomplets : il partira tout seul. |
| ✖ **Refusé par Wavelog** | La raison est dans la colonne *Détail*. Corrige le QSO dans HRD si besoin, puis **Renvoyer la sélection**. |

- **Envoyer tout le log HRD…** : lit ton fichier de log HRD (en lecture seule) et envoie tout l'historique. Les QSO déjà présents dans Wavelog sont ignorés.
- La croix ✕ range l'application près de l'horloge sans l'arrêter. Clic droit sur l'icône → **Quitter**.
- **Dossier de sauvegarde** : le fichier `qsos_envoyes_wavelog.adi` garde une copie ADIF de tout ce qui a été envoyé.

## En cas de souci

| Problème | Solution |
|---|---|
| Voyant **HRD rouge** | Le port UDP est déjà utilisé par un autre programme. Choisis un autre port dans *Réglages* et mets le même dans HRD (*QSO Forwarding*). |
| Le voyant HRD est vert mais **aucun QSO n'arrive** | Vérifie dans HRD (*Tools → Configure → QSO Forwarding*) que l'**envoi** UDP est activé, vers `127.0.0.1`, sur le même port que l'app. |
| *Envoyer tout le log HRD…* ne trouve pas le log | Dans *Réglages*, choisis ton fichier `.hrdsql` (en général `Documents\Ham Radio Deluxe\HRD Logbook\`). Seuls les logbooks **Local/SQLite** sont pris en charge, c'est le format par défaut des versions récentes de HRD. |
| Voyant **Wavelog rouge** | Vérifie ta connexion Internet et l'adresse de Wavelog. |
| « clé API invalide » / « lecture seule » | Crée une clé **Read & Write** dans Wavelog et colle-la dans *Réglages*. |
| Un QSO modifié dans HRD après l'envoi | L'app n'envoie que les **nouveaux** QSO. Une correction faite ensuite dans HRD n'est pas répercutée : corrige aussi dans Wavelog. |
| Antivirus qui bloque | L'app n'est pas signée et envoie des données sur Internet, ce qui peut inquiéter certains antivirus (Bitdefender notamment). Ajoute une exception pour `HRDtoWavelog.exe` et autorise-le dans le pare-feu de l'antivirus. |

Une question, un bug, une idée ? Ouvre une [**issue**](https://github.com/LesF4/hrd-wavelog-bridge/issues).

## Où sont mes données ?

Dans `%APPDATA%\HRDtoWavelog\` :
- `config.json` : tes réglages, dont ta clé API, qui reste uniquement sur ton PC ;
- `history.json` : la liste affichée dans la fenêtre ;
- `qsos_envoyes_wavelog.adi` : la copie ADIF des QSO envoyés.

## Testé avec

- HRD Logbook 6.9
- Wavelog auto-hébergé
- Windows 11

## Comment ça marche (pour les curieux)

```
HRD Logbook ──(QSO Forwarding : UDP 12060, XML « contactinfo »)──▶ HRDtoWavelog ──(API Wavelog, HTTPS)──▶ Wavelog
```

L'app écoute uniquement sur la machine locale (`127.0.0.1`), convertit chaque QSO reçu en ADIF et l'envoie à l'API `index.php/api/qso` de Wavelog. Le code est en Python (interface tkinter). Pour lancer depuis les sources, lancer les tests ou construire l'installeur : voir [`packaging/README.md`](packaging/README.md).

## Voir aussi

[**JS8Call → HRD Logbook**](https://github.com/LesF4/js8-hrd-bridge) envoie tes QSO JS8Call dans HRD. Associé à cette application, chaque QSO JS8 arrive dans HRD puis dans Wavelog, sans rien faire.

## Licence

[MIT](LICENSE) © 2026 **F4MAJ / Jean-Bernard**. Tu peux librement utiliser, copier, modifier et partager cette application, à condition de conserver la mention de copyright.

73 de F4MAJ !
