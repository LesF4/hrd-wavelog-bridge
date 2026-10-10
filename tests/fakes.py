"""Faux Wavelog (API HTTP), faux HRD (envoi UDP) et faux log HRD (SQLite) pour les tests et la démo."""
import json
import re
import socket
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY = "testkey"
COLUMNS = ["COL_PRIMARY_KEY INT64 PRIMARY KEY", "COL_CALL TEXT", "COL_BAND TEXT", "COL_FREQ INTEGER",
           "COL_MODE TEXT", "COL_SUBMODE TEXT", "COL_QSO_DATE TEXT", "COL_TIME_ON TEXT", "COL_RST_SENT TEXT",
           "COL_RST_RCVD TEXT", "COL_GRIDSQUARE TEXT", "COL_NAME TEXT", "COL_TX_PWR DOUBLE",
           "COL_LAT DOUBLE", "COL_LON DOUBLE", "COL_MY_IOTA_ISLAND_ID INTEGER",
           "COL_QRZCOM_QSO_UPLOAD_STATUS TEXT", "COL_APP_HAMRADIODELUXE_HRDCOUNTRYNO TEXT", "COL_COMMENT TEXT",
           "COL_EMAIL TEXT", "COL_ADDRESS TEXT", "COL_NOTES TEXT"]


def make_hrd_db(path, n=3):
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE TABLE_HRD_CONTACTS_V07 (%s)" % ", ".join(COLUMNS))
    for i in range(1, n + 1):
        add_qso(con, i, "OLD%d" % i, minute=10 + i)
    con.commit()
    return con


def add_qso(con, key, call, name="Gérard", minute=0):
    con.execute("INSERT INTO TABLE_HRD_CONTACTS_V07 VALUES (%s)" % ",".join("?" * len(COLUMNS)),
                (key, call, "20m", 14074000, "FT8", "", "2026-10-09", "12:%02d:30.000" % minute, "-10",
                 "-07", "JN18", name, 100.0, 48.85, 2.35, -1, "RESULT=OK", "227", "test",
                 "prive@example.org", "1 rue Privée", "note perso"))
    con.commit()


CONTACT_XML = """<?xml version="1.0" encoding="utf-8"?>
<{kind}>
  <app>HamRadioDeluxe</app>
  <contestname></contestname>
  <dbname>TEST</dbname>
  <timestamp>{ts}</timestamp>
  <band>{band}</band>
  <txfreq>{freq}</txfreq>
  <operator>F4XYZ</operator>
  <mode>{mode}</mode>
  <submode>{submode}</submode>
  <call>{call}</call>
  <snt>-11</snt>
  <sntnr>0</sntnr>
  <rcv>+06</rcv>
  <rcvnr>0</rcvnr>
  <gridsquare>IO86</gridsquare>
  <comment>essai</comment>
  <qth>Dundee</qth>
  <name>{name}</name>
  <power>300</power>
  <mycall>F4XYZ</mycall>
  <ID>{ident}</ID>
</{kind}>"""


def contact_xml(call, ident, kind="contactinfo", ts="2026-10-09 12:45:30", band="14", freq="14075491",
                mode="FT8", submode="", name="Gérard"):
    """Paquet au format envoyé par HRD Logbook (QSO Forwarding, envoi UDP)."""
    return CONTACT_XML.format(kind=kind, ts=ts, band=band, freq=freq, mode=mode, submode=submode,
                              call=call, name=name, ident=ident).encode("utf-8")


def send_contact(port, *args, **kwargs):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(contact_xml(*args, **kwargs), ("127.0.0.1", port))


class FakeWavelog:
    """Imite l'API Wavelog : auth/{key}, station_info/{key}, qso (avec détection des doublons)."""

    def __init__(self):
        self.qsos = []  # (call, time_on, adif, station_id)
        self.online = True
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def reply_xml(self, text):
                body = text.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/xml")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not outer.online:
                    return self.send_error(503)
                m = re.match(r"/index.php/api/(auth|station_info)/(.*)", self.path)
                if not m:
                    return self.send_error(404)
                if m.group(1) == "auth":  # la vraie API répond en XML ici
                    if m.group(2) != KEY:
                        return self.reply_xml("<auth><message>Key Invalid - either not found or disabled"
                                              "</message></auth>")
                    return self.reply_xml("<auth><status>Valid</status><rights>rw</rights></auth>")
                if m.group(2) != KEY:
                    return self.reply(401, {"status": "failed", "reason": "missing or invalid api key"})
                return self.reply(200, [{"station_id": "7", "station_profile_name": "Maison",
                                         "station_callsign": "F4MAJ", "station_gridsquare": "JN37QS",
                                         "station_active": "1"}])

            def do_POST(self):
                if not outer.online:
                    return self.send_error(503)
                obj = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())
                if obj.get("key") != KEY:
                    return self.reply(401, {"status": "failed", "reason": "missing or wrong api key"})
                if self.path.endswith("/get_contacts_adif"):  # export des QSO d'identifiant > fetchfromid
                    since = int(obj["fetchfromid"])
                    with outer.lock:
                        recs = [(i, q[2]) for i, q in enumerate(outer.qsos, start=1) if i > since]
                    last = recs[-1][0] if recs else since
                    adif = ("Wavelog export <eoh>\n" + "\n".join(r for _i, r in recs)) if recs else None
                    return self.reply(200, {"status": "successful", "lastfetchedid": last,
                                            "exported_qsos": len(recs), "adif": adif})
                s = obj["string"]
                call = re.search(r"<call:\d+>(\S+)", s).group(1)
                when = re.search(r"<time_on:\d+>(\d+)", s).group(1)
                if any(q[0] == call and q[1] == when for q in outer.qsos):
                    return self.reply(400, {"status": "abort", "adif_errors": 1,
                                            "messages": ["", "Duplicate for %s" % call]})
                with outer.lock:
                    outer.qsos.append((call, when, s, obj["station_profile_id"]))
                self.reply(201, {"status": "created", "adif_count": 1, "adif_errors": 0})

        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def add_external(self, call, date="20261010", time_on="093000", band="40m", freq="7.074000", mode="FT8"):
        """QSO saisi directement dans Wavelog (radio-club, portable…)."""
        f = {"CALL": call, "QSO_DATE": date, "TIME_ON": time_on, "BAND": band, "FREQ": freq, "MODE": mode,
             "RST_SENT": "-10", "RST_RCVD": "-12", "STATION_CALLSIGN": "F4XYZ", "MY_GRIDSQUARE": "JN37QS",
             "APP_WAVELOG_DUMMY": "x"}
        adif = "".join("<%s:%d>%s " % (k, len(v), v) for k, v in f.items()) + "<eor>"
        with self.lock:
            self.qsos.append((call, time_on, adif, "7"))

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class FakeHRDReceiver:
    """Imite la réception UDP de HRD (ADIF). Avec `echo_port`, renvoie chaque QSO reçu à l'app
    comme le fait HRD avec son envoi UDP (QSO Forwarding)."""

    def __init__(self, echo_port=None):
        self.received = []
        self.echo_port = echo_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.5)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not self._stop.is_set():
            try:
                data, _src = self.sock.recvfrom(65535)
            except (socket.timeout, OSError):
                continue
            text = data.decode("cp1252")
            self.received.append(text)
            if self.echo_port:
                call = re.search(r"<call:\d+>(\S+)", text).group(1)
                date = re.search(r"<qso_date:\d+>(\d{8})", text).group(1)
                tm = re.search(r"<time_on:\d+>(\d{6})", text).group(1)
                freq = re.search(r"<freq:\d+>([\d.]+)", text).group(1)
                ts = "%s-%s-%s %s:%s:%s" % (date[:4], date[4:6], date[6:], tm[:2], tm[2:4], tm[4:])
                send_contact(self.echo_port, call, "echo-%d" % len(self.received), ts=ts,
                             band=str(int(float(freq))), freq=str(int(float(freq) * 1e6)))

    def calls(self):
        return [re.search(r"<call:\d+>(\S+)", r).group(1) for r in self.received]

    def close(self):
        self._stop.set()
        self.sock.close()
