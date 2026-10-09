# Journal des versions / Changelog

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
