"""Radio en direct : HRD Rig Control <-> Wavelog.

- Lecture : l'app interroge HRD Rig Control (TCP 7809, protocole utilisé aussi par WSJT-X) pour connaître
  la radio, la fréquence et le mode, et les envoie à Wavelog (POST index.php/api/radio). Wavelog affiche
  alors la radio « en ligne » et pré-remplit fréquence / bande / mode à la saisie d'un QSO.
- Changement de fréquence (QSY) : quand on clique sur un spot dans Wavelog, le navigateur appelle
  http://127.0.0.1:54321/<fréquence en Hz>/<mode> ; l'app demande alors à HRD de régler la radio.
  Seules la fréquence (et éventuellement le mode) sont modifiées : JAMAIS l'émission (PTT).
"""

import json
import re
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .i18n import t

MAGIC_1, MAGIC_2 = 0x1234ABCD, 0xABCD1234
MIN_HZ, MAX_HZ = 100_000, 3_000_000_000  # garde-fou : on ne règle jamais une fréquence absurde


class RigError(Exception):
    pass


def hrd_message(cmd):
    payload = (cmd + "\0").encode("utf-16-le")
    return struct.pack("<IIII", 16 + len(payload), MAGIC_1, MAGIC_2, 0) + payload


class HRDRig:
    """Client minimal de HRD Rig Control (une connexion, commandes texte, réponses UTF-16)."""

    def __init__(self, host="127.0.0.1", port=7809, timeout=3):
        self.host, self.port, self.timeout = host, int(port), timeout
        self.sock = None
        self.context = None
        self.radio = ""
        self.lock = threading.Lock()  # lecture régulière et QSY peuvent arriver en même temps

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock, self.context = None, None

    def _connect(self):
        self.close()
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self.sock.settimeout(self.timeout)
        except OSError as e:
            self.sock = None
            raise RigError(str(e))
        radios = self._ask("get radios")  # « 523:FTDX-101D-MP » (un ou plusieurs, séparés par des virgules)
        current = self._ask("get radio")
        self.context, self.radio = None, current
        for entry in radios.split(","):
            num, _, name = entry.partition(":")
            if name.strip() == current.strip() or self.context is None:
                self.context = num.strip()
        if not self.context or not current:
            self.close()
            raise RigError("aucune radio connectée dans HRD")

    def _ask(self, cmd):
        try:
            self.sock.sendall(hrd_message(cmd))
            buf = b""
            while len(buf) < 16 or len(buf) < struct.unpack("<I", buf[:4])[0]:
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise RigError("HRD a fermé la connexion")
                buf += chunk
        except (OSError, struct.error) as e:
            self.close()
            raise RigError(str(e))
        size, m1, m2, _ = struct.unpack("<IIII", buf[:16])
        if (m1, m2) != (MAGIC_1, MAGIC_2):
            self.close()
            raise RigError("réponse de HRD non reconnue")
        return buf[16:size].decode("utf-16-le", "replace").split("\0")[0].strip()

    def command(self, cmd):
        """Commande avec le contexte de la radio ; reconnecte si besoin."""
        with self.lock:
            if self.sock is None or self.context is None:
                self._connect()
            return self._ask("[%s] %s" % (self.context, cmd))

    def state(self):
        """(radio, fréquence Hz, mode HRD, fréquence VFO B Hz ou None)."""
        freq = int(self.command("get frequency") or 0)
        mode = self.command("get dropdown-text {Mode}")
        mode = mode.split(":", 1)[1].strip() if ":" in mode else mode
        rx = None
        freqs = self.command("get frequencies")
        if "-" in freqs:
            try:
                rx = int(freqs.split("-")[1])
            except ValueError:
                rx = None
        return self.radio, freq, mode, rx

    def set_frequency(self, hz):
        hz = int(hz)
        if not MIN_HZ <= hz <= MAX_HZ:
            raise RigError("fréquence hors limites : %s Hz" % hz)
        reply = self.command("set frequency-hz %d" % hz)
        if reply.upper() != "OK":
            raise RigError("HRD a répondu « %s »" % reply)


# Modes affichés par HRD (menu « Mode ») -> modes compris par Wavelog.
# Modes « data » (DATA-U, DATA-L, DATA-FM…) : None = on n'envoie PAS de mode. Wavelog laisse alors le mode
# choisi dans le formulaire (FT8, JS8, PSK…) au lieu de le remplacer par USB, ce qui ferait un faux QSO phonie.
_MODE_MAP = [
    (re.compile(r"^(DATA|PKT|DIG)|^(USB|LSB)[-_ ]?D", re.I), None),
    (re.compile(r"^USB", re.I), "USB"),
    (re.compile(r"^LSB", re.I), "LSB"),
    (re.compile(r"^CW", re.I), "CW"),
    (re.compile(r"^RTTY", re.I), "RTTY"),
    (re.compile(r"^(FM|C4FM|NFM|WFM)", re.I), "FM"),
    (re.compile(r"^AM", re.I), "AM"),
]


DATA_MODES = ("none", "auto", "FT8", "FT4", "JS8", "PSK31", "RTTY")

# Fréquences d'appel usuelles (fréquence affichée en USB, kHz) des modes numériques.
# En DATA, la radio ne sait pas quel mode est utilisé : on le déduit de la fréquence.
_DIAL_KHZ = {
    "FT8": (1840, 3573, 5357, 7074, 10136, 14074, 18100, 21074, 24915, 28074, 50313, 50323, 144174),
    "FT4": (3575, 7047.5, 10140, 14080, 18104, 21140, 24919, 28180, 50318, 144170),
    "JS8": (1842, 3578, 7078, 10130, 14078, 18104, 21078, 24922, 28078, 50318, 144178),
    "PSK31": (1838, 3580, 7040, 7070, 10142, 14070, 18100, 21070, 24920, 28120, 50250),
}
_DIAL_TOLERANCE_KHZ = 1.5


def guess_data_mode(freq_hz, js8_open=False):
    """Mode numérique probable d'après la fréquence (None si inconnue). JS8 a la priorité quand
    JS8Call est ouvert et que la fréquence est aussi une fréquence JS8 (ex. 18,104 = FT4 et JS8)."""
    khz = freq_hz / 1000.0
    matches = [mode for mode, dials in _DIAL_KHZ.items()
               if any(abs(khz - d) <= _DIAL_TOLERANCE_KHZ for d in dials)]
    if js8_open and "JS8" in matches:
        return "JS8"
    return matches[0] if matches else None


def js8call_running():
    """Vrai si JS8Call est ouvert (liste des processus Windows, sans fenêtre)."""
    try:
        import subprocess
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq js8call.exe", "/NH"], capture_output=True,
                             text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return "js8call.exe" in out.lower()
    except (OSError, ValueError, Exception):
        return False


def wavelog_mode(hrd_mode, data_mode="none", js8_open=False, freq_hz=0):
    """Mode HRD -> mode Wavelog. En DATA (DATA-U…) : mode numérique choisi dans les réglages, ou en
    automatique d'après la fréquence d'appel (14,074 = FT8, 14,070 = PSK31…), sinon JS8 si JS8Call
    est ouvert, sinon rien (Wavelog garde le mode du formulaire). « none » : jamais de mode en DATA."""
    for rx, mode in _MODE_MAP:
        if rx.search(hrd_mode or ""):
            if mode is not None:
                return mode
            if data_mode in (None, "", "none"):
                return None
            if data_mode == "auto":
                return guess_data_mode(freq_hz, js8_open) or ("JS8" if js8_open else None)
            return data_mode[:10]
    return (hrd_mode or "")[:10]


def radio_payload(key, radio, freq, mode, rx=None, cat_url=None, data_mode="none", js8_open=False):
    # Le VFO B n'est PAS une fréquence de réception séparée (sauf en split, que HRD ne signale pas
    # simplement) : on n'envoie que la fréquence principale, sinon Wavelog affiche un faux split.
    p = {"key": key, "radio": radio[:250], "frequency": int(freq)}
    wl_mode = wavelog_mode(mode, data_mode, js8_open, freq)
    if wl_mode:
        p["mode"] = wl_mode
    if cat_url:
        p["cat_url"] = cat_url
    return p


class QSYServer(threading.Thread):
    """Petit serveur local (127.0.0.1 uniquement) qui reçoit les demandes de QSY de Wavelog :
    GET /<fréquence Hz>/<mode>  ->  on_qsy(hz, mode). Répond avec les en-têtes qui autorisent
    l'appel depuis la page Wavelog dans le navigateur."""

    def __init__(self, port, on_qsy, on_status):
        super().__init__(daemon=True)
        self.port, self.on_qsy, self.on_status = int(port), on_qsy, on_status
        self.httpd = None
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _cors(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Private-Network", "true")

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors()
                self.end_headers()

            def do_GET(self):
                m = re.match(r"^/(\d{5,10})(?:/([A-Za-z0-9_-]{1,10}))?/?$", self.path.split("?")[0])
                if not m:
                    self.send_response(404)
                    self._cors()
                    self.end_headers()
                    return
                ok, message = outer.on_qsy(int(m.group(1)), m.group(2) or "")
                body = json.dumps({"status": "ok" if ok else "error", "message": message}).encode()
                self.send_response(200 if ok else 500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.handler = Handler

    def run(self):
        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), self.handler)
        except OSError as e:
            self.on_status(False, str(e))
            return
        self.on_status(True, "")
        self.httpd.serve_forever(poll_interval=0.5)

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


class RigBridge(threading.Thread):
    """Lit la radio dans HRD toutes les `interval` s et l'envoie à Wavelog quand elle change
    (et au moins toutes les `keepalive` s). Reçoit aussi les QSY de Wavelog.

    post(event, *args) :
      ("rig", state, text)   state : "ok" | "off" (HRD/radio absent) | "disabled"
      ("log", text)
    """

    def __init__(self, cfg, send_radio, post, interval=2.0, keepalive=60.0):
        super().__init__(daemon=True)
        self.cfg, self.send_radio, self.post = cfg, send_radio, post
        self.interval, self.keepalive = interval, keepalive
        self.rig = HRDRig(port=cfg.get("rig_port", 7809))
        self._stop_evt = threading.Event()
        self._last_sent = None
        self._last_time = 0.0
        self._state = None
        self.qsy = None
        self._js8_open, self._js8_checked = False, 0.0
        self.js8_check = js8call_running  # remplaçable dans les tests

    def stop(self):
        self._stop_evt.set()
        if self.qsy:
            self.qsy.stop()
        self.rig.close()

    def _set_state(self, state, text):
        if (state, text) != self._state:
            self._state = (state, text)
            self.post("rig", state, text)

    def handle_qsy(self, hz, mode):
        if not self.cfg.get("qsy_enabled", True):
            return False, t("msg_qsy_disabled")
        try:
            self.rig.set_frequency(hz)
        except RigError as e:
            self.post("log", t("log_qsy_error", mhz="%.3f" % (hz / 1e6), err=e))
            return False, str(e)
        self.post("log", t("log_qsy", mhz="%.3f" % (hz / 1e6)))
        self._last_time = 0  # renvoyer tout de suite le nouvel état à Wavelog
        return True, "OK"

    def run(self):
        if not self.cfg.get("rig_enabled", True):
            self._set_state("disabled", "")
            return
        qsy_port = int(self.cfg.get("qsy_port", 54321))
        self.qsy = QSYServer(qsy_port, self.handle_qsy,
                             lambda ok, err: ok or self.post("log", t("log_qsy_port_busy", port=qsy_port, err=err)))
        self.qsy.start()
        cat_url = "http://127.0.0.1:%d" % qsy_port
        while not self._stop_evt.is_set():
            try:
                radio, freq, mode, rx = self.rig.state()
                self._set_state("ok", "%s %.3f MHz %s" % (radio, freq / 1e6, mode))
                data_mode = self.cfg.get("data_mode", "none")
                if data_mode == "auto" and time.time() - self._js8_checked >= 30:  # coûteux : toutes les 30 s
                    self._js8_open, self._js8_checked = self.js8_check(), time.time()
                current = (radio, freq, mode, data_mode, self._js8_open)
                if current != self._last_sent or time.time() - self._last_time >= self.keepalive:
                    payload = radio_payload(self.cfg.get("api_key", ""), radio, freq, mode, rx, cat_url,
                                            data_mode, self._js8_open)
                    if self.send_radio(payload):
                        self._last_sent, self._last_time = current, time.time()
            except RigError as e:
                self._set_state("off", str(e))
                self._stop_evt.wait(10)  # HRD fermé : on réessaie sans insister
                continue
            except Exception as e:  # le thread ne doit jamais mourir
                self._set_state("off", repr(e))
            self._stop_evt.wait(self.interval)
