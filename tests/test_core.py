import os
import queue
import socket
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["APPDATA"] = tempfile.mkdtemp()  # config/historique de test isolés
from hrdwl import core, i18n  # noqa: E402
from tests import fakes  # noqa: E402


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(cond, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.1)
    return False


class XmlTests(unittest.TestCase):
    def test_contact_from_hrd(self):
        kind, ident, f = core.contact_from_xml(fakes.contact_xml("gm9zz", "abc123"))
        self.assertEqual((kind, ident), ("contactinfo", "abc123"))
        self.assertEqual(f, {
            "QSO_DATE": "20261009", "TIME_ON": "124530", "CALL": "GM9ZZ", "FREQ": "14.075491", "BAND": "20m",
            "MODE": "FT8", "RST_SENT": "-11", "RST_RCVD": "+06", "GRIDSQUARE": "IO86", "NAME": "Gérard",
            "QTH": "Dundee", "COMMENT": "essai", "STATION_CALLSIGN": "F4XYZ", "OPERATOR": "F4XYZ",
            "TX_PWR": "300"})

    def test_frequency_units(self):
        for raw, band, mhz in (("14075491", "14", "14.075491"), ("1407549", "14", "14.075490"),
                               ("433600000", "430", "433.600000"), ("7078000", "7", "7.078000"),
                               ("50313", "50", "50.313000")):
            _k, _i, f = core.contact_from_xml(fakes.contact_xml("K1AB", "x", freq=raw, band=band))
            self.assertEqual(f["FREQ"], mhz, raw)

    def test_js8_submode_and_other_kinds(self):
        _k, _i, f = core.contact_from_xml(fakes.contact_xml("K1AB", "x", mode="MFSK", submode="JS8"))
        self.assertEqual((f["MODE"], f["SUBMODE"]), ("MFSK", "JS8"))
        self.assertEqual(core.contact_from_xml(fakes.contact_xml("K1AB", "x", kind="contactreplace"))[0],
                         "contactreplace")
        with self.assertRaises(ValueError):
            core.contact_from_xml(b"pas du XML")


class ConversionTests(unittest.TestCase):
    def test_row_to_fields_keeps_only_qso_fields(self):
        row = {"COL_PRIMARY_KEY": 5, "COL_CALL": "4S7AB", "COL_FREQ": 14074439, "COL_BAND": "20M",
               "COL_QSO_DATE": "2026-10-09", "COL_TIME_ON": "11:16:00.000", "COL_TX_PWR": 300.0,
               "COL_LAT": 48.85, "COL_EMAIL": "prive@example.org", "COL_ADDRESS": "1 rue Privée",
               "COL_NOTES": "note perso", "COL_QRZCOM_QSO_UPLOAD_STATUS": "RESULT=OK", "COL_NAME": "",
               "COL_CQZ": 0}
        self.assertEqual(core.row_to_fields(row), {
            "CALL": "4S7AB", "QSO_DATE": "20261009", "TIME_ON": "111600", "BAND": "20m",
            "FREQ": "14.074439", "TX_PWR": "300"})

    def test_adif_lengths_count_characters(self):
        rec = core.build_adif_record({"NAME": "Gérard", "CALL": "F4MAJ"})
        self.assertEqual(rec, "<name:6>Gérard <call:5>F4MAJ <eor>")

    def test_base_url(self):
        for u in ("https://wl.example.org", "https://wl.example.org/",
                  "https://wl.example.org/index.php/logbook", "https://wl.example.org/index.php"):
            self.assertEqual(core._base(u), "https://wl.example.org/index.php/api/")

    def test_same_keys_in_all_languages(self):
        self.assertEqual(set(i18n.TEXTS["fr"]), set(i18n.TEXTS["en"]))


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.wl = fakes.FakeWavelog()
        self.db = os.path.join(tempfile.mkdtemp(), "log.hrdsql")
        self.con = fakes.make_hrd_db(self.db, n=3)
        self.port = free_udp_port()
        self.cfg = dict(core.DEFAULT_CONFIG, udp_port=self.port, hrd_db=self.db, api_key=fakes.KEY,
                        station_id="7", wavelog_url=self.wl.url + "/index.php/logbook")
        self.history = core.History()
        self.history.items = []
        self.events = queue.Queue()
        self.sync = core.Syncer(self.cfg, self.history, lambda *e: self.events.put(e))
        self.sync.start()
        self.assertTrue(wait_for(lambda: ("hrd", True, self.port) in list(self.events.queue)))

    def tearDown(self):
        self.sync.stop()
        self.sync.join(5)
        self.assertFalse(self.sync.is_alive())
        self.con.close()
        self.wl.close()

    def sent_calls(self):
        return sorted(q[0] for q in self.wl.qsos)

    def status(self, key):
        item = self.history.find(key)
        return item and item["status"]

    def test_qso_from_hrd_reaches_wavelog(self):
        fakes.send_contact(self.port, "EA4XY", "id-1")
        self.assertTrue(wait_for(lambda: self.status("id-1") == "sent"))
        self.assertEqual(self.sent_calls(), ["EA4XY"])
        self.assertIn("<name:6>Gérard", self.wl.qsos[0][2])
        self.assertEqual(self.wl.qsos[0][3], "7")

        fakes.send_contact(self.port, "EA4XY", "id-1")  # HRD renvoie le même paquet : ignoré
        fakes.send_contact(self.port, "EA4XY", "id-1", kind="contactreplace")
        time.sleep(0.5)
        self.assertEqual(len(self.wl.qsos), 1)
        self.assertEqual(len(self.history.items), 1)

    def test_offline_then_back(self):
        self.wl.online = False
        fakes.send_contact(self.port, "DL1ABC", "id-2")
        self.assertTrue(wait_for(lambda: ("wl", "bad") in list(self.events.queue)))
        self.assertEqual(self.status("id-2"), "pending")
        self.wl.online = True
        self.sync.wake()
        self.assertTrue(wait_for(lambda: self.status("id-2") == "sent"))

    def test_whole_log_on_demand_without_private_fields(self):
        fakes.send_contact(self.port, "OLD1", "id-3", ts="2026-10-09 12:11:30", band="20", freq="14074000")
        self.assertTrue(wait_for(lambda: self.status("id-3") == "sent"))
        self.sync.send_whole_log()
        self.assertTrue(wait_for(lambda: self.status("db:3") == "sent"))
        self.assertEqual(self.status("db:1"), "dupe")  # déjà reçu par UDP -> Wavelog le reconnaît
        self.assertEqual(self.sent_calls(), ["OLD1", "OLD2", "OLD3"])
        for _call, _when, adif, _sid in self.wl.qsos:
            for private in ("prive@", "rue Privée", "note perso", "RESULT=OK"):
                self.assertNotIn(private, adif)

    def test_bad_key_marks_error(self):
        self.cfg["api_key"] = "wrong"
        self.sync.reconfigure()
        fakes.send_contact(self.port, "EA4XY", "id-4")
        self.assertTrue(wait_for(lambda: self.status("id-4") == "error"))

    def test_port_busy_is_reported(self):
        other = core.Syncer(dict(self.cfg), core.History(), lambda *e: self.events.put(e))
        other.start()
        self.assertTrue(wait_for(lambda: any(e[0] == "hrd" and e[1] is False for e in list(self.events.queue))))
        other.stop()
        other.join(5)


class WavelogTests(unittest.TestCase):
    def test_station_profiles_and_key(self):
        wl = fakes.FakeWavelog()
        try:
            self.assertEqual(core.check_key(wl.url, fakes.KEY), "rw")
            self.assertEqual(core.station_profiles(wl.url, fakes.KEY)[0][0], "7")
            with self.assertRaises(core.WavelogError):
                core.check_key(wl.url, "nope")
        finally:
            wl.close()


if __name__ == "__main__":
    unittest.main()
