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

    def test_qso_index_matching(self):
        idx = core.QsoIndex([{"CALL": "K1AB", "BAND": "20m", "QSO_DATE": "20261010", "TIME_ON": "120000",
                              "MODE": "PSK31"}])
        same = {"CALL": "k1ab", "BAND": "20M", "QSO_DATE": "20261010", "TIME_ON": "121400", "MODE": "PSK"}
        self.assertTrue(idx.find(same))  # mode écrit autrement, 14 min d'écart : même QSO
        self.assertFalse(idx.find(dict(same, TIME_ON="121600")))  # 16 min : autre QSO
        self.assertFalse(idx.find(dict(same, BAND="40m")))
        self.assertTrue(idx.find(same, consume=True))
        self.assertFalse(idx.find(same))  # déjà apparié

    def test_parse_adif_and_fields_for_hrd(self):
        qsos = core.parse_adif("export <eoh>\n<CALL:4>K1AB <BAND:3>20M <QSO_DATE:8>20261010 "
                               "<TIME_ON:4>1200 <APP_X:1>y <EMAIL:5>a@b.c <eor>\n<call:2>F4 <eor>")
        self.assertEqual([q["CALL"] for q in qsos], ["K1AB", "F4"])
        self.assertEqual(core.fields_for_hrd(qsos[0]),
                         {"CALL": "K1AB", "QSO_DATE": "20261010", "TIME_ON": "1200", "BAND": "20m"})

    def test_history_keys_stay_unique(self):
        h = core.History()
        h.items = []
        f = {"CALL": "G0ABC", "QSO_DATE": "20250309", "TIME_ON": "142215"}
        keys = [h.add("cmp:x", f, "pending")["hrd_key"] for _ in range(3)]
        self.assertEqual(keys, ["cmp:x", "cmp:x#2", "cmp:x#3"])

    def test_history_with_duplicate_keys_is_repaired_on_load(self):
        h = core.History()
        f = {"CALL": "G0ABC", "QSO_DATE": "20250309", "TIME_ON": "142215"}
        h.items = [{"hrd_key": "cmp:x", "fields": f, "status": "error", "message": "", "dir": "up"}] * 2
        h.save()
        self.assertEqual([i["hrd_key"] for i in core.History().items], ["cmp:x", "cmp:x#2"])

    def test_same_keys_in_all_languages(self):
        self.assertEqual(set(i18n.TEXTS["fr"]), set(i18n.TEXTS["en"]))


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.wl = fakes.FakeWavelog()
        self.db = os.path.join(tempfile.mkdtemp(), "log.hrdsql")
        self.con = fakes.make_hrd_db(self.db, n=3)
        self.port = free_udp_port()
        # port de réception « HRD » libre par défaut : surtout ne jamais viser le vrai HRD (2333)
        self.cfg = dict(core.DEFAULT_CONFIG, udp_port=self.port, hrd_in_port=free_udp_port(), hrd_db=self.db,
                        api_key=fakes.KEY, station_id="7", wavelog_url=self.wl.url + "/index.php/logbook")
        self.history = core.History()
        self.history.items = []
        self.events = queue.Queue()
        self.sync = core.Syncer(self.cfg, self.history, lambda *e: self.events.put(e))
        self.sync.RETRY_SECONDS = 0.3
        self.sync.DOWNLOAD_SECONDS = 0
        self.receiver = None
        if self._testMethodName == "test_wavelog_qso_copied_to_hrd_without_boomerang":
            self.wl.add_external("OLDWL", time_on="080000")  # déjà dans Wavelog avant le démarrage
        if self._testMethodName == "test_catch_up_qsos_logged_while_app_was_closed":
            # dernier QSO reçu de HRD avant la fermeture de l'app : OLD3 (12:13:30), déjà envoyé
            old3 = {"CALL": "OLD3", "QSO_DATE": "20261009", "TIME_ON": "121330", "BAND": "20m"}
            self.history.add("id-old3", old3, "sent")
            fakes.add_qso(self.con, 4, "MISSED1", minute=40)  # enregistrés pendant que l'app était fermée
            fakes.add_qso(self.con, 5, "MISSED2", minute=45)
        self.sync.start()
        self.assertTrue(wait_for(lambda: ("hrd", True, self.port) in list(self.events.queue)))

    def tearDown(self):
        self.sync.stop()
        self.sync.join(5)
        self.assertFalse(self.sync.is_alive())
        if self.receiver:
            self.receiver.close()
        self.con.close()
        self.wl.close()

    def start_hrd(self, echo=True, crash_after=None):
        """Démarre le faux HRD (réception UDP, enregistre dans le faux log) et y dirige l'app."""
        self.receiver = fakes.FakeHRDReceiver(echo_port=self.port if echo else None, db_path=self.db,
                                              crash_after=crash_after)
        self.cfg["hrd_in_port"] = self.receiver.port

    @staticmethod
    def qso(call, minute):
        return {"CALL": call, "QSO_DATE": "20260221", "TIME_ON": "08%02d00" % minute, "BAND": "40m",
                "FREQ": "7.080000", "MODE": "SSB"}

    def test_catch_up_qsos_logged_while_app_was_closed(self):
        self.assertTrue(wait_for(lambda: self.sent_calls() == ["MISSED1", "MISSED2"]))
        self.assertIn(("log", core.t("log_catch_up", n=2)), list(self.events.queue))
        time.sleep(1)
        self.assertEqual(self.sent_calls(), ["MISSED1", "MISSED2"])  # OLD1 / OLD2 plus anciens : pas renvoyés

    def test_no_catch_up_on_first_start(self):
        time.sleep(1.5)  # historique vide : on ne renvoie pas tout le log
        self.assertEqual(self.wl.qsos, [])

    def test_bulk_to_hrd_one_by_one_with_progress(self):
        self.cfg["download_enabled"] = False
        self.start_hrd(echo=True)
        old3 = {"CALL": "OLD3", "QSO_DATE": "20261009", "TIME_ON": "121330", "BAND": "20m"}  # déjà dans HRD
        self.sync.add_missing([self.qso("REF1", 0), old3, self.qso("REF2", 5), self.qso("REF3", 9)], [])
        self.assertTrue(wait_for(lambda: [i["status"] for i in self.items("down")] == ["imported"] * 4, 30))
        self.assertEqual(self.receiver.calls(), ["REF1", "REF2", "REF3"])  # OLD3 n'est pas renvoyé
        self.assertEqual(self.history.find("wl:" + core.qso_sig(old3))["message"], core.t("msg_already_in_hrd"))
        progress = [e for e in list(self.events.queue) if e[0] == "progress" and e[1] == "down"]
        self.assertEqual([e[2] for e in progress if e[2]], [1, 2, 3, 4])
        self.assertEqual(progress[-1], ("progress", "down", None, None))
        time.sleep(1)
        self.assertEqual(self.items("up"), [])  # les échos de HRD ne repartent pas vers Wavelog

    def test_hrd_crash_stops_and_flags_the_qso(self):
        self.cfg["download_enabled"] = False
        self.start_hrd(echo=False, crash_after=2)  # HRD plante à la réception du 2e QSO
        self.sync.add_missing([self.qso("REF1", 0), self.qso("REF2", 5), self.qso("REF3", 9)], [])
        self.assertTrue(wait_for(lambda: [i["status"] for i in self.items("down")] == ["imported", "error",
                                                                                         "pending"], 30))
        self.assertEqual(self.history.find("wl:" + core.qso_sig(self.qso("REF2", 5)))["message"],
                         core.t("msg_hrd_closed_after"))
        time.sleep(1.5)
        self.assertEqual(self.receiver.calls(), ["REF1", "REF2"])  # rien n'est renvoyé en boucle

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

    def items(self, direction):
        return [i for i in self.history.snapshot() if i.get("dir", "up") == direction]

    def test_wavelog_qso_copied_to_hrd_without_boomerang(self):
        self.assertTrue(wait_for(lambda: self.cfg["wl_last_id"] == 1))  # point de départ : OLDWL pas recopié
        self.start_hrd(echo=True)
        self.wl.add_external("F5CLUB", time_on="093000")  # QSO saisi au radio-club
        self.assertTrue(wait_for(lambda: self.receiver.calls() == ["F5CLUB"]))
        self.assertTrue(wait_for(lambda: [i["status"] for i in self.items("down")] == ["imported"]))
        adif = self.receiver.received[0]
        self.assertIn("<band:3>40m", adif)
        self.assertNotIn("app_wavelog", adif.lower())  # seulement les champs du QSO
        time.sleep(1.5)  # HRD renvoie l'écho : il ne doit ni repartir vers Wavelog, ni revenir dans HRD
        self.assertEqual(self.items("up"), [])
        self.assertEqual(self.receiver.calls(), ["F5CLUB"])
        self.assertEqual(len(self.wl.qsos), 2)

    def test_qso_from_hrd_is_not_sent_back_to_hrd(self):
        self.assertTrue(wait_for(lambda: self.cfg["wl_last_id"] is not None))
        self.start_hrd(echo=False)
        fakes.send_contact(self.port, "EA4XY", "id-5", ts="2026-10-10 10:00:00")
        self.assertTrue(wait_for(lambda: self.status("id-5") == "sent"))
        time.sleep(1.5)  # plusieurs récupérations Wavelog -> HRD ont eu lieu
        self.assertEqual(self.receiver.calls(), [])
        self.assertEqual(self.items("down"), [])

    def test_hrd_closed_then_opened(self):
        self.assertTrue(wait_for(lambda: self.cfg["wl_last_id"] is not None))
        self.wl.add_external("F5PORT", time_on="110000")
        self.assertTrue(wait_for(lambda: [i["status"] for i in self.items("down")] == ["pending"]))
        self.start_hrd(echo=False)  # HRD vient d'être ouvert
        self.assertTrue(wait_for(lambda: self.receiver.calls() == ["F5PORT"]))
        self.assertTrue(wait_for(lambda: [i["status"] for i in self.items("down")] == ["imported"]))

    def test_wavelog_qso_already_in_hrd_is_not_duplicated(self):
        self.assertTrue(wait_for(lambda: self.cfg["wl_last_id"] is not None))
        self.start_hrd(echo=False)
        # import ADIF manuel dans Wavelog d'un QSO qui est déjà dans le log HRD (OLD2 à 12:12:30)
        self.wl.add_external("OLD2", date="20261009", time_on="121230", band="20m", freq="14.074")
        self.wl.add_external("F5NEW", time_on="130000")
        self.assertTrue(wait_for(lambda: self.receiver.calls() == ["F5NEW"]))
        time.sleep(1)
        self.assertEqual(self.receiver.calls(), ["F5NEW"])

    def test_compare_and_fill_both_sides(self):
        self.cfg["download_enabled"] = False  # on teste la comparaison seule
        # Wavelog : OLD1 (identique à HRD, mode écrit autrement) + REFSSB (concours jamais entré dans HRD)
        self.wl.add_external("OLD1", date="20261009", time_on="121130", band="20m", freq="14.074", mode="MFSK")
        self.wl.add_external("REFSSB", date="20260221", time_on="080000", band="40m", freq="7.080", mode="SSB")
        self.sync.compare()
        self.assertTrue(wait_for(lambda: any(e[0] == "compare" for e in list(self.events.queue))))
        _kind, wl_only, hrd_only = next(e for e in list(self.events.queue) if e[0] == "compare")
        self.assertEqual([f["CALL"] for f in wl_only], ["REFSSB"])
        self.assertEqual(sorted(f["CALL"] for f in hrd_only), ["OLD2", "OLD3"])
        for f in hrd_only:  # rien de personnel ne sort du log HRD
            self.assertFalse({"EMAIL", "ADDRESS", "NOTES", "LAT"} & set(f))
        self.start_hrd(echo=True)
        self.sync.add_missing(wl_only, hrd_only)
        self.assertTrue(wait_for(lambda: self.receiver.calls() == ["REFSSB"]))
        self.assertTrue(wait_for(lambda: self.sent_calls() == ["OLD1", "OLD2", "OLD3", "REFSSB"]))
        time.sleep(1.5)  # ni boomerang, ni doublon
        self.assertEqual(self.receiver.calls(), ["REFSSB"])
        self.assertEqual(len(self.wl.qsos), 4)
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
