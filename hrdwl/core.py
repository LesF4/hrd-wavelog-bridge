"""Logique du pont HRD Logbook <-> Wavelog (sans interface graphique).

HRD -> Wavelog : HRD Logbook envoie chaque nouveau QSO en UDP (« QSO Forwarding », envoi UDP,
format XML <contactinfo> type N1MM) : l'app écoute ce port sur la machine locale, convertit le
QSO en ADIF et l'envoie à Wavelog par son API (POST index.php/api/qso, clé API en écriture).

Wavelog -> HRD : l'app demande régulièrement à Wavelog les QSO ajoutés depuis la dernière fois
(POST index.php/api/get_contacts_adif) et envoie ceux qui ne viennent pas de HRD à la réception
UDP de HRD (ADIF, port 2333 par défaut), comme le font WSJT-X ou JS8Call.

Le fichier du log HRD (.hrdsql) n'est lu QUE si l'utilisateur demande « Envoyer tout le log »,
en lecture seule, et seulement les champs du QSO (pas d'adresse, e-mail, notes…).
"""

import glob
import json
import os
import queue
import re
import shutil
import socket
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from .i18n import t

APP_NAME = "HRDtoWavelog"
APP_TITLE = "HRD Logbook → Wavelog"
APP_VERSION = "1.2.0"
APP_URL = "https://github.com/LesF4/hrd-wavelog-bridge"
TABLE = "TABLE_HRD_CONTACTS_V07"

DEFAULT_CONFIG = {
    "udp_port": 12060,        # port de l'envoi UDP de HRD (QSO Forwarding)
    "hrd_in_port": 2333,      # port de la réception UDP de HRD (QSO Forwarding), pour Wavelog -> HRD
    "download_enabled": True, # copier dans HRD les QSO ajoutés dans Wavelog
    "download_stations": [],  # stations Wavelog à suivre (vide = la station configurée)
    "wl_last_id": None,       # dernier identifiant Wavelog déjà vu (None = partir de maintenant)
    "hrd_db": "",             # fichier .hrdsql, utilisé seulement pour « Envoyer tout le log »
    "wavelog_url": "",        # ex. https://wavelog.example.org
    "api_key": "",
    "station_id": "",
    "start_minimized": False,
    "close_to_tray": True,
    "language": "auto",
}

BANDS = [
    ("2190m", 0.1357, 0.1378), ("630m", 0.472, 0.479), ("160m", 1.8, 2.0), ("80m", 3.5, 4.0),
    ("60m", 5.06, 5.45), ("40m", 7.0, 7.3), ("30m", 10.1, 10.15), ("20m", 14.0, 14.35),
    ("17m", 18.068, 18.168), ("15m", 21.0, 21.45), ("12m", 24.89, 24.99), ("10m", 28.0, 29.7),
    ("6m", 50.0, 54.0), ("4m", 70.0, 71.0), ("2m", 144.0, 148.0), ("1.25m", 222.0, 225.0),
    ("70cm", 420.0, 450.0), ("23cm", 1240.0, 1300.0), ("13cm", 2300.0, 2450.0),
]


# --------------------------------------------------------------------------- dossiers / config

def data_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(os.path.join(data_dir(), "config.json"), encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULT_CONFIG})
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    path = os.path.join(data_dir(), "config.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)


# --------------------------------------------------------------------------- QSO reçus de HRD (UDP)

def band_for_mhz(mhz):
    for name, lo, hi in BANDS:
        if lo <= mhz <= hi:
            return name
    return ""


def _freq_mhz(raw, band_hint):
    """Fréquence HRD/N1MM -> MHz. L'unité varie (Hz ou dizaines de Hz) : on choisit celle
    qui tombe dans la bande annoncée (<band> en MHz)."""
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0:
        return None
    candidates = [value / 1e6, value / 1e5, value / 1e3, value]
    try:
        hint = float(band_hint)
    except ValueError:
        hint = 0
    if hint:
        for mhz in candidates:
            if band_for_mhz(mhz) and abs(mhz - hint) <= max(1.0, hint * 0.2):
                return mhz
    for mhz in candidates:
        if band_for_mhz(mhz):
            return mhz
    return None


_TS_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?")


def contact_from_xml(data):
    """Paquet UDP de HRD -> (type, identifiant, champs ADIF). Lève ValueError si illisible."""
    try:
        root = ET.fromstring(data.decode("utf-8", "replace").strip().lstrip("﻿"))
    except ET.ParseError as e:
        raise ValueError(e)

    def g(tag):
        return (root.findtext(tag) or "").strip()

    f = {}
    m = _TS_RE.match(g("timestamp"))
    if m:
        f["QSO_DATE"] = m.group(1) + m.group(2) + m.group(3)
        f["TIME_ON"] = m.group(4) + m.group(5) + (m.group(6) or "00")
    f["CALL"] = g("call").upper()
    mhz = _freq_mhz(g("txfreq") or g("rxfreq"), g("band"))
    if mhz:
        f["FREQ"] = "%.6f" % mhz
        f["BAND"] = band_for_mhz(mhz)
    for adif, tag in (("MODE", "mode"), ("SUBMODE", "submode"), ("RST_SENT", "snt"), ("RST_RCVD", "rcv"),
                      ("GRIDSQUARE", "gridsquare"), ("NAME", "name"), ("QTH", "qth"), ("COMMENT", "comment"),
                      ("STATION_CALLSIGN", "mycall"), ("OPERATOR", "operator"), ("CONTEST_ID", "contestname"),
                      ("SRX_STRING", "exchange1")):
        if g(tag):
            f[adif] = g(tag)
    for adif, tag in (("TX_PWR", "power"), ("SRX", "rcvnr"), ("STX", "sntnr")):
        if g(tag) not in ("", "0"):
            f[adif] = g(tag)
    f = {k: v for k, v in f.items() if v}
    ident = g("ID") or "%s|%s|%s|%s" % (f.get("CALL"), f.get("QSO_DATE"), f.get("TIME_ON"), f.get("BAND"))
    return root.tag.lower(), ident, f


# --------------------------------------------------------------------------- log HRD (sur demande)

def find_hrd_logbooks():
    """Logbooks déclarés dans HRD : liste de (titre, type, chemin)."""
    base = os.path.join(os.environ.get("APPDATA", ""), "HRDLLC", "HRD Logbook")
    files = sorted(glob.glob(os.path.join(base, "LogbookDatabases*.xml")),
                   key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)) or 0))
    if not files:
        return []
    try:
        root = ET.parse(files[-1]).getroot()
    except (ET.ParseError, OSError):
        return []
    return [(db.get("Title", ""), db.get("DatabaseType", ""), db.get("Database", ""))
            for db in root.iter("Database")]


def default_hrd_db():
    for _title, dbtype, path in find_hrd_logbooks():
        if "sqlite" in dbtype.lower() and os.path.exists(path):
            return path
    return ""


# Champs du QSO lus dans le log HRD : uniquement le contact, rien de personnel sur le correspondant
# (pas d'adresse, d'e-mail, de coordonnées ni de notes).
_DB_FIELDS = [
    "CALL", "QSO_DATE", "TIME_ON", "QSO_DATE_OFF", "TIME_OFF", "BAND", "BAND_RX", "FREQ", "FREQ_RX",
    "MODE", "SUBMODE", "RST_SENT", "RST_RCVD", "GRIDSQUARE", "NAME", "QTH", "COMMENT", "TX_PWR",
    "OPERATOR", "STATION_CALLSIGN", "MY_GRIDSQUARE", "PROP_MODE", "SAT_NAME", "SAT_MODE",
    "CONTEST_ID", "SRX", "STX", "SRX_STRING", "STX_STRING", "IOTA", "SOTA_REF", "POTA_REF", "WWFF_REF",
    "SIG", "SIG_INFO", "MY_SOTA_REF", "MY_POTA_REF", "MY_WWFF_REF", "MY_SIG", "MY_SIG_INFO",
]
_FREQ_COLS = {"FREQ", "FREQ_RX"}
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_TIME_RE = re.compile(r"^(\d{2}):(\d{2})(?::(\d{2}))?")


class HRDReader:
    """Lecture seule du log HRD (SQLite), sur demande de l'utilisateur. Ne modifie jamais la base."""

    def __init__(self, path):
        self.path = path

    def _query(self, sql, args=()):
        uri = "file:%s?mode=ro" % urllib.request.pathname2url(os.path.abspath(self.path))
        try:
            con = sqlite3.connect(uri, uri=True, timeout=5)
        except sqlite3.Error:
            return self._query_copy(sql, args)
        try:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute(sql, args)]
        except sqlite3.OperationalError:
            return self._query_copy(sql, args)
        finally:
            con.close()

    def _query_copy(self, sql, args):
        # Repli : HRD fermé en mode WAL sans fichier -shm -> on lit une copie temporaire.
        tmpdir = tempfile.mkdtemp(prefix="hrdwl_")
        try:
            dst = os.path.join(tmpdir, "log.hrdsql")
            shutil.copy2(self.path, dst)
            for ext in ("-wal", "-shm"):
                if os.path.exists(self.path + ext):
                    shutil.copy2(self.path + ext, dst + ext)
            con = sqlite3.connect(dst, timeout=5)
            try:
                con.row_factory = sqlite3.Row
                return [dict(r) for r in con.execute(sql, args)]
            finally:
                con.close()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _columns(self):
        names = {r["name"] for r in self._query("PRAGMA table_info(%s)" % TABLE)}
        return ["COL_PRIMARY_KEY"] + ["COL_" + n for n in _DB_FIELDS if "COL_" + n in names]

    def count(self):
        return self._query("SELECT COUNT(*) AS n FROM %s" % TABLE)[0]["n"]

    def all_rows(self):
        return self._query("SELECT %s FROM %s ORDER BY COL_PRIMARY_KEY" % (", ".join(self._columns()), TABLE))


def _fmt_number(v):
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else ("%.6f" % v).rstrip("0").rstrip(".")
    return str(v)


def row_to_fields(row):
    """Ligne du log HRD -> dict de champs ADIF (uniquement les champs de _DB_FIELDS)."""
    f = {}
    for name in _DB_FIELDS:
        v = row.get("COL_" + name)
        if v is None:
            continue
        if isinstance(v, (int, float)):
            if v == 0:
                continue
            v = "%.6f" % (v / 1e6) if name in _FREQ_COLS else _fmt_number(v)
        else:
            v = str(v).strip()
            if not v:
                continue
            if name in ("QSO_DATE", "QSO_DATE_OFF"):
                m = _DATE_RE.match(v)
                if not m:
                    continue
                v = "".join(m.groups())
            elif name in ("TIME_ON", "TIME_OFF"):
                m = _TIME_RE.match(v)
                if not m:
                    continue
                v = m.group(1) + m.group(2) + (m.group(3) or "00")
        f[name] = v
    if "BAND" in f:
        f["BAND"] = f["BAND"].lower()
    return f


# --------------------------------------------------------------------------- ADIF

def build_adif_record(fields):
    return "".join("<%s:%d>%s " % (k.lower(), len(v), v) for k, v in fields.items()) + "<eor>"


def qso_label(f):
    d, tm = f.get("QSO_DATE", ""), f.get("TIME_ON", "")
    when = "%s-%s-%s %s:%s" % (d[0:4], d[4:6], d[6:8], tm[0:2], tm[2:4]) if len(d) == 8 else ""
    return when, f.get("CALL", "")


def append_backup(fields):
    path = os.path.join(data_dir(), "qsos_envoyes_wavelog.adi")
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as fh:
        if new:
            fh.write(t("backup_header") + "\n<adif_ver:5>3.1.4 <programid:%d>%s <eoh>\n"
                     % (len(APP_NAME), APP_NAME))
        fh.write(build_adif_record(fields) + "\n")


# --------------------------------------------------------------------------- Wavelog

class WavelogError(Exception):
    """Wavelog a répondu mais refuse (clé, station, QSO invalide…)."""


class WavelogOffline(WavelogError):
    """Wavelog injoignable (Internet coupé, serveur arrêté…) : on réessaiera."""


def _base(url):
    url = url.strip().rstrip("/")
    for suffix in ("/index.php/logbook", "/logbook", "/index.php"):
        if url.lower().endswith(suffix):
            url = url[: -len(suffix)]
    return url + "/index.php/api/"


def is_configured(cfg):
    return bool(cfg["wavelog_url"].strip() and cfg["api_key"].strip() and str(cfg["station_id"]).strip())


def _request(url, payload=None, timeout=20, raw=False):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "%s/%s" % (APP_NAME, APP_VERSION)})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:  # Wavelog répond 400/401 avec un JSON explicatif
        if e.code >= 500:  # serveur en panne / redémarrage : on réessaiera
            raise WavelogOffline("HTTP %s" % e.code)
        body = e.read().decode("utf-8", "replace")
        if not body.strip().startswith(("{", "[")):
            raise WavelogError("HTTP %s" % e.code)
    except (urllib.error.URLError, OSError) as e:
        raise WavelogOffline(str(getattr(e, "reason", e)))
    if raw:
        return body
    try:
        return json.loads(body)
    except ValueError:
        raise WavelogError(t("err_not_json"))


def check_key(url, key):
    """Retourne les droits de la clé ('rw' attendu) ou lève WavelogError."""
    # Cette route de Wavelog répond en XML : <auth><status>Valid</status><rights>rw</rights></auth>
    body = _request(_base(url) + "auth/" + key.strip(), raw=True)
    try:
        root = ET.fromstring(body.strip())
    except ET.ParseError:
        raise WavelogError(t("err_not_json"))
    if (root.findtext("status") or "").lower() != "valid":
        raise WavelogError(t("err_bad_key"))
    return root.findtext("rights") or ""


def station_profiles(url, key):
    res = _request(_base(url) + "station_info/" + key.strip())
    if isinstance(res, dict):
        raise WavelogError(res.get("reason") or t("err_bad_key"))
    return [(str(s.get("station_id")), "%s — %s (%s)" % (s.get("station_profile_name", ""),
                                                         s.get("station_callsign", ""),
                                                         s.get("station_gridsquare", "")),
             str(s.get("station_active")) == "1") for s in res]


def upload_qso(url, key, station_id, fields):
    """Envoie un QSO. Retourne 'sent' ou 'dupe' ; lève WavelogError sinon."""
    res = _request(_base(url) + "qso", {"key": key.strip(), "station_profile_id": str(station_id),
                                        "type": "adif", "string": build_adif_record(fields)})
    status = res.get("status")
    if status == "created":
        return "sent"
    text = " ".join(str(m) for m in res.get("messages") or []) + " " + str(res.get("reason", ""))
    if any(w in text.lower() for w in ("dupe", "duplicate", "doublon")):  # message traduit par Wavelog
        return "dupe"
    raise WavelogError(re.sub(r"<[^>]+>", " ", text).strip() or str(status))


def fetch_wavelog(url, key, station_ids, from_id):
    """QSO de Wavelog dont l'identifiant est > from_id. Retourne (liste de champs, dernier identifiant)."""
    res = _request(_base(url) + "get_contacts_adif",
                   {"key": key.strip(), "station_id": [int(s) for s in station_ids], "fetchfromid": int(from_id)},
                   timeout=180)
    if res.get("status") != "successful":
        raise WavelogError(res.get("reason") or res.get("message") or str(res.get("status")))
    return parse_adif(res.get("adif") or ""), int(res.get("lastfetchedid") or from_id)


# --------------------------------------------------------------------------- HRD : réception UDP (Wavelog -> HRD)

_ADIF_TAG = re.compile(r"<([A-Za-z0-9_]+):(\d+)(?::[A-Za-z])?>")


def parse_adif(text):
    """Texte ADIF -> liste de dict (clés en majuscules), en-tête ignoré."""
    low = text.lower()
    if "<eoh>" in low:
        text = text[low.find("<eoh>") + 5:]
    out = []
    for rec in re.split(r"(?i)<eor>", text):
        f, pos = {}, 0
        while True:
            m = _ADIF_TAG.search(rec, pos)
            if not m:
                break
            n = int(m.group(2))
            f[m.group(1).upper()] = rec[m.end():m.end() + n]
            pos = m.end() + n
        if f.get("CALL"):
            out.append(f)
    return out


def fields_for_hrd(f):
    """QSO venant de Wavelog -> champs ADIF envoyés à HRD (champs du QSO uniquement)."""
    out = {k: str(f[k]).strip() for k in _DB_FIELDS if str(f.get(k, "")).strip()}
    if "BAND" in out:
        out["BAND"] = out["BAND"].lower()
    if "CALL" in out:
        out["CALL"] = out["CALL"].upper()
    return out


def hrd_listening(port):
    """Vrai si HRD (ou un autre programme) écoute déjà ce port UDP sur la machine locale."""
    for addr in ("0.0.0.0", "127.0.0.1"):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((addr, int(port)))
        except OSError:
            return True
        finally:
            s.close()
    return False


def send_to_hrd(fields, port):
    payload = build_adif_record(fields).encode("cp1252", errors="replace")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(payload, ("127.0.0.1", int(port)))


# --------------------------------------------------------------------------- comparaison

MATCH_MINUTES = 15  # même règle que Wavelog pour les doublons


def qso_time(f):
    d, tm = f.get("QSO_DATE", ""), (f.get("TIME_ON", "") + "000000")[:6]
    try:
        return datetime.strptime(d + tm, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def qso_sig(f):
    return "%s|%s|%s|%s" % (f.get("CALL", "").upper(), (f.get("BAND") or "").lower(),
                            f.get("QSO_DATE", ""), f.get("TIME_ON", "")[:4])


class QsoIndex:
    """Retrouve un QSO « identique » (même indicatif, même bande, à 15 minutes près).
    Le mode n'est pas comparé : HRD et Wavelog ne l'écrivent pas pareil (PSK31 / PSK+PSK31…)."""

    def __init__(self, qsos=()):
        self.by_key = {}
        for f in qsos:
            self.add(f)

    @staticmethod
    def _key(f):
        return f.get("CALL", "").upper().strip(), (f.get("BAND") or "").lower()

    def add(self, f):
        t0 = qso_time(f)
        if t0:
            self.by_key.setdefault(self._key(f), []).append([t0, False])

    def find(self, f, consume=False):
        t0 = qso_time(f)
        if not t0:
            return False
        for entry in self.by_key.get(self._key(f), []):
            if not entry[1] and abs(entry[0] - t0) <= timedelta(minutes=MATCH_MINUTES):
                if consume:
                    entry[1] = True
                return True
        return False


def compare_logs(hrd_qsos, wl_qsos):
    """Retourne (dans Wavelog seulement, dans HRD seulement)."""
    hrd_idx = QsoIndex(hrd_qsos)
    wl_only = [f for f in wl_qsos if not hrd_idx.find(f, consume=True)]
    wl_idx = QsoIndex(wl_qsos)
    hrd_only = [f for f in hrd_qsos if not wl_idx.find(f, consume=True)]
    return wl_only, hrd_only


# --------------------------------------------------------------------------- historique

class History:
    """Derniers QSO traités, persistés sur disque (liste affichée + file d'attente)."""

    MAX = 3000

    def __init__(self):
        self.path = os.path.join(data_dir(), "history.json")
        self.lock = threading.Lock()
        try:
            with open(self.path, encoding="utf-8") as f:
                self.items = json.load(f)
        except (OSError, ValueError):
            self.items = []
        for item in self.items:  # les identifiants de la 1.0 étaient des numéros
            item["hrd_key"] = str(item["hrd_key"])

    def save(self):
        with self.lock:
            # on ne jette jamais un QSO encore en attente
            keep = [i for i in self.items[:-self.MAX] if i["status"] in ("pending", "error")]
            self.items = keep + self.items[-self.MAX:]
            data = list(self.items)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def find(self, key):
        with self.lock:
            for item in self.items:
                if item["hrd_key"] == key:
                    return item
        return None

    def add(self, key, fields, status, message="", direction="up"):
        """direction : "up" = HRD -> Wavelog, "down" = Wavelog -> HRD."""
        item = {"hrd_key": key, "fields": fields, "status": status, "message": message, "dir": direction,
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with self.lock:
            self.items.append(item)
        return item

    def pending(self, direction="up"):
        with self.lock:
            return [i for i in self.items if i["status"] == "pending" and i.get("dir", "up") == direction]

    def index(self, direction=None):
        """Index des QSO de l'historique (pour reconnaître un QSO déjà connu)."""
        with self.lock:
            return QsoIndex(i["fields"] for i in self.items
                            if direction is None or i.get("dir", "up") == direction)

    def snapshot(self):
        with self.lock:
            return [dict(i) for i in self.items]


# --------------------------------------------------------------------------- moteur

class UDPListener(threading.Thread):
    """Écoute l'envoi UDP de HRD sur la machine locale et passe chaque paquet à `on_packet`."""

    def __init__(self, port, on_packet, on_status):
        super().__init__(daemon=True)
        self.port, self.on_packet, self.on_status = int(port), on_packet, on_status
        self._stop_evt = threading.Event()

    def stop(self):
        self._stop_evt.set()

    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", self.port))
        except OSError as e:
            sock.close()
            self.on_status(False, str(e))
            return
        sock.settimeout(1)
        self.on_status(True, "")
        with sock:
            while not self._stop_evt.is_set():
                try:
                    data, _src = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    continue
                self.on_packet(data)


class Syncer(threading.Thread):
    """Moteur de fond : reçoit les QSO de HRD (-> Wavelog) et récupère ceux de Wavelog (-> HRD).

    `post(event, *args)` remonte les événements vers l'interface :
      ("hrd", ok, info) ("wl", "ok"|"bad"|"unset") ("log", text) ("refresh",) ("sent", call)
      ("compare", wl_only, hrd_only) ("compare_error", message)
    """

    RETRY_SECONDS = 30
    DOWNLOAD_SECONDS = 120

    def __init__(self, cfg, history, post):
        super().__init__(daemon=True)
        self.cfg, self.history, self.post = cfg, history, post
        self.cmds = queue.Queue()
        self.listener = None
        self._wl_state = None
        self._offline_logged = False
        self._need_check = True
        self._last_download = 0.0
        self._hrd_closed_logged = False

    # commandes envoyées par l'interface (ou par l'écoute UDP)
    def wake(self):
        self.cmds.put(("wake",))

    def packet(self, data):
        self.cmds.put(("packet", data))

    def resend(self, keys):
        self.cmds.put(("resend", list(keys)))

    def compare(self):
        self.cmds.put(("compare",))

    def add_missing(self, to_hrd, to_wavelog):
        self.cmds.put(("add_missing", list(to_hrd), list(to_wavelog)))

    def reconfigure(self):
        self.cmds.put(("reload",))

    def stop(self):
        self.cmds.put(("stop",))

    def start_listener(self):
        if self.listener:
            self.listener.stop()
            self.listener.join(3)
        port = int(self.cfg.get("udp_port") or 12060)
        self.listener = UDPListener(port, self.packet,
                                    lambda ok, err: self.post("hrd", ok, port if ok else err))
        self.listener.start()

    def run(self):
        self.start_listener()
        while True:
            for step in (self.upload_cycle, self.download_cycle):
                try:
                    step()
                except Exception as e:  # le thread ne doit jamais mourir
                    self.post("log", t("log_internal", err=repr(e)))
            try:
                cmd = self.cmds.get(timeout=self.RETRY_SECONDS)
            except queue.Empty:
                continue
            try:
                if not self.handle(cmd):
                    break
            except Exception as e:
                self.post("log", t("log_internal", err=repr(e)))
        if self.listener:
            self.listener.stop()

    def handle(self, cmd):
        kind = cmd[0]
        if kind == "stop":
            return False
        if kind == "packet":
            self.receive(cmd[1])
        elif kind == "resend":
            for k in cmd[1]:
                item = self.history.find(k)
                if item:
                    item["status"], item["message"] = "pending", ""
            self.save_history()
        elif kind == "compare":
            self.do_compare()
        elif kind == "add_missing":
            self.queue_missing(cmd[1], cmd[2])
        elif kind == "reload":
            old_port = self.listener.port if self.listener else None
            self._need_check, self._wl_state, self._last_download = True, None, 0.0
            if int(self.cfg.get("udp_port") or 12060) != old_port:
                self.start_listener()
        return True

    def save_history(self):
        try:
            self.history.save()
        except OSError as e:
            self.post("log", t("log_save_error", err=e))
        self.post("refresh")

    def save_config(self):
        try:
            save_config(self.cfg)
        except OSError as e:
            self.post("log", t("log_save_error", err=e))

    # ----------------------------------------------------------------- HRD -> Wavelog
    def receive(self, data):
        try:
            kind, ident, fields = contact_from_xml(data)
        except ValueError:
            return  # paquet qui n'est pas un QSO
        call = fields.get("CALL", "?")
        if kind == "contactinfo":
            if not fields.get("CALL") or self.history.find(ident):
                return  # paquet vide ou déjà reçu (HRD peut l'envoyer deux fois)
            if self.history.index("down").find(fields):
                return  # écho d'un QSO que l'app vient elle-même d'ajouter dans HRD depuis Wavelog
            when, _ = qso_label(fields)
            self.post("log", t("log_new", call=call, when=when))
            self.history.add(ident, fields, "pending")
            self.save_history()
        elif kind == "contactreplace":
            self.post("log", t("log_replace", call=call))
        elif kind == "contactdelete":
            self.post("log", t("log_delete", call=call))

    def _set_wl(self, state):
        if state != self._wl_state:
            self._wl_state = state
            self.post("wl", state)

    def upload_cycle(self):
        if not is_configured(self.cfg):
            self._set_wl("unset")
            return
        if self._need_check:
            try:
                check_key(self.cfg["wavelog_url"], self.cfg["api_key"])
                self._need_check = False
                self._set_wl("ok")
            except WavelogOffline:
                self._set_wl("bad")
            except WavelogError as e:
                self._set_wl("bad")
                self.post("log", t("log_error", call="—", err=e))
        self.upload_pending()

    def upload_pending(self):
        pending = self.history.pending("up")
        done = 0
        for item in pending:
            if not self.cmds.empty() and self.cmds.queue[0][0] == "stop":
                break
            call = item["fields"].get("CALL", "?")
            try:
                status = upload_qso(self.cfg["wavelog_url"], self.cfg["api_key"],
                                    self.cfg["station_id"], item["fields"])
            except WavelogOffline as e:
                self._set_wl("bad")
                if not self._offline_logged:
                    self._offline_logged = True
                    self.post("log", t("log_offline", err=e, n=len(pending) - done))
                break
            except WavelogError as e:
                item["status"], item["message"] = "error", str(e)[:300]
                self.post("log", t("log_error", call=call, err=e))
            else:
                item["status"], item["message"] = status, ""
                self._offline_logged = False
                self._set_wl("ok")
                if status == "sent":
                    try:
                        append_backup(item["fields"])
                    except OSError:
                        pass
                    if len(pending) <= 5:
                        self.post("log", t("log_sent", call=call))
                        self.post("sent", call)
                elif len(pending) <= 5:
                    self.post("log", t("log_dupe", call=call))
            done += 1
            if done % 20 == 0:
                self.save_history()
        if done:
            self.save_history()

    # ----------------------------------------------------------------- Wavelog -> HRD
    def stations(self):
        return [s for s in (self.cfg.get("download_stations") or [self.cfg["station_id"]]) if str(s).strip()]

    def download_cycle(self, force=False):
        if is_configured(self.cfg) and self.cfg.get("download_enabled", True):
            if force or time.time() - self._last_download >= self.DOWNLOAD_SECONDS:
                self._last_download = time.time()
                self.fetch_new_from_wavelog()
        self.push_to_hrd()  # aussi les QSO ajoutés via « Comparer les deux logs »

    def fetch_new_from_wavelog(self):
        first = self.cfg.get("wl_last_id") is None
        try:
            qsos, last_id = fetch_wavelog(self.cfg["wavelog_url"], self.cfg["api_key"], self.stations(),
                                          0 if first else self.cfg["wl_last_id"])
        except WavelogOffline:
            return
        except WavelogError as e:
            self.post("log", t("log_fetch_error", err=e))
            return
        if first:  # point de départ : on ne recopie pas l'existant (voir « Comparer les deux logs »)
            self.cfg["wl_last_id"] = last_id
            self.save_config()
            self.post("log", t("log_download_start"))
            return
        known = self.history.index()
        candidates = [f for f in qsos if not known.find(f)]  # pas venu de HRD par l'app, pas déjà copié
        if candidates:
            # Déjà dans HRD par un autre chemin (import ADIF manuel…) ? On vérifie dans le log HRD,
            # en lecture seule, et seulement quand Wavelog a vraiment du nouveau.
            path = self.cfg["hrd_db"] or default_hrd_db()
            if path and os.path.exists(path):
                try:
                    in_hrd = QsoIndex(row_to_fields(r) for r in HRDReader(path).all_rows())
                    candidates = [f for f in candidates if not in_hrd.find(f)]
                except (sqlite3.Error, OSError) as e:
                    self.post("log", t("log_hrd_error", err=e))
                    return  # on réessaiera : mieux vaut attendre que créer des doublons
        added = 0
        for f in candidates:
            if known.find(f):
                continue  # doublon à l'intérieur même de cette récupération
            fields = fields_for_hrd(f)
            if not fields.get("CALL"):
                continue
            self.history.add("wl:" + qso_sig(fields), fields, "pending", direction="down")
            known.add(fields)
            added += 1
            if added <= 5:
                when, call = qso_label(fields)
                self.post("log", t("log_from_wavelog", call=call, when=when))
        if added > 5:
            self.post("log", t("log_from_wavelog_many", n=added))
        self.cfg["wl_last_id"] = last_id
        self.save_config()
        if added:
            self.save_history()

    def push_to_hrd(self):
        pending = self.history.pending("down")
        if not pending:
            return
        port = int(self.cfg.get("hrd_in_port") or 2333)
        if not hrd_listening(port):
            if not self._hrd_closed_logged:
                self._hrd_closed_logged = True
                self.post("log", t("log_hrd_closed", n=len(pending), port=port))
            return
        self._hrd_closed_logged = False
        for item in pending:
            try:
                send_to_hrd(item["fields"], port)
            except OSError as e:
                item["status"], item["message"] = "error", str(e)[:300]
                continue
            item["status"], item["message"] = "imported", ""
            if len(pending) <= 5:
                self.post("log", t("log_imported", call=item["fields"].get("CALL", "?")))
            time.sleep(0.3)  # laisser HRD enregistrer chaque QSO (il fait une recherche à chaque réception)
        if len(pending) > 5:
            self.post("log", t("log_imported_many", n=len(pending)))
        self.save_history()

    # ----------------------------------------------------------------- comparaison des deux logs
    def do_compare(self):
        if not is_configured(self.cfg):
            self.post("compare_error", t("err_missing"))
            return
        path = self.cfg["hrd_db"] or default_hrd_db()
        if not path or not os.path.exists(path):
            self.post("compare_error", t("log_no_db"))
            return
        try:
            hrd_qsos = [row_to_fields(r) for r in HRDReader(path).all_rows()]
        except (sqlite3.Error, OSError) as e:
            self.post("compare_error", t("log_hrd_error", err=e))
            return
        try:
            wl_qsos, last_id = fetch_wavelog(self.cfg["wavelog_url"], self.cfg["api_key"], self.stations(), 0)
        except WavelogError as e:
            self.post("compare_error", t("log_fetch_error", err=e))
            return
        if self.cfg.get("wl_last_id") is None:
            self.cfg["wl_last_id"] = last_id
            self.save_config()
        # ce qui est déjà en file d'attente n'est plus « manquant »
        queued = QsoIndex(i["fields"] for i in self.history.snapshot() if i["status"] in ("pending", "imported"))
        wl_only, hrd_only = compare_logs([f for f in hrd_qsos if f.get("CALL")], wl_qsos)
        wl_only = [fields_for_hrd(f) for f in wl_only if not queued.find(f)]
        hrd_only = [f for f in hrd_only if not queued.find(f)]
        self.post("compare", wl_only, hrd_only)

    def queue_missing(self, to_hrd, to_wavelog):
        for f in to_hrd:
            self.history.add("wl:" + qso_sig(f), f, "pending", direction="down")
        for f in to_wavelog:
            self.history.add("cmp:" + qso_sig(f), f, "pending")
        if to_hrd:
            self.post("log", t("log_queued_to_hrd", n=len(to_hrd)))
        if to_wavelog:
            self.post("log", t("log_queued_to_wavelog", n=len(to_wavelog)))
        self.save_history()
