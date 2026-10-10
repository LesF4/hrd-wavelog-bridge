"""Démo sans risque : faux Wavelog + faux HRD qui envoie un QSO toutes les 3 s en UDP.

    python tests/demo.py <dossier> [port_udp] [secondes_avant_fin]

Écrit <dossier>/HRDtoWavelog/config.json ; lancer ensuite l'app avec APPDATA=<dossier>
pour qu'elle utilise ce faux environnement.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests import fakes  # noqa: E402

folder = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 12099
os.makedirs(os.path.join(folder, "HRDtoWavelog"), exist_ok=True)
db = os.path.join(folder, "log.hrdsql")
if not os.path.exists(db):
    fakes.make_hrd_db(db, n=3).close()
wl = fakes.FakeWavelog()
with open(os.path.join(folder, "HRDtoWavelog", "config.json"), "w") as f:
    # réception « HRD » sur un port à part : la démo ne doit jamais rien envoyer au vrai HRD (2333)
    json.dump({"udp_port": port, "hrd_in_port": port + 1, "hrd_db": db, "wavelog_url": wl.url,
               "api_key": fakes.KEY, "station_id": "7"}, f)
print("faux Wavelog :", wl.url, "— faux HRD vers UDP", port, flush=True)
time.sleep(4)
calls = [("EA4XY", "Pedro", "7", "7074000"), ("DL1ABC", "Hans", "14", "14074000"),
         ("G4XYZ", "John", "21", "21074000"), ("ON4AA", "Luc", "7", "7078000"),
         ("4S7AB", "Ravi", "14", "14078000")]
for i, (call, name, band, freq) in enumerate(calls):
    fakes.send_contact(port, call, "demo-%d" % i, ts="2026-10-09 12:%02d:00" % i, band=band, freq=freq,
                       name=name, mode="MFSK" if i == 3 else "FT8", submode="JS8" if i == 3 else "")
    print("QSO envoyé par le faux HRD :", call, flush=True)
    time.sleep(3)
time.sleep(int(sys.argv[3]) if len(sys.argv) > 3 else 10)
print("reçus par le faux Wavelog :", [q[0] for q in wl.qsos], flush=True)
