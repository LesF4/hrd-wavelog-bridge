"""Logique du pont HRD Logbook -> Wavelog (sans interface graphique).

HRD Logbook envoie chaque nouveau QSO en UDP (« QSO Forwarding », envoi UDP, format XML
<contactinfo> type N1MM) : l'app écoute ce port sur la machine locale, convertit le QSO en
ADIF et l'envoie à Wavelog par son API (POST index.php/api/qso, clé API en écriture).

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
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .i18n import t

APP_NAME = "HRDtoWavelog"
APP_TITLE = "HRD Logbook → Wavelog"
APP_VERSION = "1.1.0"
APP_URL = "https://github.com/LesF4/hrd-wavelog-bridge"
TABLE = "TABLE_HRD_CONTACTS_V07"

DEFAULT_CONFIG = {
    "udp_port": 12060,        # port de l'envoi UDP de HRD (QSO Forwarding)
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

    def add(self, key, fields, status, message=""):
        item = {"hrd_key": key, "fields": fields, "status": status, "message": message,
                "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        with self.lock:
            self.items.append(item)
        return item

    def pending(self):
        with self.lock:
            return [i for i in self.items if i["status"] == "pending"]

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
    """Reçoit les QSO de HRD et les envoie à Wavelog (thread de fond).

    `post(event, *args)` remonte les événements vers l'interface :
      ("hrd", ok, info) ("wl", "ok"|"bad"|"unset") ("log", text) ("refresh",) ("sent", call)
    """

    RETRY_SECONDS = 30

    def __init__(self, cfg, history, post):
        super().__init__(daemon=True)
        self.cfg, self.history, self.post = cfg, history, post
        self.cmds = queue.Queue()
        self.listener = None
        self._wl_state = None
        self._offline_logged = False
        self._need_check = True

    # commandes envoyées par l'interface (ou par l'écoute UDP)
    def wake(self):
        self.cmds.put(("wake",))

    def packet(self, data):
        self.cmds.put(("packet", data))

    def resend(self, keys):
        self.cmds.put(("resend", list(keys)))

    def send_whole_log(self):
        self.cmds.put(("history",))

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
            try:
                self.upload_cycle()
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
        elif kind == "history":
            self.queue_whole_log()
        elif kind == "reload":
            old_port = self.listener.port if self.listener else None
            self._need_check, self._wl_state = True, None
            if int(self.cfg.get("udp_port") or 12060) != old_port:
                self.start_listener()
        return True

    def save_history(self):
        try:
            self.history.save()
        except OSError as e:
            self.post("log", t("log_save_error", err=e))
        self.post("refresh")

    def receive(self, data):
        try:
            kind, ident, fields = contact_from_xml(data)
        except ValueError:
            return  # paquet qui n'est pas un QSO
        call = fields.get("CALL", "?")
        if kind == "contactinfo":
            if not fields.get("CALL") or self.history.find(ident):
                return  # paquet vide ou déjà reçu (HRD peut l'envoyer deux fois)
            when, _ = qso_label(fields)
            self.post("log", t("log_new", call=call, when=when))
            self.history.add(ident, fields, "pending")
            self.save_history()
        elif kind == "contactreplace":
            self.post("log", t("log_replace", call=call))
        elif kind == "contactdelete":
            self.post("log", t("log_delete", call=call))

    def queue_whole_log(self):
        path = self.cfg["hrd_db"] or default_hrd_db()
        if not path or not os.path.exists(path):
            self.post("log", t("log_no_db"))
            return
        try:
            rows = HRDReader(path).all_rows()
        except (sqlite3.Error, OSError) as e:
            self.post("log", t("log_hrd_error", err=e))
            return
        queued = 0
        for row in rows:
            key = "db:%s" % row["COL_PRIMARY_KEY"]
            fields = row_to_fields(row)
            old = self.history.find(key)
            if not fields.get("CALL") or (old and old["status"] in ("sent", "dupe")):
                continue
            if old:
                old.update(fields=fields, status="pending", message="")
            else:
                self.history.add(key, fields, "pending")
            queued += 1
        self.post("log", t("log_history", n=queued))
        self.save_history()

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
        pending = self.history.pending()
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
