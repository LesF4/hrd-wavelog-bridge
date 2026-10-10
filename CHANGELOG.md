# Journal des versions / Changelog

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
