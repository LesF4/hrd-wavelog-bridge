"""Interface graphique (tkinter) du pont HRD Logbook -> Wavelog."""

import os
import queue
import sys
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from . import core
from .i18n import set_language, t

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:  # l'app fonctionne aussi sans icône de notification
    pystray = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MUTEX = "Global\\HRDtoWavelog_single_instance"
GREEN, RED, ORANGE = "#1a7f37", "#c62828", "#b26a00"


# --------------------------------------------------------------------------- utilitaires Windows

def make_icon_image(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 6, fill=(46, 125, 50, 255))
    try:
        big = ImageFont.truetype("arialbd.ttf", int(size * 0.34))
        small = ImageFont.truetype("arialbd.ttf", int(size * 0.26))
    except OSError:
        big = small = ImageFont.load_default()
    d.text((size / 2, size * 0.35), "HRD", font=big, fill="white", anchor="mm")
    d.text((size / 2, size * 0.73), "WL", font=small, fill=(255, 214, 0, 255), anchor="mm")
    return img


def single_instance():
    if sys.platform != "win32":
        return True
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX)
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def autostart_command():
    if getattr(sys, "frozen", False):
        return '"%s" --minimized' % sys.executable
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "HRDtoWavelog.pyw"))
    return '"%s" "%s" --minimized' % (pythonw, script)


def get_autostart():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, core.APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, core.APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, core.APP_NAME)
            except FileNotFoundError:
                pass


def refresh_autostart():
    """Si le démarrage auto est actif, le fait pointer vers l'exe actuel (après une mise à jour)."""
    try:
        if get_autostart():
            set_autostart(True)
    except OSError:
        pass


# --------------------------------------------------------------------------- application

class App:
    def __init__(self, root, start_minimized=False):
        self.root = root
        self.cfg = core.load_config()
        set_language(self.cfg["language"])
        self.history = core.History()
        self.events = queue.Queue()
        self.tray = None
        self.hrd_state = (None, "")
        self.wl_state = None
        self.tray_hint_shown = False
        self.refresh_scheduled = False

        root.title("%s  v%s" % (core.APP_TITLE, core.APP_VERSION))
        root.geometry("920x540")
        root.minsize(720, 380)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        if pystray:
            self._icon_img = make_icon_image(64)
            self._tk_icon = ImageTk.PhotoImage(self._icon_img)
            root.iconphoto(True, self._tk_icon)

        self.build_ui()
        self.refresh_tree()
        self.start_tray()
        refresh_autostart()

        self.log(t("log_start", port=self.cfg["udp_port"]))
        if not core.is_configured(self.cfg):
            self.log(t("log_need_setup"))
        self.syncer = core.Syncer(self.cfg, self.history, lambda *ev: self.events.put(ev))
        self.syncer.start()
        root.after(200, self.poll_events)
        if start_minimized or self.cfg["start_minimized"]:
            root.after(100, self.hide)
        elif not core.is_configured(self.cfg):
            root.after(600, self.open_settings)

    # ----------------------------------------------------------------- UI
    def build_ui(self):
        ttk.Style().configure("Treeview", rowheight=22)

        top = ttk.Frame(self.root, padding=(10, 8))
        top.pack(fill="x")
        self.hrd_lbl = tk.Label(top, text="● HRD Logbook …", font=("Segoe UI", 10, "bold"), fg=ORANGE)
        self.hrd_lbl.pack(side="left")
        self.wl_lbl = tk.Label(top, text="● Wavelog …", font=("Segoe UI", 10, "bold"), fg=ORANGE)
        self.wl_lbl.pack(side="left", padx=(24, 0))
        ttk.Button(top, text=t("btn_about"), command=self.about).pack(side="right")
        ttk.Button(top, text=t("btn_settings"), command=self.open_settings).pack(side="right", padx=6)

        cols = [("utc", 120), ("call", 95), ("band", 55), ("mode", 70), ("freq", 85),
                ("status", 150), ("msg", 200)]
        frame = ttk.Frame(self.root, padding=(10, 0))
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in cols], show="headings", selectmode="extended")
        for cid, width in cols:
            self.tree.heading(cid, text=t("col_" + cid))
            self.tree.column(cid, width=width, anchor="w", stretch=cid == "msg")
        for tag, color in (("sent", GREEN), ("dupe", GREEN), ("pending", ORANGE), ("error", RED)):
            self.tree.tag_configure(tag, foreground=color)
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        bar = ttk.Frame(self.root, padding=(10, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text=t("btn_resend"), command=self.resend_selected).pack(side="left")
        ttk.Button(bar, text=t("btn_history"), command=self.send_whole_log).pack(side="left", padx=6)
        ttk.Button(bar, text=t("btn_open_folder"),
                   command=lambda: os.startfile(core.data_dir())).pack(side="left")
        ttk.Button(bar, text=t("btn_quit"), command=self.quit).pack(side="right")

        self.logbox = tk.Text(self.root, height=6, state="disabled", font=("Consolas", 9),
                              bg="#f6f6f6", relief="flat", padx=6, pady=4)
        self.logbox.pack(fill="x", padx=10, pady=(0, 10))

    def rebuild_ui(self):
        old_log = self.logbox.get("1.0", "end-1c")
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        self.build_ui()
        self.logbox.configure(state="normal")
        self.logbox.insert("end", old_log + ("\n" if old_log else ""))
        self.logbox.configure(state="disabled")
        self.refresh_tree()
        self.set_indicators()

    def log(self, text):
        line = "%s  %s\n" % (datetime.now().strftime("%H:%M:%S"), text)
        self.logbox.configure(state="normal")
        self.logbox.insert("end", line)
        lines = int(self.logbox.index("end-1c").split(".")[0])
        if lines > 300:
            self.logbox.delete("1.0", "%d.0" % (lines - 300))
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    def refresh_tree(self):
        self.refresh_scheduled = False
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for item in self.history.snapshot()[-1000:]:
            f = item["fields"]
            when, call = core.qso_label(f)
            mode = f.get("SUBMODE") and "%s/%s" % (f.get("MODE", ""), f["SUBMODE"]) or f.get("MODE", "")
            iid = str(item["hrd_key"])
            self.tree.insert("", 0, iid=iid, tags=(item["status"],), values=(
                when, call, f.get("BAND", ""), mode, f.get("FREQ", ""),
                t("status_" + item["status"]), item.get("message", "")))
            if iid in sel:
                self.tree.selection_add(iid)

    def schedule_refresh(self):
        if not self.refresh_scheduled:
            self.refresh_scheduled = True
            self.root.after(700, self.refresh_tree)

    def set_indicators(self):
        ok, info = self.hrd_state
        if ok:
            self.hrd_lbl.config(text=t("hrd_listen", port=info), fg=GREEN)
        elif ok is False:
            self.hrd_lbl.config(text=t("hrd_busy"), fg=RED)
        if self.wl_state == "ok":
            self.wl_lbl.config(text=t("wl_ok"), fg=GREEN)
        elif self.wl_state == "bad":
            self.wl_lbl.config(text=t("wl_bad"), fg=RED)
        elif self.wl_state == "unset":
            self.wl_lbl.config(text=t("wl_unset"), fg=ORANGE)
        if self.tray:
            self.tray.title = "HRD → Wavelog — HRD %s — Wavelog %s" % (
                "✔" if ok else "✖", "✔" if self.wl_state == "ok" else "✖")

    def about(self):
        messagebox.showinfo(core.APP_TITLE, t("about_text", version=core.APP_VERSION, url=core.APP_URL))

    # ----------------------------------------------------------------- événements du moteur
    def poll_events(self):
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "log":
                    self.log(ev[1])
                elif kind == "refresh":
                    self.schedule_refresh()
                elif kind == "hrd":
                    self.hrd_state = (ev[1], ev[2])
                    if not ev[1]:
                        self.log(t("log_listen_error", port=self.cfg["udp_port"], err=ev[2]))
                    self.set_indicators()
                elif kind == "wl":
                    self.wl_state = ev[1]
                    self.set_indicators()
                elif kind == "sent":
                    self.notify(t("notify_sent", call=ev[1]))
                elif kind == "show":
                    self.show()
                elif kind == "quit":
                    self.quit()
                    return
        except queue.Empty:
            pass
        self.root.after(200, self.poll_events)

    def resend_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(core.APP_TITLE, t("resend_none"))
            return
        self.syncer.resend(sel)

    def hrd_log_count(self):
        try:
            return core.HRDReader(self.cfg["hrd_db"] or core.default_hrd_db()).count()
        except Exception:
            return "?"

    def send_whole_log(self):
        if messagebox.askyesno(core.APP_TITLE, t("history_confirm", n=self.hrd_log_count())):
            self.syncer.send_whole_log()

    # ----------------------------------------------------------------- réglages
    def open_settings(self):
        if getattr(self, "_settings_win", None) and self._settings_win.winfo_exists():
            self._settings_win.lift()
            return
        was_configured = core.is_configured(self.cfg)
        win = self._settings_win = tk.Toplevel(self.root)
        win.title(t("settings_title"))
        win.transient(self.root)
        win.resizable(False, False)
        frm = ttk.Frame(win, padding=14)
        frm.pack()
        bold = ("Segoe UI", 9, "bold")

        logbooks = [(title, path) for title, dbtype, path in core.find_hrd_logbooks()
                    if "sqlite" in dbtype.lower()]
        db_var = tk.StringVar(value=self.cfg["hrd_db"] or core.default_hrd_db())
        port_var = tk.StringVar(value=str(self.cfg["udp_port"]))
        url_var = tk.StringVar(value=self.cfg["wavelog_url"])
        key_var = tk.StringVar(value=self.cfg["api_key"])
        stations = []  # (id, libellé)
        station_var = tk.StringVar()
        info_var = tk.StringVar()
        langs = {"auto": t("lang_auto"), "fr": "Français", "en": "English"}
        lang_var = tk.StringVar(value=langs.get(self.cfg["language"], langs["auto"]))
        autostart_var = tk.BooleanVar(value=get_autostart())
        minimized_var = tk.BooleanVar(value=self.cfg["start_minimized"])
        tray_var = tk.BooleanVar(value=self.cfg["close_to_tray"])

        r = 0
        ttk.Label(frm, text=t("s_hrd"), font=bold).grid(row=r, column=0, columnspan=3, sticky="w")
        r += 1
        ttk.Label(frm, text=t("s_udp_port")).grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=port_var, width=8).grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Label(frm, text=t("s_udp_hint"), foreground="#666").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1
        ttk.Label(frm, text=t("s_logbook")).grid(row=r, column=0, sticky="w", pady=(6, 0))
        db_combo = ttk.Combobox(frm, textvariable=db_var, width=58,
                                values=[p for _t, p in logbooks])
        db_combo.grid(row=r, column=1, sticky="w", pady=(6, 0))

        def browse():
            p = filedialog.askopenfilename(parent=win, filetypes=[("HRD Logbook", "*.hrdsql"), ("*", "*.*")])
            if p:
                db_var.set(os.path.normpath(p))
        ttk.Button(frm, text=t("s_browse"), command=browse).grid(row=r, column=2, padx=(6, 0), pady=(6, 0))
        r += 1
        ttk.Label(frm, text=t("s_logbook_hint"), foreground="#666").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        ttk.Label(frm, text=t("s_wavelog"), font=bold).grid(row=r, column=0, columnspan=3, sticky="w", pady=(14, 0))
        r += 1
        ttk.Label(frm, text=t("s_url")).grid(row=r, column=0, sticky="w")
        ttk.Entry(frm, textvariable=url_var, width=60).grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1
        ttk.Label(frm, text=t("s_url_hint"), foreground="#666").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1
        ttk.Label(frm, text=t("s_key")).grid(row=r, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(frm, textvariable=key_var, width=60, show="•").grid(row=r, column=1, columnspan=2,
                                                                       sticky="w", pady=(6, 0))
        r += 1
        ttk.Label(frm, text=t("s_key_hint"), foreground="#666").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1
        ttk.Label(frm, text=t("s_station")).grid(row=r, column=0, sticky="w", pady=(6, 0))
        station_combo = ttk.Combobox(frm, textvariable=station_var, state="readonly", width=58)
        station_combo.grid(row=r, column=1, sticky="w", pady=(6, 0))
        r += 1

        def load_stations(quiet=False):
            info_var.set("…")
            win.update_idletasks()
            try:
                rights = core.check_key(url_var.get(), key_var.get())
                found = core.station_profiles(url_var.get(), key_var.get())
            except core.WavelogError as e:
                info_var.set("✖ %s" % e)
                return
            stations[:] = [(sid, label) for sid, label, _active in found]
            station_combo["values"] = [label for _sid, label in stations]
            current = str(self.cfg["station_id"])
            choice = next((lbl for sid, lbl in stations if sid == current), None)
            if choice is None:
                choice = next((lbl for sid, lbl, active in found if active), stations[0][1] if stations else "")
            station_var.set(choice)
            info_var.set(("✔ " + t("s_loaded", rights=rights)) if "w" in rights else ("✖ " + t("s_readonly")))

        ttk.Button(frm, text=t("s_load"), command=load_stations).grid(row=r, column=1, sticky="w", pady=(6, 0))
        r += 1
        ttk.Label(frm, textvariable=info_var, wraplength=480).grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        ttk.Label(frm, text=t("s_options"), font=bold).grid(row=r, column=0, columnspan=3, sticky="w", pady=(14, 0))
        r += 1
        ttk.Label(frm, text=t("s_language")).grid(row=r, column=0, sticky="w")
        ttk.Combobox(frm, textvariable=lang_var, state="readonly", width=34,
                     values=list(langs.values())).grid(row=r, column=1, sticky="w")
        r += 1
        for text, var in ((t("s_autostart"), autostart_var), (t("s_minimized"), minimized_var),
                          (t("s_tray"), tray_var)):
            ttk.Checkbutton(frm, text=text, variable=var).grid(row=r, column=0, columnspan=3, sticky="w")
            r += 1

        if self.cfg["wavelog_url"] and self.cfg["api_key"]:
            win.after(100, load_stations)

        def save():
            sid = next((s for s, lbl in stations if lbl == station_var.get()), "")
            if not sid and stations == [] and self.cfg["station_id"] and \
                    url_var.get() == self.cfg["wavelog_url"] and key_var.get() == self.cfg["api_key"]:
                sid = self.cfg["station_id"]  # stations pas rechargées : on garde la station actuelle
            if not (url_var.get().strip() and key_var.get().strip() and sid):
                messagebox.showerror(t("settings_title"), t("err_missing"), parent=win)
                return
            try:
                udp_port = int(port_var.get())
            except ValueError:
                messagebox.showerror(t("settings_title"), t("err_port"), parent=win)
                return
            old_lang = self.cfg["language"]
            self.cfg.update(
                udp_port=udp_port, hrd_db=db_var.get().strip(), wavelog_url=url_var.get().strip(),
                api_key=key_var.get().strip(), station_id=sid,
                language=next(k for k, lbl in langs.items() if lbl == lang_var.get()),
                start_minimized=minimized_var.get(), close_to_tray=tray_var.get())
            core.save_config(self.cfg)
            try:
                if autostart_var.get() != get_autostart():
                    set_autostart(autostart_var.get())
            except OSError as e:
                messagebox.showerror(t("settings_title"), t("err_autostart", err=e), parent=win)
            win.destroy()
            if self.cfg["language"] != old_lang:
                set_language(self.cfg["language"])
                self.rebuild_ui()
                self.restart_tray()
            self.log(t("log_settings_saved"))
            self.syncer.reconfigure()
            if not was_configured:
                if messagebox.askyesno(core.APP_TITLE, t("first_setup_history", n=self.hrd_log_count())):
                    self.syncer.send_whole_log()
            self.syncer.wake()

        btns = ttk.Frame(frm)
        btns.grid(row=r, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(btns, text=t("s_cancel"), command=win.destroy).pack(side="right")
        ttk.Button(btns, text=t("s_save"), command=save).pack(side="right", padx=6)
        win.grab_set()

    # ----------------------------------------------------------------- zone de notification
    def start_tray(self):
        if not pystray:
            return
        menu = pystray.Menu(
            pystray.MenuItem(t("tray_open"), lambda: self.events.put(("show",)), default=True),
            pystray.MenuItem(t("tray_quit"), lambda: self.events.put(("quit",))))
        self.tray = pystray.Icon(core.APP_NAME, self._icon_img, "HRD → Wavelog", menu)
        self.tray.run_detached()

    def restart_tray(self):
        if self.tray:
            self.tray.stop()
            self.tray = None
            self.start_tray()

    def notify(self, text):
        if self.tray and not self.root.winfo_viewable():
            try:
                self.tray.notify(text, "HRD → Wavelog")
            except Exception:
                pass

    def hide(self):
        if self.tray:
            self.root.withdraw()
        else:
            self.root.iconify()

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_close(self):
        if self.cfg["close_to_tray"] and self.tray:
            self.hide()
            if not self.tray_hint_shown:
                self.tray_hint_shown = True
                self.tray.notify(t("tray_hint"), "HRD → Wavelog")
        else:
            self.quit()

    def quit(self):
        self.syncer.stop()
        if self.tray:
            self.tray.stop()
        self.root.destroy()


def main():
    if not single_instance():
        set_language(core.load_config()["language"])
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(core.APP_TITLE, t("already_running"))
        return
    root = tk.Tk()
    App(root, start_minimized="--minimized" in sys.argv)
    root.mainloop()
