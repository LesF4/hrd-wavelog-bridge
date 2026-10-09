"""Capture la fenêtre de l'app pour la doc : python packaging/screenshot.py fr|en sortie.png [délai_ms]

À lancer avec APPDATA pointant vers le dossier de tests/demo.py (voir packaging/README.md).
"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PIL import ImageGrab  # noqa: E402

from hrdwl import app  # noqa: E402

lang, out = sys.argv[1], sys.argv[2]
delay = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
root = tk.Tk()
a = app.App(root)
a.cfg["language"] = lang
app.set_language(lang)
a.rebuild_ui()
root.attributes("-topmost", True)


def shot():
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height()), all_screens=True).save(out)
    a.quit()


root.after(delay, shot)
root.mainloop()
