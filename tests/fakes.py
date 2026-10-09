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
                s = obj["string"]
                call = re.search(r"<call:\d+>(\S+)", s).group(1)
                when = re.search(r"<time_on:\d+>(\d+)", s).group(1)
                if any(q[0] == call and q[1] == when for q in outer.qsos):
                    return self.reply(400, {"status": "abort", "adif_errors": 1,
                                            "messages": ["", "Duplicate for %s" % call]})
                outer.qsos.append((call, when, s, obj["station_profile_id"]))
                self.reply(201, {"status": "created", "adif_count": 1, "adif_errors": 0})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
