"""Textes de l'interface en français et en anglais."""

import sys

LANGUAGES = ("fr", "en")

TEXTS = {
    "fr": {
        "status_sent": "✔ Envoyé à Wavelog",
        "status_dupe": "✔ Déjà dans Wavelog",
        "status_pending": "⏳ En attente",
        "status_error": "✖ Refusé par Wavelog",
        "hrd_listen": "● HRD Logbook : à l'écoute (UDP {port})",
        "hrd_busy": "● HRD Logbook : port UDP occupé",
        "wl_ok": "● Wavelog : connecté",
        "wl_bad": "● Wavelog : injoignable",
        "wl_unset": "● Wavelog : à configurer",
        "btn_settings": "Réglages…",
        "btn_about": "À propos",
        "btn_resend": "Renvoyer la sélection",
        "btn_history": "Envoyer tout le log HRD…",
        "btn_open_folder": "Dossier de sauvegarde",
        "btn_quit": "Quitter",
        "col_utc": "Date / UTC", "col_call": "Indicatif", "col_band": "Bande", "col_mode": "Mode",
        "col_freq": "Fréquence", "col_status": "Statut", "col_msg": "Détail",
        "log_start": "Démarrage. En attente des QSO envoyés par HRD Logbook (UDP {port}).",
        "log_listen_error": "Impossible d'écouter le port UDP {port} ({err}). Un autre programme l'utilise-t-il ?",
        "log_replace": "QSO {call} modifié dans HRD : la modification n'est pas répercutée dans Wavelog.",
        "log_delete": "QSO {call} supprimé dans HRD : il reste dans Wavelog.",
        "log_no_db": "Fichier du log HRD introuvable : choisis-le dans les Réglages.",
        "log_save_error": "Impossible d'enregistrer les données de l'app : {err}",
        "log_internal": "Erreur interne : {err}",
        "log_new": "Nouveau QSO dans HRD : {call} ({when})",
        "log_sent": "→ Wavelog : {call} envoyé.",
        "log_dupe": "{call} était déjà dans Wavelog.",
        "log_error": "Wavelog a refusé {call} : {err}",
        "log_offline": "Wavelog injoignable ({err}). {n} QSO en attente, nouvel essai automatique.",
        "log_hrd_error": "Lecture du fichier du log HRD impossible : {err}",
        "log_need_setup": "Ouvre les Réglages pour renseigner l'adresse de Wavelog, la clé API et la station.",
        "log_settings_saved": "Réglages enregistrés.",
        "log_history": "{n} QSO du log HRD mis en file d'envoi. Wavelog ignore ceux qu'il a déjà.",
        "notify_sent": "QSO avec {call} envoyé à Wavelog",
        "resend_none": "Sélectionne d'abord un ou plusieurs QSO dans la liste.",
        "history_confirm": "Envoyer les {n} QSO de ton log HRD vers Wavelog ?\n\n"
                           "Wavelog ignore automatiquement les QSO qu'il a déjà. "
                           "Cela peut prendre plusieurs minutes, l'app reste utilisable pendant l'envoi.",
        "first_setup_history": "Réglages OK !\n\nTon log HRD contient déjà {n} QSO.\n"
                               "Veux-tu les envoyer aussi vers Wavelog ?\n\n"
                               "• Oui : tout le log est envoyé (Wavelog ignore ceux qu'il a déjà)\n"
                               "• Non : seuls les prochains QSO seront envoyés",
        "settings_title": "Réglages",
        "s_hrd": "HRD Logbook",
        "s_udp_port": "Port UDP",
        "s_udp_hint": "HRD Logbook → Tools → Configure → QSO Forwarding → envoi UDP activé, 127.0.0.1, ce port",
        "s_logbook": "Fichier du log",
        "s_logbook_hint": "Utilisé seulement pour « Envoyer tout le log HRD… »",
        "s_browse": "Parcourir…",
        "s_wavelog": "Wavelog",
        "s_url": "Adresse",
        "s_url_hint": "ex. https://wavelog.monsite.fr",
        "s_key": "Clé API",
        "s_key_hint": "Wavelog → menu de ton compte → API Keys → créer une clé « Read & Write »",
        "s_station": "Station",
        "s_load": "Tester et charger les stations",
        "s_loaded": "Connexion OK ({rights}) — choisis ta station.",
        "s_readonly": "Cette clé est en lecture seule : crée une clé « Read & Write » dans Wavelog.",
        "s_options": "Options",
        "s_language": "Langue",
        "lang_auto": "Automatique (langue de Windows)",
        "s_autostart": "Lancer automatiquement au démarrage de Windows",
        "s_minimized": "Démarrer réduit",
        "s_tray": "La croix ✕ réduit dans la zone de notification (au lieu de quitter)",
        "s_save": "Enregistrer",
        "s_cancel": "Annuler",
        "err_missing": "Renseigne l'adresse, la clé API et choisis une station.",
        "err_port": "Le port UDP doit être un nombre.",
        "err_autostart": "Démarrage automatique impossible : {err}",
        "err_not_json": "réponse inattendue du serveur (adresse de Wavelog correcte ?)",
        "err_bad_key": "clé API invalide",
        "tray_open": "Ouvrir",
        "tray_quit": "Quitter",
        "tray_hint": "L'app continue de tourner ici. Clic droit > Quitter pour l'arrêter.",
        "already_running": "L'application est déjà lancée "
                           "(regarde près de l'horloge, dans la zone de notification).",
        "about_text": "Envoie automatiquement les QSO de HRD Logbook vers Wavelog.\n\n"
                      "Version {version}\n© 2026 F4MAJ / Jean-Bernard — licence MIT\n\n{url}",
        "backup_header": "QSO de HRD Logbook envoyés à Wavelog",
    },
    "en": {
        "status_sent": "✔ Sent to Wavelog",
        "status_dupe": "✔ Already in Wavelog",
        "status_pending": "⏳ Waiting",
        "status_error": "✖ Rejected by Wavelog",
        "hrd_listen": "● HRD Logbook: listening (UDP {port})",
        "hrd_busy": "● HRD Logbook: UDP port busy",
        "wl_ok": "● Wavelog: connected",
        "wl_bad": "● Wavelog: unreachable",
        "wl_unset": "● Wavelog: needs setup",
        "btn_settings": "Settings…",
        "btn_about": "About",
        "btn_resend": "Resend selection",
        "btn_history": "Send the whole HRD log…",
        "btn_open_folder": "Backup folder",
        "btn_quit": "Quit",
        "col_utc": "Date / UTC", "col_call": "Call", "col_band": "Band", "col_mode": "Mode",
        "col_freq": "Frequency", "col_status": "Status", "col_msg": "Details",
        "log_start": "Started. Waiting for QSOs sent by HRD Logbook (UDP {port}).",
        "log_listen_error": "Cannot listen on UDP port {port} ({err}). Is another program using it?",
        "log_replace": "QSO {call} edited in HRD: the change is not carried over to Wavelog.",
        "log_delete": "QSO {call} deleted in HRD: it stays in Wavelog.",
        "log_no_db": "HRD log file not found: pick it in Settings.",
        "log_save_error": "Cannot save the app data: {err}",
        "log_internal": "Internal error: {err}",
        "log_new": "New QSO in HRD: {call} ({when})",
        "log_sent": "→ Wavelog: {call} sent.",
        "log_dupe": "{call} was already in Wavelog.",
        "log_error": "Wavelog rejected {call}: {err}",
        "log_offline": "Cannot reach Wavelog ({err}). {n} QSO(s) waiting, will retry automatically.",
        "log_hrd_error": "Cannot read the HRD log file: {err}",
        "log_need_setup": "Open Settings to enter the Wavelog address, API key and station.",
        "log_settings_saved": "Settings saved.",
        "log_history": "{n} QSOs from the HRD log queued. Wavelog skips those it already has.",
        "notify_sent": "QSO with {call} sent to Wavelog",
        "resend_none": "First select one or more QSOs in the list.",
        "history_confirm": "Send the {n} QSOs of your HRD log to Wavelog?\n\n"
                           "Wavelog automatically skips QSOs it already has. "
                           "This can take several minutes; the app stays usable meanwhile.",
        "first_setup_history": "Settings OK!\n\nYour HRD log already holds {n} QSOs.\n"
                               "Do you want to send them to Wavelog too?\n\n"
                               "• Yes: the whole log is sent (Wavelog skips those it already has)\n"
                               "• No: only upcoming QSOs will be sent",
        "settings_title": "Settings",
        "s_hrd": "HRD Logbook",
        "s_udp_port": "UDP port",
        "s_udp_hint": "HRD Logbook → Tools → Configure → QSO Forwarding → UDP send on, 127.0.0.1, this port",
        "s_logbook": "Log file",
        "s_logbook_hint": "Only used for \"Send the whole HRD log…\"",
        "s_browse": "Browse…",
        "s_wavelog": "Wavelog",
        "s_url": "Address",
        "s_url_hint": "e.g. https://wavelog.mysite.org",
        "s_key": "API key",
        "s_key_hint": "Wavelog → your account menu → API Keys → create a \"Read & Write\" key",
        "s_station": "Station",
        "s_load": "Test and load stations",
        "s_loaded": "Connection OK ({rights}) — pick your station.",
        "s_readonly": "This key is read-only: create a \"Read & Write\" key in Wavelog.",
        "s_options": "Options",
        "s_language": "Language",
        "lang_auto": "Automatic (Windows language)",
        "s_autostart": "Start automatically with Windows",
        "s_minimized": "Start minimized",
        "s_tray": "The ✕ button minimizes to the notification area (instead of quitting)",
        "s_save": "Save",
        "s_cancel": "Cancel",
        "err_missing": "Enter the address and API key, and pick a station.",
        "err_port": "The UDP port must be a number.",
        "err_autostart": "Cannot set up automatic start: {err}",
        "err_not_json": "unexpected server reply (is the Wavelog address right?)",
        "err_bad_key": "invalid API key",
        "tray_open": "Open",
        "tray_quit": "Quit",
        "tray_hint": "The app keeps running here. Right-click > Quit to stop it.",
        "already_running": "The application is already running "
                           "(look near the clock, in the notification area).",
        "about_text": "Automatically sends HRD Logbook QSOs to Wavelog.\n\n"
                      "Version {version}\n© 2026 F4MAJ / Jean-Bernard — MIT licence\n\n{url}",
        "backup_header": "HRD Logbook QSOs sent to Wavelog",
    },
}

_lang = "en"


def system_language():
    """'fr' si Windows est en français, sinon 'en'."""
    if sys.platform == "win32":
        try:
            import ctypes
            return "fr" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x0C else "en"
        except (AttributeError, OSError):
            pass
    import locale
    return "fr" if (locale.getlocale()[0] or "").lower().startswith("fr") else "en"


def set_language(choice):
    global _lang
    _lang = choice if choice in LANGUAGES else system_language()


def t(key, **kwargs):
    text = TEXTS[_lang].get(key) or TEXTS["en"][key]
    return text.format(**kwargs) if kwargs else text
