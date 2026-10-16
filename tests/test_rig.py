import os
import queue
import socket
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["APPDATA"] = tempfile.mkdtemp()
from hrdwl import core, rig  # noqa: E402
from tests import fakes  # noqa: E402


def free_tcp_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(cond, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.1)
    return False


class RigClientTests(unittest.TestCase):
    def setUp(self):
        self.fake = fakes.FakeHRDRig()
        self.rig = rig.HRDRig(port=self.fake.port)

    def tearDown(self):
        self.rig.close()
        self.fake.close()

    def test_state(self):
        self.assertEqual(self.rig.state(), ("FTDX-101D-MP", 21074000, "DATA-U", 21300000))
        self.assertIn("[523] get frequency", self.fake.commands)  # bon contexte de radio

    def test_set_frequency_and_guard(self):
        self.rig.set_frequency(14074000)
        self.assertEqual(self.fake.freq, 14074000)
        with self.assertRaises(rig.RigError):
            self.rig.set_frequency(5)  # fréquence absurde : refusée sans rien envoyer
        self.assertFalse(any("frequency-hz 5" in c for c in self.fake.commands))
        self.assertFalse(any("ptt" in c.lower() or "tx" in c.lower().split() for c in self.fake.commands))

    def test_hrd_absent(self):
        with self.assertRaises(rig.RigError):
            rig.HRDRig(port=free_tcp_port()).state()

    def test_modes(self):
        for hrd, wl in (("DATA-U", "USB"), ("DATA-L", "LSB"), ("USB", "USB"), ("LSB", "LSB"), ("CW-U", "CW"),
                        ("CW-L", "CW"), ("RTTY-L", "RTTY"), ("FM", "FM"), ("DATA-FM", "FM"), ("AM", "AM"),
                        ("C4FM", "FM")):
            self.assertEqual(rig.wavelog_mode(hrd), wl, hrd)


class RigBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fake = fakes.FakeHRDRig()
        self.wl = fakes.FakeWavelog()
        self.qsy_port = free_tcp_port()
        self.cfg = dict(core.DEFAULT_CONFIG, wavelog_url=self.wl.url, api_key=fakes.KEY, station_id="7",
                        rig_port=self.fake.port, qsy_port=self.qsy_port)
        self.events = queue.Queue()
        self.bridge = rig.RigBridge(self.cfg, lambda p: core.send_radio(self.cfg["wavelog_url"], p),
                                    lambda *e: self.events.put(e), interval=0.2, keepalive=60)
        self.bridge.start()

    def tearDown(self):
        self.bridge.stop()
        self.fake.close()
        self.wl.close()

    def qsy(self, path):
        return urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.qsy_port, path), timeout=5)

    def test_radio_state_reaches_wavelog_and_follows_changes(self):
        self.assertTrue(wait_for(lambda: len(self.wl.radio_updates) >= 1))
        first = self.wl.radio_updates[0]
        self.assertEqual((first["radio"], first["frequency"], first["mode"], first["frequency_rx"]),
                         ("FTDX-101D-MP", 21074000, "USB", 21300000))
        self.assertEqual(first["cat_url"], "http://127.0.0.1:%d" % self.qsy_port)
        self.assertEqual(first["key"], fakes.KEY)
        time.sleep(1)
        self.assertEqual(len(self.wl.radio_updates), 1)  # rien ne change : pas de renvoi inutile
        self.fake.freq = 7074000                           # on tourne le bouton
        self.assertTrue(wait_for(lambda: self.wl.radio_updates[-1]["frequency"] == 7074000))
        self.assertIn(("rig", "ok", "FTDX-101D-MP 7.074 MHz DATA-U"), list(self.events.queue))

    def test_qsy_from_wavelog_tunes_the_radio(self):
        self.assertTrue(wait_for(lambda: len(self.wl.radio_updates) >= 1))
        r = self.qsy("/14025000/cw")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
        self.assertEqual(self.fake.freq, 14025000)
        self.assertTrue(wait_for(lambda: self.wl.radio_updates[-1]["frequency"] == 14025000))

    def test_qsy_preflight_and_bad_requests(self):
        self.assertTrue(wait_for(lambda: self.bridge.qsy is not None and self.bridge.qsy.httpd is not None))
        req = urllib.request.Request("http://127.0.0.1:%d/7074000/usb" % self.qsy_port, method="OPTIONS")
        r = urllib.request.urlopen(req, timeout=5)
        self.assertEqual(r.headers["Access-Control-Allow-Private-Network"], "true")
        with self.assertRaises(urllib.error.HTTPError):
            self.qsy("/n-importe-quoi")
        with self.assertRaises(urllib.error.HTTPError):
            self.qsy("/12/usb")  # fréquence absurde
        self.assertEqual(self.fake.freq, 21074000)

    def test_qsy_disabled(self):
        self.cfg["qsy_enabled"] = False
        self.assertTrue(wait_for(lambda: self.bridge.qsy is not None and self.bridge.qsy.httpd is not None))
        with self.assertRaises(urllib.error.HTTPError):
            self.qsy("/7074000/usb")
        self.assertEqual(self.fake.freq, 21074000)


class RigBridgeWithoutHRDTests(unittest.TestCase):
    def test_hrd_closed_is_reported_without_crash(self):
        events = queue.Queue()
        cfg = dict(core.DEFAULT_CONFIG, wavelog_url="http://127.0.0.1:9", api_key="k", station_id="7",
                   rig_port=free_tcp_port(), qsy_port=free_tcp_port())
        bridge = rig.RigBridge(cfg, lambda p: False, lambda *e: events.put(e), interval=0.2)
        bridge.start()
        try:
            self.assertTrue(wait_for(lambda: any(e[0] == "rig" and e[1] == "off" for e in list(events.queue))))
            self.assertTrue(bridge.is_alive())
        finally:
            bridge.stop()


if __name__ == "__main__":
    unittest.main()
