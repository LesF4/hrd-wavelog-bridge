"""Vérification de l'interface (fenêtre principale, comparaison, réglages) avec un faux environnement.

    python tests/ui_check.py <dossier_vide> [capture_comparaison.png]

Aucune donnée réelle n'est utilisée : faux Wavelog, faux log HRD, APPDATA du dossier donné.
"""
import json
import os
import socket
import sys
import tkinter as tk

folder = sys.argv[1]
os.makedirs(os.path.join(folder, "HRDtoWavelog"), exist_ok=True)
os.environ["APPDATA"] = folder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from hrdwl import app  # noqa: E402
from tests import fakes  # noqa: E402


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


db = os.path.join(folder, "log.hrdsql")
if not os.path.exists(db):
    fakes.make_hrd_db(db, n=3).close()
wl = fakes.FakeWavelog()
wl.add_external("OLD1", date="20261009", time_on="121130", band="20m", freq="14.074", mode="MFSK")
for i, call in enumerate(("F5AAA", "F5BBB", "F6CCC")):
    wl.add_external(call, date="20260221", time_on="08%02d00" % i, band="40m", freq="7.080", mode="SSB")
with open(os.path.join(folder, "HRDtoWavelog", "config.json"), "w") as f:
    json.dump({"udp_port": free_udp_port(), "hrd_in_port": free_udp_port(), "hrd_db": db,
               "wavelog_url": wl.url, "api_key": fakes.KEY, "station_id": "7", "language": "fr"}, f)

app.refresh_autostart = lambda: None  # ne pas toucher au démarrage auto réel
root = tk.Tk()
a = app.App(root)
errors = []
root.report_callback_exception = lambda *exc: errors.append(exc[1])


def step_compare():
    a.compare_logs()


def step_check():
    dialogs = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    print("fenêtres ouvertes :", [d.title() for d in dialogs])
    if len(sys.argv) > 2 and dialogs:
        from PIL import ImageGrab
        d = dialogs[0]
        d.attributes("-topmost", True)
        d.update()
        x, y = d.winfo_rootx(), d.winfo_rooty()
        ImageGrab.grab((x, y, x + d.winfo_width(), y + d.winfo_height()), all_screens=True).save(sys.argv[2])
    for d in dialogs:
        d.destroy()
    a.open_settings()


def step_settings():
    win = a._settings_win
    win.update()
    labels = [w.cget("text") for w in win.winfo_children()[0].winfo_children() if isinstance(w, tk.ttk.Label)]
    print("réglages, sections :", [s for s in labels if s in ("HRD Logbook", "Wavelog", "Wavelog → HRD", "Options")])
    win.destroy()
    print("erreurs d'interface :", errors or "aucune")
    a.quit()


root.after(1500, step_compare)
root.after(7000, step_check)
root.after(10000, step_settings)
root.mainloop()
wl.close()
