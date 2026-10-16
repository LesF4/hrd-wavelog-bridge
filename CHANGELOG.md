# Journal des versions / Changelog

## 1.3.0 — 2026-10-16

- **Radio en direct dans Wavelog, via HRD :** l'app lit la radio pilotée par HRD Rig Control (nom, fréquence, mode, VFO B) et l'envoie à Wavelog (API `radio`). La radio apparaît « en ligne » dans Wavelog, qui pré-remplit fréquence, bande et mode à la saisie d'un QSO, comme si elle y était branchée. HRD garde le contrôle de la radio : rien à brancher en plus.
- **Clic sur un spot du cluster dans Wavelog → la radio change de fréquence :** l'app reçoit la demande (port local 54321, comme WaveLogGate) et la transmet à HRD. Seules la fréquence est réglée ; l'émission (PTT) n'est jamais commandée. Les fréquences absurdes sont refusées.
- Modes numériques : quand la radio est en DATA-U / DATA-L, l'app envoie à Wavelog un mode numérique et non « USB » (pas de faux QSO phonie) : par défaut **JS8 si JS8Call est ouvert, sinon FT8** ; réglable (FT8, FT4, JS8, PSK31, RTTY, ou rien). Le VFO B n'est plus présenté comme un « split ».
- Nouveau voyant « Radio » dans la fenêtre, et deux options dans les Réglages (envoi de la radio, QSY depuis Wavelog), activées par défaut.

## 1.2.4 — 2026-10-11

- **Réglages retrouvés automatiquement :** si l'app a été lancée un jour depuis une application Windows « empaquetée » (par exemple un assistant comme l'app Claude), Windows a pu ranger ses réglages dans un dossier séparé (`%LOCALAPPDATA%\Packages\…\LocalCache\Roaming\HRDtoWavelog`). Au démarrage, si l'app ne trouve pas de réglages, elle les récupère là, avec l'historique, et les enregistre au bon endroit. Plus besoin de tout ressaisir.
- **Démarrage avec Windows plus fiable :** s'il est coché dans les Réglages mais que Windows ne l'a plus, l'app le remet en place toute seule.

## 1.2.3 — 2026-10-10

- **Les réglages ne peuvent plus « disparaître » au démarrage :** si le fichier de réglages est momentanément illisible (bloqué par l'antivirus juste après l'allumage du PC, par exemple), l'app réessaie pendant quelques secondes, puis utilise sa **copie de secours** (`config.json.bak`, mise à jour à chaque enregistrement). Elle n'ouvre plus jamais des Réglages vides par-dessus une configuration existante.
- Même protection pour l'historique : s'il reste illisible, l'app affiche un message et s'arrête sans rien modifier, au lieu de repartir d'une liste vide.

## 1.2.2 — 2026-10-10

- **La fenêtre ne peut plus se figer à cause de Windows ou d'Internet :** les notifications et l'icône près de l'horloge, ainsi que le test de connexion des Réglages, se font en arrière-plan. (Une fenêtre figée avait été fermée par Windows en plein trafic.)
- **Rattrapage automatique au démarrage :** les QSO enregistrés dans HRD pendant que l'app était fermée sont retrouvés et envoyés à Wavelog, sans rien faire.
- **Diagnostic :** si la fenêtre ne répond plus pendant plus de 8 secondes, l'app note l'état de chacune de ses tâches dans `%APPDATA%\HRDtoWavelog\diagnostic.log`, pour trouver la cause.

## 1.2.1 — 2026-10-10

- Correctif : la 1.2.0 pouvait se fermer au démarrage si l'historique contenait deux fois le même QSO (doublon dans un log). L'historique est maintenant réparé automatiquement au démarrage, et la liste ne peut plus planter sur une ligne en double.

## 1.2.0 — 2026-10-10

- **Synchronisation dans les deux sens :** les QSO ajoutés dans Wavelog ailleurs (radio-club, portable, concours…) sont récupérés toutes les 2 minutes (API `get_contacts_adif`) et ajoutés dans HRD Logbook par sa réception UDP (port 2333), comme pour WSJT-X. Stations Wavelog suivies au choix.
- **Pas de doublons :** un QSO venu de HRD n'y revient pas, l'« écho » renvoyé par HRD est ignoré, et un QSO déjà présent dans HRD (import manuel…) n'y est pas ajouté une deuxième fois.
- **Nouveau bouton « Comparer les deux logs… »** : affiche, date par date, les QSO manquants de chaque côté et les ajoute en un clic. Il remplace « Envoyer tout le log HRD… ». Rien n'est jamais supprimé.
- Nouvelle colonne « Sens » dans la liste (HRD → Wavelog / Wavelog → HRD).
- Si HRD est fermé, les QSO venus de Wavelog attendent et sont ajoutés dès son ouverture.
- **Ajout dans HRD un QSO à la fois, avec confirmation :** l'app attend que HRD ait vraiment enregistré chaque QSO avant d'envoyer le suivant (HRD peut se fermer brutalement si on lui en envoie trop vite). Un QSO déjà présent n'est pas renvoyé, et si HRD se ferme, l'envoi s'arrête et le QSO concerné est signalé.
- **Barre de progression** pendant l'envoi de plusieurs QSO, dans les deux sens.
- Correctif : deux QSO identiques (doublon dans un log) ne se mélangent plus dans la liste.

## 1.1.0 — 2026-10-09

- **Nouveau fonctionnement :** l'app reçoit les QSO que HRD Logbook lui envoie (*QSO Forwarding*, envoi UDP, port 12060 par défaut) au lieu de surveiller le fichier du log. Elle n'ouvre plus le log HRD, sauf pour « Envoyer tout le log HRD… ». Ce comportement est aussi beaucoup moins susceptible d'inquiéter les antivirus.
- **Vie privée :** quand le log HRD est lu (envoi de tout l'historique), seuls les champs du QSO sont transmis. L'adresse, l'e-mail, les coordonnées et les notes des correspondants ne sont plus envoyés.
- Les QSO modifiés ou supprimés dans HRD sont signalés dans le journal de l'app (non répercutés dans Wavelog).
- Correction : une erreur d'enregistrement des réglages n'est plus présentée comme une erreur de lecture du log HRD.
- Seul l'installeur est publié (la version « un seul fichier » se décompressait dans le dossier temporaire à chaque lancement).

## 1.0.0 — 2026-10-09

Première version / First release.

- Envoi automatique vers Wavelog (API `api/qso`) de chaque nouveau QSO enregistré dans HRD Logbook.
- Lecture du log HRD (Local/SQLite) en lecture seule, détection des nouveaux QSO toutes les 10 s.
- File d'attente si Wavelog est injoignable, doublons reconnus, sauvegarde ADIF des QSO envoyés.
- Envoi optionnel de tout l'historique HRD.
- Réglages guidés : test de la clé API, choix de la station Wavelog.
- Fenêtre avec voyants HRD / Wavelog, renvoi manuel, icône dans la zone de notification.
- Démarrage automatique avec Windows (optionnel), interface français / anglais.
