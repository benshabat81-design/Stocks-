#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Tracker Pro
=================
אפליקציית מעקב תיק מניות מקצועית (Wall Street - NYSE/NASDAQ).
כלי לניהול השקעות אישי - כל הנתונים מוזנים ידנית, ללא APIs חיצוניים.

מבנה:
    מודול 1: מעקב תיק (Portfolio Tracker)
    מודול 2: ניתוח מניה (Stock Analysis)
    מודול 3: יומן מסחר (Trade Journal)
    מודול 4: גרפים (Charts)

הרצה:
    python stock_tracker.py

דרישות:
    Python 3.x, Tkinter, Matplotlib, Pandas
"""

import os
import json
import datetime
from collections import Counter

import tkinter as tk
from tkinter import ttk, messagebox

import pandas as pd

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# ===================================================================
#  הגדרות עיצוב וקבועים (Theme & Constants)
# ===================================================================
COLORS = {
    "bg":      "#1E2A3A",   # רקע ראשי
    "surface": "#2C3E50",   # משטח (כרטיסים/טבלאות)
    "accent":  "#2980B9",   # כחול
    "green":   "#27AE60",   # ירוק (רווח)
    "red":     "#E74C3C",   # אדום (הפסד)
    "text":    "#ECF0F1",   # טקסט בהיר
    "muted":   "#95A5A6",   # טקסט עמום
    "border":  "#34495E",   # גבול
    "input":   "#34495E",   # רקע שדות קלט
}

FONT_FAMILY = "Arial"
FONT_NORMAL = (FONT_FAMILY, 11)
FONT_SMALL = (FONT_FAMILY, 10)
FONT_BOLD = (FONT_FAMILY, 11, "bold")
FONT_TITLE = (FONT_FAMILY, 14, "bold")
FONT_CARD_VALUE = (FONT_FAMILY, 18, "bold")
FONT_CARD_LABEL = (FONT_FAMILY, 10)

# ספי התראות
ALERT_TAKE_PROFIT = 15.0    # רווח מעל 15%
ALERT_STOP_LOSS = -8.0      # הפסד מתחת ל-8%-
ALERT_CONCENTRATION = 25.0  # ריכוז מעל 25%

# קבצי נתונים (באותה תיקייה של הסקריפט)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
ANALYSES_FILE = os.path.join(BASE_DIR, "analyses.json")
JOURNAL_FILE = os.path.join(BASE_DIR, "journal.json")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")


# ===================================================================
#  שכבת נתונים (Data Persistence Helpers)
# ===================================================================
def load_json(path, default):
    """טעינת קובץ JSON עם ערך ברירת מחדל במקרה של כשל."""
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return default


def save_json(path, data):
    """שמירת נתונים לקובץ JSON (אוטומטית בכל שינוי)."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError as exc:
        messagebox.showerror("שגיאת שמירה", "שגיאה בשמירת הנתונים:\n%s" % exc)
        return False


def parse_float(value, field_name, allow_empty=False, allow_zero=True):
    """
    המרת מחרוזת למספר עם הודעות שגיאה בעברית.
    מחזיר (מספר, None) בהצלחה או (None, שגיאה) בכישלון.
    """
    value = str(value).strip()
    if value == "":
        if allow_empty:
            return None, None
        return None, "השדה '%s' לא יכול להיות ריק" % field_name
    try:
        num = float(value)
    except ValueError:
        return None, "השדה '%s' חייב להכיל מספר תקין" % field_name
    if not allow_zero and num == 0:
        return None, "השדה '%s' לא יכול להיות אפס" % field_name
    return num, None


def fmt_money(value):
    """פורמט כספי."""
    return "${:,.2f}".format(value)


def fmt_pct(value):
    """פורמט אחוזים."""
    return "%+.2f%%" % value


# ===================================================================
#  האפליקציה הראשית
# ===================================================================
class StockTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Stock Tracker Pro")
        self.geometry("1280x860")
        self.minsize(1200, 800)
        self.configure(bg=COLORS["bg"])

        # --- טעינת נתונים ---
        self.portfolio = load_json(PORTFOLIO_FILE, [])
        self.analyses = load_json(ANALYSES_FILE, [])
        self.journal = load_json(JOURNAL_FILE, [])
        self.history = load_json(HISTORY_FILE, [])

        self._configure_style()

        # --- כותרת ראשית ---
        header = tk.Frame(self, bg=COLORS["surface"], height=56)
        header.pack(side=tk.TOP, fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="📈  Stock Tracker Pro  -  מעקב תיק מניות",
            bg=COLORS["surface"], fg=COLORS["text"],
            font=FONT_TITLE, anchor="e", justify="right",
        ).pack(side=tk.RIGHT, padx=20, fill=tk.Y)

        # --- טאבים ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.tab_portfolio = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.tab_analysis = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.tab_journal = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.tab_charts = tk.Frame(self.notebook, bg=COLORS["bg"])

        # סדר RTL: הטאב הראשון מימין
        self.notebook.add(self.tab_portfolio, text="  📊 תיק מניות  ")
        self.notebook.add(self.tab_analysis, text="  🔍 ניתוח מניה  ")
        self.notebook.add(self.tab_journal, text="  📒 יומן מסחר  ")
        self.notebook.add(self.tab_charts, text="  📈 גרפים  ")

        # בניית כל הטאבים
        self._build_portfolio_tab()
        self._build_analysis_tab()
        self._build_journal_tab()
        self._build_charts_tab()

        # רענון גרפים בעת מעבר לטאב הגרפים
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # מילוי ראשוני
        self.refresh_portfolio()
        self.refresh_journal()
        self.refresh_analyses_list()

    # ---------------------------------------------------------------
    #  עיצוב ttk (Style)
    # ---------------------------------------------------------------
    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Notebook
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=COLORS["surface"], foreground=COLORS["muted"],
            font=FONT_BOLD, padding=(18, 10), borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", COLORS["accent"])],
            foreground=[("selected", COLORS["text"])],
        )

        # Treeview (טבלאות)
        style.configure(
            "Treeview",
            background=COLORS["surface"], fieldbackground=COLORS["surface"],
            foreground=COLORS["text"], rowheight=28, borderwidth=0,
            font=FONT_SMALL,
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["accent"], foreground=COLORS["text"],
            font=FONT_BOLD, relief="flat",
        )
        style.map(
            "Treeview.Heading",
            background=[("active", COLORS["accent"])],
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["border"])],
            foreground=[("selected", COLORS["text"])],
        )

        # Scrollbar
        style.configure(
            "Vertical.TScrollbar",
            background=COLORS["surface"], troughcolor=COLORS["bg"],
            borderwidth=0, arrowcolor=COLORS["text"],
        )

        # Combobox
        style.configure(
            "TCombobox",
            fieldbackground=COLORS["input"], background=COLORS["input"],
            foreground=COLORS["text"], arrowcolor=COLORS["text"],
            borderwidth=0, padding=4,
        )

    # ---------------------------------------------------------------
    #  ווידג'טים עזר (Helper widgets)
    # ---------------------------------------------------------------
    def _make_label(self, parent, text, font=FONT_NORMAL, fg=None, bg=None):
        return tk.Label(
            parent, text=text, font=font,
            fg=fg or COLORS["text"], bg=bg or COLORS["bg"],
            anchor="e", justify="right",
        )

    def _make_entry(self, parent, width=18):
        return tk.Entry(
            parent, width=width, font=FONT_NORMAL,
            bg=COLORS["input"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief="flat",
            justify="right", highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
        )

    def _make_button(self, parent, text, command, color=None, width=14):
        return tk.Button(
            parent, text=text, command=command, width=width,
            bg=color or COLORS["accent"], fg=COLORS["text"],
            font=FONT_BOLD, relief="flat", cursor="hand2",
            activebackground=COLORS["border"],
            activeforeground=COLORS["text"], bd=0, pady=6,
        )

    def _make_text(self, parent, height=3, width=30):
        return tk.Text(
            parent, height=height, width=width, font=FONT_SMALL,
            bg=COLORS["input"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief="flat",
            highlightthickness=1, highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"], wrap="word", padx=6, pady=4,
        )

    def _make_combo(self, parent, values, width=16):
        var = tk.StringVar(value=values[0] if values else "")
        combo = ttk.Combobox(
            parent, textvariable=var, values=values, width=width,
            state="readonly", font=FONT_NORMAL, justify="right",
        )
        return combo, var

    # ===============================================================
    #  מודול 1: תיק מניות (Portfolio Tracker)
    # ===============================================================
    def _build_portfolio_tab(self):
        tab = self.tab_portfolio

        # ----- כרטיסי סיכום (Summary Cards) -----
        cards_frame = tk.Frame(tab, bg=COLORS["bg"])
        cards_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(12, 6))

        self.card_value = self._create_card(cards_frame, "שווי תיק כולל", "$0.00")
        self.card_pnl = self._create_card(cards_frame, "רווח/הפסד כולל ($)", "$0.00")
        self.card_pnl_pct = self._create_card(cards_frame, "רווח/הפסד כולל (%)", "0.00%")
        self.card_positions = self._create_card(cards_frame, "מספר פוזיציות", "0")

        # ----- טופס קלט (Input Form) -----
        form = tk.LabelFrame(
            tab, text=" הזנת פוזיציה ", bg=COLORS["bg"], fg=COLORS["accent"],
            font=FONT_BOLD, labelanchor="ne", bd=1, relief="solid",
        )
        form.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)

        self.p_entries = {}
        fields = [
            ("symbol", "סימבול (AAPL)"),
            ("name", "שם החברה"),
            ("shares", "מספר מניות"),
            ("entry_price", "מחיר כניסה $"),
            ("current_price", "מחיר נוכחי $"),
        ]
        # סידור RTL: ראשון מימין
        for i, (key, label) in enumerate(fields):
            col = len(fields) - 1 - i
            cell = tk.Frame(form, bg=COLORS["bg"])
            cell.grid(row=0, column=col, padx=8, pady=8, sticky="e")
            self._make_label(cell, label, font=FONT_SMALL).pack(anchor="e")
            ent = self._make_entry(cell, width=16)
            ent.pack(anchor="e", pady=(2, 0))
            self.p_entries[key] = ent

        # כפתורי פעולה
        btns = tk.Frame(form, bg=COLORS["bg"])
        btns.grid(row=1, column=0, columnspan=len(fields), pady=(0, 10), sticky="e", padx=8)
        self._make_button(btns, "הוסף פוזיציה", self.add_position, COLORS["green"]).pack(side=tk.RIGHT, padx=4)
        self._make_button(btns, "עדכן מחיר", self.update_price, COLORS["accent"]).pack(side=tk.RIGHT, padx=4)
        self._make_button(btns, "מחק פוזיציה", self.remove_position, COLORS["red"]).pack(side=tk.RIGHT, padx=4)
        self._make_button(btns, "נקה טופס", self.clear_portfolio_form, COLORS["surface"]).pack(side=tk.RIGHT, padx=4)

        # ----- פאנל התראות (Alerts) -----
        alert_frame = tk.LabelFrame(
            tab, text=" ⚠ התראות ", bg=COLORS["bg"], fg=COLORS["red"],
            font=FONT_BOLD, labelanchor="ne", bd=1, relief="solid",
        )
        alert_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)
        self.alerts_label = tk.Label(
            alert_frame, text="אין התראות פעילות", bg=COLORS["bg"],
            fg=COLORS["muted"], font=FONT_SMALL, anchor="e",
            justify="right", wraplength=1180,
        )
        self.alerts_label.pack(fill=tk.X, padx=10, pady=8, anchor="e")

        # ----- טבלת תיק (Portfolio Table) -----
        table_frame = tk.Frame(tab, bg=COLORS["bg"])
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(6, 12))

        cols = (
            "symbol", "name", "shares", "entry_price", "current_price",
            "entry_cost", "current_value", "pnl", "pnl_pct", "weight",
        )
        headers = {
            "symbol": "סימבול", "name": "שם החברה", "shares": "מניות",
            "entry_price": "מחיר כניסה $", "current_price": "מחיר נוכחי $",
            "entry_cost": "עלות כניסה $", "current_value": "שווי נוכחי $",
            "pnl": "רווח/הפסד $", "pnl_pct": "רווח/הפסד %", "weight": "משקל בתיק %",
        }
        widths = {
            "symbol": 80, "name": 170, "shares": 80, "entry_price": 110,
            "current_price": 110, "entry_cost": 120, "current_value": 120,
            "pnl": 120, "pnl_pct": 110, "weight": 110,
        }

        self.portfolio_tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", selectmode="browse",
        )
        for c in cols:
            self.portfolio_tree.heading(c, text=headers[c])
            self.portfolio_tree.column(c, width=widths[c], anchor="center")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.portfolio_tree.yview)
        self.portfolio_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.portfolio_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # צביעת שורות לפי רווח/הפסד
        self.portfolio_tree.tag_configure("profit", foreground=COLORS["green"])
        self.portfolio_tree.tag_configure("loss", foreground=COLORS["red"])
        self.portfolio_tree.tag_configure("neutral", foreground=COLORS["text"])

        self.portfolio_tree.bind("<<TreeviewSelect>>", self._on_portfolio_select)

    def _create_card(self, parent, label, value):
        """כרטיס סיכום."""
        card = tk.Frame(parent, bg=COLORS["surface"], bd=1, relief="flat")
        card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=6)
        val_lbl = tk.Label(
            card, text=value, bg=COLORS["surface"], fg=COLORS["text"],
            font=FONT_CARD_VALUE, anchor="center",
        )
        val_lbl.pack(pady=(14, 2), padx=10)
        tk.Label(
            card, text=label, bg=COLORS["surface"], fg=COLORS["muted"],
            font=FONT_CARD_LABEL, anchor="center",
        ).pack(pady=(0, 14), padx=10)
        return val_lbl

    # ----- חישובים -----
    def _position_metrics(self, pos, total_value):
        """חישוב מדדים נגזרים לפוזיציה בודדת."""
        shares = pos["shares"]
        entry = pos["entry_price"]
        current = pos["current_price"]
        entry_cost = shares * entry
        current_value = shares * current
        pnl = current_value - entry_cost
        pnl_pct = (pnl / entry_cost * 100) if entry_cost else 0.0
        weight = (current_value / total_value * 100) if total_value else 0.0
        return entry_cost, current_value, pnl, pnl_pct, weight

    def refresh_portfolio(self):
        """רענון טבלת התיק, כרטיסי הסיכום וההתראות."""
        # ניקוי הטבלה
        for item in self.portfolio_tree.get_children():
            self.portfolio_tree.delete(item)

        total_value = sum(p["shares"] * p["current_price"] for p in self.portfolio)
        total_cost = sum(p["shares"] * p["entry_price"] for p in self.portfolio)
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

        alerts = []
        for pos in self.portfolio:
            entry_cost, current_value, pnl, pnl_pct, weight = self._position_metrics(pos, total_value)
            tag = "profit" if pnl > 0 else ("loss" if pnl < 0 else "neutral")
            self.portfolio_tree.insert(
                "", tk.END, iid=pos["symbol"], tags=(tag,),
                values=(
                    pos["symbol"], pos["name"], "%g" % pos["shares"],
                    "%.2f" % pos["entry_price"], "%.2f" % pos["current_price"],
                    "{:,.2f}".format(entry_cost), "{:,.2f}".format(current_value),
                    "{:+,.2f}".format(pnl), fmt_pct(pnl_pct), "%.2f%%" % weight,
                ),
            )
            # התראות
            if pnl_pct >= ALERT_TAKE_PROFIT:
                alerts.append("🟢 %s: רווח של %s — שקול מימוש רווחים (Take Profit)" % (pos["symbol"], fmt_pct(pnl_pct)))
            if pnl_pct <= ALERT_STOP_LOSS:
                alerts.append("🔴 %s: הפסד של %s — שקול סטופ-לוס (Stop Loss)" % (pos["symbol"], fmt_pct(pnl_pct)))
            if weight > ALERT_CONCENTRATION:
                alerts.append("🟡 %s: משקל %.1f%% בתיק — סיכון ריכוזיות (Concentration Risk)" % (pos["symbol"], weight))

        # עדכון כרטיסים
        self.card_value.config(text=fmt_money(total_value))
        self.card_pnl.config(
            text="{:+,.2f}$".format(total_pnl),
            fg=COLORS["green"] if total_pnl > 0 else (COLORS["red"] if total_pnl < 0 else COLORS["text"]),
        )
        self.card_pnl_pct.config(
            text=fmt_pct(total_pnl_pct),
            fg=COLORS["green"] if total_pnl > 0 else (COLORS["red"] if total_pnl < 0 else COLORS["text"]),
        )
        self.card_positions.config(text=str(len(self.portfolio)))

        # עדכון התראות
        if alerts:
            self.alerts_label.config(text="\n".join(alerts), fg=COLORS["text"])
        else:
            self.alerts_label.config(text="אין התראות פעילות ✓", fg=COLORS["muted"])

    def _log_history(self):
        """תיעוד שווי התיק הכולל לאורך זמן (לגרף ההיסטוריה)."""
        total_value = sum(p["shares"] * p["current_price"] for p in self.portfolio)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.history.append({"timestamp": timestamp, "value": round(total_value, 2)})
        save_json(HISTORY_FILE, self.history)

    def _read_portfolio_form(self, require_prices=True):
        """קריאה וולידציה של טופס התיק. מחזיר dict או None בשגיאה."""
        symbol = self.p_entries["symbol"].get().strip().upper()
        name = self.p_entries["name"].get().strip()
        if not symbol:
            messagebox.showerror("שגיאת קלט", "יש להזין סימבול מניה")
            return None

        shares, err = parse_float(self.p_entries["shares"].get(), "מספר מניות", allow_zero=False)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return None
        if shares < 0:
            messagebox.showerror("שגיאת קלט", "מספר המניות חייב להיות חיובי")
            return None

        entry_price, err = parse_float(self.p_entries["entry_price"].get(), "מחיר כניסה $", allow_zero=False)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return None

        current_raw = self.p_entries["current_price"].get().strip()
        if current_raw == "" and not require_prices:
            current_price = entry_price
        else:
            current_price, err = parse_float(self.p_entries["current_price"].get(), "מחיר נוכחי $", allow_zero=False)
            if err:
                messagebox.showerror("שגיאת קלט", err)
                return None

        return {
            "symbol": symbol, "name": name or symbol, "shares": shares,
            "entry_price": entry_price, "current_price": current_price,
        }

    def add_position(self):
        """הוספת פוזיציה חדשה."""
        data = self._read_portfolio_form()
        if data is None:
            return
        # אם הסימבול קיים — שאל אם למזג
        for pos in self.portfolio:
            if pos["symbol"] == data["symbol"]:
                if messagebox.askyesno("סימבול קיים", "הסימבול %s כבר קיים. לעדכן את הפוזיציה הקיימת?" % data["symbol"]):
                    pos.update(data)
                    self._after_portfolio_change()
                return
        self.portfolio.append(data)
        self._after_portfolio_change()
        self.clear_portfolio_form()

    def update_price(self):
        """עדכון מחיר נוכחי (ושאר נתונים) לפוזיציה לפי סימבול."""
        symbol = self.p_entries["symbol"].get().strip().upper()
        if not symbol:
            messagebox.showerror("שגיאת קלט", "בחר פוזיציה מהטבלה או הזן סימבול לעדכון")
            return
        current_price, err = parse_float(self.p_entries["current_price"].get(), "מחיר נוכחי $", allow_zero=False)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return
        for pos in self.portfolio:
            if pos["symbol"] == symbol:
                pos["current_price"] = current_price
                # עדכון אופציונלי של שדות נוספים אם הוזנו
                shares_raw = self.p_entries["shares"].get().strip()
                if shares_raw:
                    val, e = parse_float(shares_raw, "מספר מניות", allow_zero=False)
                    if e is None:
                        pos["shares"] = val
                entry_raw = self.p_entries["entry_price"].get().strip()
                if entry_raw:
                    val, e = parse_float(entry_raw, "מחיר כניסה $", allow_zero=False)
                    if e is None:
                        pos["entry_price"] = val
                name = self.p_entries["name"].get().strip()
                if name:
                    pos["name"] = name
                self._after_portfolio_change()
                return
        messagebox.showerror("לא נמצא", "לא נמצאה פוזיציה עם הסימבול %s" % symbol)

    def remove_position(self):
        """מחיקת פוזיציה נבחרת."""
        sel = self.portfolio_tree.selection()
        symbol = sel[0] if sel else self.p_entries["symbol"].get().strip().upper()
        if not symbol:
            messagebox.showerror("שגיאת קלט", "בחר פוזיציה למחיקה")
            return
        if not messagebox.askyesno("אישור מחיקה", "למחוק את הפוזיציה %s?" % symbol):
            return
        before = len(self.portfolio)
        self.portfolio = [p for p in self.portfolio if p["symbol"] != symbol]
        if len(self.portfolio) == before:
            messagebox.showerror("לא נמצא", "לא נמצאה פוזיציה למחיקה")
            return
        self._after_portfolio_change()
        self.clear_portfolio_form()

    def _after_portfolio_change(self):
        """שמירה, תיעוד היסטוריה ורענון תצוגה לאחר כל שינוי."""
        save_json(PORTFOLIO_FILE, self.portfolio)
        self._log_history()
        self.refresh_portfolio()

    def clear_portfolio_form(self):
        for ent in self.p_entries.values():
            ent.delete(0, tk.END)

    def _on_portfolio_select(self, _event):
        """מילוי הטופס בעת בחירת שורה בטבלה."""
        sel = self.portfolio_tree.selection()
        if not sel:
            return
        symbol = sel[0]
        for pos in self.portfolio:
            if pos["symbol"] == symbol:
                self.clear_portfolio_form()
                self.p_entries["symbol"].insert(0, pos["symbol"])
                self.p_entries["name"].insert(0, pos["name"])
                self.p_entries["shares"].insert(0, "%g" % pos["shares"])
                self.p_entries["entry_price"].insert(0, "%g" % pos["entry_price"])
                self.p_entries["current_price"].insert(0, "%g" % pos["current_price"])
                break

    # ===============================================================
    #  מודול 2: ניתוח מניה (Stock Analysis)
    # ===============================================================
    def _build_analysis_tab(self):
        tab = self.tab_analysis

        # אזור גלילה
        canvas = tk.Canvas(tab, bg=COLORS["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["bg"])
        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=1230)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # שדה סימבול עליון
        top = tk.Frame(scroll_frame, bg=COLORS["bg"])
        top.pack(fill=tk.X, padx=14, pady=(12, 4))
        cell = tk.Frame(top, bg=COLORS["bg"])
        cell.pack(side=tk.RIGHT)
        self._make_label(cell, "סימבול מניה לניתוח", font=FONT_BOLD).pack(anchor="e")
        self.a_symbol = self._make_entry(cell, width=20)
        self.a_symbol.pack(anchor="e", pady=2)

        self.a_entries = {}

        # ----- סקציה A: ניתוח פונדמנטלי -----
        fund_fields = [
            ("revenue_growth", "צמיחת הכנסות YoY %"),
            ("gross_margin", "מרווח גולמי %"),
            ("net_margin", "מרווח נקי %"),
            ("fcf", "תזרים חופשי FCF $"),
            ("pe", "מכפיל רווח P/E"),
            ("forward_pe", "Forward P/E"),
            ("ev_ebitda", "EV/EBITDA"),
            ("peg", "PEG Ratio"),
            ("debt_equity", "חוב/הון Debt/Equity"),
            ("roe", "תשואה על ההון ROE %"),
            ("insider", "אחזקת מנהלים %"),
        ]
        self._build_analysis_section(scroll_frame, "סקציה A — ניתוח פונדמנטלי", fund_fields)

        # ----- סקציה B: ניתוח טכני -----
        tech_fields = [
            ("price", "מחיר נוכחי $"),
            ("ma50", "ממוצע נע MA 50"),
            ("ma150", "ממוצע נע MA 150"),
            ("ma200", "ממוצע נע MA 200"),
            ("rsi", "RSI (14)"),
            ("atr", "ATR% (14 ימים)"),
            ("vol_ratio", "יחס נפח מסחר (14 ימים)"),
            ("high52", "שיא 52 שבועות"),
            ("low52", "שפל 52 שבועות"),
        ]
        self._build_analysis_section(scroll_frame, "סקציה B — ניתוח טכני", tech_fields)

        # ----- סקציה C: בניית תזה -----
        thesis = tk.LabelFrame(
            scroll_frame, text=" סקציה C — בניית תזה ", bg=COLORS["bg"],
            fg=COLORS["accent"], font=FONT_BOLD, labelanchor="ne",
            bd=1, relief="solid",
        )
        thesis.pack(fill=tk.X, padx=14, pady=8)

        # 3 טיעונים שוריים
        self._make_label(thesis, "3 טיעונים שוריים (Bullish):", font=FONT_BOLD).pack(anchor="e", padx=10, pady=(8, 2))
        self.a_bull = []
        for i in range(3):
            t = self._make_text(thesis, height=2, width=120)
            t.pack(fill=tk.X, padx=10, pady=2)
            self.a_bull.append(t)

        # 2 סיכוני דוב
        self._make_label(thesis, "2 סיכוני דוב (Bear Risks):", font=FONT_BOLD).pack(anchor="e", padx=10, pady=(8, 2))
        self.a_bear = []
        for i in range(2):
            t = self._make_text(thesis, height=2, width=120)
            t.pack(fill=tk.X, padx=10, pady=2)
            self.a_bear.append(t)

        # שורת דרופדאונים
        dd_frame = tk.Frame(thesis, bg=COLORS["bg"])
        dd_frame.pack(fill=tk.X, padx=10, pady=8)

        dd_specs = [
            ("הכרעה אישית", ["שורי (Bullish)", "ניטרלי (Neutral)", "דובי (Bearish)"], "verdict"),
            ("המלצה", ["קנייה (Buy)", "החזקה (Hold)", "מכירה (Sell)"], "recommend"),
            ("רמת ביטחון", ["גבוהה (High)", "בינונית (Medium)", "נמוכה (Low)"], "confidence"),
        ]
        for i, (lbl, values, attr) in enumerate(dd_specs):
            col = len(dd_specs) - 1 - i
            cell = tk.Frame(dd_frame, bg=COLORS["bg"])
            cell.grid(row=0, column=col, padx=10, sticky="e")
            self._make_label(cell, lbl, font=FONT_SMALL).pack(anchor="e")
            combo, var = self._make_combo(cell, values)
            combo.pack(anchor="e", pady=2)
            setattr(self, "a_%s_combo" % attr, combo)
            setattr(self, "a_%s" % attr, var)

        # אופק זמן + יעד מחיר
        extra = tk.Frame(thesis, bg=COLORS["bg"])
        extra.pack(fill=tk.X, padx=10, pady=8)
        cell1 = tk.Frame(extra, bg=COLORS["bg"])
        cell1.grid(row=0, column=1, padx=10, sticky="e")
        self._make_label(cell1, "אופק זמן", font=FONT_SMALL).pack(anchor="e")
        self.a_horizon = self._make_entry(cell1, width=24)
        self.a_horizon.pack(anchor="e", pady=2)
        cell2 = tk.Frame(extra, bg=COLORS["bg"])
        cell2.grid(row=0, column=0, padx=10, sticky="e")
        self._make_label(cell2, "יעד מחיר $", font=FONT_SMALL).pack(anchor="e")
        self.a_target = self._make_entry(cell2, width=24)
        self.a_target.pack(anchor="e", pady=2)

        # כפתורים
        btns = tk.Frame(scroll_frame, bg=COLORS["bg"])
        btns.pack(fill=tk.X, padx=14, pady=8)
        self._make_button(btns, "שמור ניתוח", self.save_analysis, COLORS["green"]).pack(side=tk.RIGHT, padx=4)
        self._make_button(btns, "נקה טופס", self.clear_analysis_form, COLORS["surface"]).pack(side=tk.RIGHT, padx=4)

        # ----- רשימת ניתוחים שמורים -----
        saved = tk.LabelFrame(
            scroll_frame, text=" ניתוחים שמורים (לחיצה כפולה לטעינה) ",
            bg=COLORS["bg"], fg=COLORS["accent"], font=FONT_BOLD,
            labelanchor="ne", bd=1, relief="solid",
        )
        saved.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        cols = ("timestamp", "symbol", "verdict", "recommend", "target")
        headers = {
            "timestamp": "תאריך", "symbol": "סימבול", "verdict": "הכרעה",
            "recommend": "המלצה", "target": "יעד מחיר $",
        }
        self.analyses_tree = ttk.Treeview(saved, columns=cols, show="headings", height=5)
        for c in cols:
            self.analyses_tree.heading(c, text=headers[c])
            self.analyses_tree.column(c, anchor="center", width=160)
        self.analyses_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.analyses_tree.bind("<Double-1>", self._load_analysis)

    def _build_analysis_section(self, parent, title, fields):
        """בניית סקציה של שדות מספריים בארבע עמודות."""
        frame = tk.LabelFrame(
            parent, text=" %s " % title, bg=COLORS["bg"], fg=COLORS["accent"],
            font=FONT_BOLD, labelanchor="ne", bd=1, relief="solid",
        )
        frame.pack(fill=tk.X, padx=14, pady=8)
        per_row = 4
        for idx, (key, label) in enumerate(fields):
            row = idx // per_row
            pos_in_row = idx % per_row
            col = (per_row - 1 - pos_in_row)  # RTL
            cell = tk.Frame(frame, bg=COLORS["bg"])
            cell.grid(row=row, column=col, padx=10, pady=6, sticky="e")
            self._make_label(cell, label, font=FONT_SMALL).pack(anchor="e")
            ent = self._make_entry(cell, width=18)
            ent.pack(anchor="e", pady=2)
            self.a_entries[key] = ent

    def save_analysis(self):
        """שמירת ניתוח מלא ל-JSON עם חותמת זמן וסימבול."""
        symbol = self.a_symbol.get().strip().upper()
        if not symbol:
            messagebox.showerror("שגיאת קלט", "יש להזין סימבול מניה לניתוח")
            return

        # ולידציה רכה: שדות מספריים — מותר ריק, אך אם הוזנו חייבים להיות מספר
        numeric = {}
        for key, ent in self.a_entries.items():
            val, err = parse_float(ent.get(), key, allow_empty=True)
            if err:
                messagebox.showerror("שגיאת קלט", "ערך לא תקין בשדה הניתוח (%s)" % key)
                return
            numeric[key] = val

        target, err = parse_float(self.a_target.get(), "יעד מחיר $", allow_empty=True)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return

        analysis = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "fundamental_technical": numeric,
            "bullish": [t.get("1.0", tk.END).strip() for t in self.a_bull],
            "bearish": [t.get("1.0", tk.END).strip() for t in self.a_bear],
            "verdict": self.a_verdict.get(),
            "recommendation": self.a_recommend.get(),
            "confidence": self.a_confidence.get(),
            "time_horizon": self.a_horizon.get().strip(),
            "price_target": target,
        }
        self.analyses.append(analysis)
        save_json(ANALYSES_FILE, self.analyses)
        self.refresh_analyses_list()
        messagebox.showinfo("נשמר", "הניתוח של %s נשמר בהצלחה ✓" % symbol)

    def refresh_analyses_list(self):
        for item in self.analyses_tree.get_children():
            self.analyses_tree.delete(item)
        for i, a in enumerate(self.analyses):
            target = a.get("price_target")
            self.analyses_tree.insert(
                "", tk.END, iid=str(i),
                values=(
                    a.get("timestamp", ""), a.get("symbol", ""),
                    a.get("verdict", ""), a.get("recommendation", ""),
                    ("%.2f" % target) if target is not None else "-",
                ),
            )

    def _load_analysis(self, _event):
        """טעינת ניתוח שמור לטופס."""
        sel = self.analyses_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        a = self.analyses[idx]
        self.clear_analysis_form()
        self.a_symbol.insert(0, a.get("symbol", ""))
        for key, ent in self.a_entries.items():
            val = a.get("fundamental_technical", {}).get(key)
            if val is not None:
                ent.insert(0, "%g" % val)
        for i, t in enumerate(self.a_bull):
            if i < len(a.get("bullish", [])):
                t.insert("1.0", a["bullish"][i])
        for i, t in enumerate(self.a_bear):
            if i < len(a.get("bearish", [])):
                t.insert("1.0", a["bearish"][i])
        if a.get("verdict"):
            self.a_verdict.set(a["verdict"])
        if a.get("recommendation"):
            self.a_recommend.set(a["recommendation"])
        if a.get("confidence"):
            self.a_confidence.set(a["confidence"])
        self.a_horizon.insert(0, a.get("time_horizon", ""))
        if a.get("price_target") is not None:
            self.a_target.insert(0, "%g" % a["price_target"])

    def clear_analysis_form(self):
        self.a_symbol.delete(0, tk.END)
        for ent in self.a_entries.values():
            ent.delete(0, tk.END)
        for t in self.a_bull + self.a_bear:
            t.delete("1.0", tk.END)
        self.a_horizon.delete(0, tk.END)
        self.a_target.delete(0, tk.END)

    # ===============================================================
    #  מודול 3: יומן מסחר (Trade Journal)
    # ===============================================================
    def _build_journal_tab(self):
        tab = self.tab_journal

        # ----- טופס הוספת עסקה -----
        form = tk.LabelFrame(
            tab, text=" הוספת עסקה ליומן ", bg=COLORS["bg"], fg=COLORS["accent"],
            font=FONT_BOLD, labelanchor="ne", bd=1, relief="solid",
        )
        form.pack(side=tk.TOP, fill=tk.X, padx=12, pady=12)

        self.j_entries = {}
        # שורה ראשונה — שדות מספריים/טקסט קצר
        row1 = [
            ("date", "תאריך (YYYY-MM-DD)"),
            ("symbol", "סימבול"),
            ("name", "שם החברה"),
            ("quantity", "כמות"),
            ("entry_price", "מחיר כניסה $"),
            ("target_price", "מחיר יעד $"),
            ("stop_loss", "סטופ לוס $"),
            ("exit_price", "מחיר יציאה $ (אופ')"),
        ]
        grid = tk.Frame(form, bg=COLORS["bg"])
        grid.pack(fill=tk.X, padx=8, pady=6)
        for i, (key, label) in enumerate(row1):
            col = len(row1) - 1 - i
            cell = tk.Frame(grid, bg=COLORS["bg"])
            cell.grid(row=0, column=col, padx=6, pady=4, sticky="e")
            self._make_label(cell, label, font=FONT_SMALL).pack(anchor="e")
            ent = self._make_entry(cell, width=14)
            ent.pack(anchor="e", pady=2)
            self.j_entries[key] = ent
        self.j_entries["date"].insert(0, datetime.date.today().isoformat())

        # שורת דרופדאונים: פעולה + סטטוס
        dd = tk.Frame(form, bg=COLORS["bg"])
        dd.pack(fill=tk.X, padx=8, pady=4)
        j_dd_specs = [
            ("פעולה", ["קנייה (Buy)", "מכירה (Sell)", "מעקב (Watch)"], "action"),
            ("סטטוס", ["פתוחה (Open)", "סגורה (Closed)"], "status"),
        ]
        for i, (lbl, values, attr) in enumerate(j_dd_specs):
            col = 1 - i
            cell = tk.Frame(dd, bg=COLORS["bg"])
            cell.grid(row=0, column=col, padx=10, sticky="e")
            self._make_label(cell, lbl, font=FONT_SMALL).pack(anchor="e")
            combo, var = self._make_combo(cell, values)
            combo.pack(anchor="e", pady=2)
            setattr(self, "j_%s_combo" % attr, combo)
            setattr(self, "j_%s" % attr, var)

        # אזורי טקסט: תזה + לקח
        texts = tk.Frame(form, bg=COLORS["bg"])
        texts.pack(fill=tk.X, padx=8, pady=4)
        cell_thesis = tk.Frame(texts, bg=COLORS["bg"])
        cell_thesis.grid(row=0, column=1, padx=8, sticky="e")
        self._make_label(cell_thesis, "תזה / נימוק", font=FONT_SMALL).pack(anchor="e")
        self.j_thesis = self._make_text(cell_thesis, height=3, width=55)
        self.j_thesis.pack(anchor="e", pady=2)
        cell_lesson = tk.Frame(texts, bg=COLORS["bg"])
        cell_lesson.grid(row=0, column=0, padx=8, sticky="e")
        self._make_label(cell_lesson, "לקח שנלמד", font=FONT_SMALL).pack(anchor="e")
        self.j_lesson = self._make_text(cell_lesson, height=3, width=55)
        self.j_lesson.pack(anchor="e", pady=2)

        # כפתורים
        btns = tk.Frame(form, bg=COLORS["bg"])
        btns.pack(fill=tk.X, padx=8, pady=8)
        self._make_button(btns, "הוסף עסקה", self.add_trade, COLORS["green"]).pack(side=tk.RIGHT, padx=4)
        self._make_button(btns, "מחק עסקה", self.remove_trade, COLORS["red"]).pack(side=tk.RIGHT, padx=4)
        self._make_button(btns, "נקה טופס", self.clear_journal_form, COLORS["surface"]).pack(side=tk.RIGHT, padx=4)

        # ----- פאנל סטטיסטיקה -----
        stats = tk.Frame(tab, bg=COLORS["bg"])
        stats.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)
        self.stat_total = self._create_card(stats, "סך עסקאות", "0")
        self.stat_winrate = self._create_card(stats, "אחוז הצלחה (Win Rate)", "0%")
        self.stat_avg = self._create_card(stats, "ממוצע רווח/הפסד %", "0.00%")
        self.stat_symbols = self._create_card(stats, "סימבולים נסחרים", "-")

        # ----- טבלת יומן -----
        table_frame = tk.Frame(tab, bg=COLORS["bg"])
        table_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(6, 12))

        cols = ("date", "symbol", "action", "quantity", "entry_price", "target", "stop", "status")
        headers = {
            "date": "תאריך", "symbol": "סימבול", "action": "פעולה",
            "quantity": "כמות", "entry_price": "מחיר כניסה", "target": "יעד",
            "stop": "סטופ לוס", "status": "סטטוס",
        }
        self.journal_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.journal_tree.heading(c, text=headers[c])
            self.journal_tree.column(c, anchor="center", width=140)
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.journal_tree.yview)
        self.journal_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.journal_tree.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.journal_tree.bind("<<TreeviewSelect>>", self._on_journal_select)

    def add_trade(self):
        """הוספת עסקה ליומן."""
        symbol = self.j_entries["symbol"].get().strip().upper()
        if not symbol:
            messagebox.showerror("שגיאת קלט", "יש להזין סימבול")
            return
        date = self.j_entries["date"].get().strip() or datetime.date.today().isoformat()

        quantity, err = parse_float(self.j_entries["quantity"].get(), "כמות", allow_empty=True)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return
        entry_price, err = parse_float(self.j_entries["entry_price"].get(), "מחיר כניסה $", allow_empty=True)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return
        target, err = parse_float(self.j_entries["target_price"].get(), "מחיר יעד $", allow_empty=True)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return
        stop, err = parse_float(self.j_entries["stop_loss"].get(), "סטופ לוס $", allow_empty=True)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return
        exit_price, err = parse_float(self.j_entries["exit_price"].get(), "מחיר יציאה $", allow_empty=True)
        if err:
            messagebox.showerror("שגיאת קלט", err)
            return

        trade = {
            "date": date,
            "symbol": symbol,
            "name": self.j_entries["name"].get().strip() or symbol,
            "action": self.j_action.get(),
            "quantity": quantity,
            "entry_price": entry_price,
            "target_price": target,
            "stop_loss": stop,
            "exit_price": exit_price,
            "status": self.j_status.get(),
            "thesis": self.j_thesis.get("1.0", tk.END).strip(),
            "lesson": self.j_lesson.get("1.0", tk.END).strip(),
        }
        self.journal.append(trade)
        save_json(JOURNAL_FILE, self.journal)
        self.refresh_journal()
        self.clear_journal_form()

    def remove_trade(self):
        sel = self.journal_tree.selection()
        if not sel:
            messagebox.showerror("שגיאת קלט", "בחר עסקה למחיקה")
            return
        idx = int(sel[0])
        if not messagebox.askyesno("אישור מחיקה", "למחוק את העסקה הנבחרת?"):
            return
        del self.journal[idx]
        save_json(JOURNAL_FILE, self.journal)
        self.refresh_journal()
        self.clear_journal_form()

    def _trade_pnl_pct(self, trade):
        """חישוב רווח/הפסד % לעסקה סגורה (לפי מחיר יציאה)."""
        entry = trade.get("entry_price")
        exit_price = trade.get("exit_price")
        if not entry or exit_price is None:
            return None
        pct = (exit_price - entry) / entry * 100
        # עבור מכירה (שורט) — היפוך הסימן
        if "Sell" in str(trade.get("action", "")):
            pct = -pct
        return pct

    def _is_closed(self, trade):
        return "Closed" in str(trade.get("status", ""))

    def refresh_journal(self):
        """רענון טבלת היומן ופאנל הסטטיסטיקה."""
        for item in self.journal_tree.get_children():
            self.journal_tree.delete(item)

        def f(v):
            return ("%g" % v) if isinstance(v, (int, float)) else "-"

        for i, t in enumerate(self.journal):
            self.journal_tree.insert(
                "", tk.END, iid=str(i),
                values=(
                    t.get("date", ""), t.get("symbol", ""), t.get("action", ""),
                    f(t.get("quantity")), f(t.get("entry_price")),
                    f(t.get("target_price")), f(t.get("stop_loss")),
                    t.get("status", ""),
                ),
            )

        # סטטיסטיקה
        total = len(self.journal)
        closed = [t for t in self.journal if self._is_closed(t)]
        closed_pnls = [self._trade_pnl_pct(t) for t in closed]
        closed_pnls = [p for p in closed_pnls if p is not None]
        wins = sum(1 for p in closed_pnls if p > 0)
        win_rate = (wins / len(closed_pnls) * 100) if closed_pnls else 0.0
        avg_pnl = (sum(closed_pnls) / len(closed_pnls)) if closed_pnls else 0.0

        symbols = [t.get("symbol", "") for t in self.journal if t.get("symbol")]
        counter = Counter(symbols)
        top = counter.most_common(3)
        top_str = ", ".join("%s (%d)" % (s, c) for s, c in top) if top else "-"

        self.stat_total.config(text=str(total))
        self.stat_winrate.config(
            text="%.1f%%" % win_rate,
            fg=COLORS["green"] if win_rate >= 50 else COLORS["red"],
        )
        self.stat_avg.config(
            text=fmt_pct(avg_pnl),
            fg=COLORS["green"] if avg_pnl > 0 else (COLORS["red"] if avg_pnl < 0 else COLORS["text"]),
        )
        self.stat_symbols.config(text=top_str, font=(FONT_FAMILY, 12, "bold"))

    def _on_journal_select(self, _event):
        sel = self.journal_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        t = self.journal[idx]
        self.clear_journal_form()
        self.j_entries["date"].insert(0, t.get("date", ""))
        self.j_entries["symbol"].insert(0, t.get("symbol", ""))
        self.j_entries["name"].insert(0, t.get("name", ""))

        def put(key, val):
            if val is not None:
                self.j_entries[key].insert(0, "%g" % val)

        put("quantity", t.get("quantity"))
        put("entry_price", t.get("entry_price"))
        put("target_price", t.get("target_price"))
        put("stop_loss", t.get("stop_loss"))
        put("exit_price", t.get("exit_price"))
        if t.get("action"):
            self.j_action.set(t["action"])
        if t.get("status"):
            self.j_status.set(t["status"])
        self.j_thesis.insert("1.0", t.get("thesis", ""))
        self.j_lesson.insert("1.0", t.get("lesson", ""))

    def clear_journal_form(self):
        for key, ent in self.j_entries.items():
            ent.delete(0, tk.END)
        self.j_entries["date"].insert(0, datetime.date.today().isoformat())
        self.j_thesis.delete("1.0", tk.END)
        self.j_lesson.delete("1.0", tk.END)

    # ===============================================================
    #  מודול 4: גרפים (Charts)
    # ===============================================================
    def _build_charts_tab(self):
        tab = self.tab_charts

        top = tk.Frame(tab, bg=COLORS["bg"])
        top.pack(side=tk.TOP, fill=tk.X, padx=12, pady=8)
        self._make_button(top, "רענן גרפים", self.refresh_charts, COLORS["accent"]).pack(side=tk.RIGHT)
        self._make_label(top, "גרפים מתעדכנים אוטומטית לפי נתוני התיק", font=FONT_SMALL, fg=COLORS["muted"]).pack(side=tk.RIGHT, padx=12)

        # פיגורה אחת עם 3 תרשימים
        self.fig = Figure(figsize=(12, 7), facecolor=COLORS["bg"])
        self.ax_pie = self.fig.add_subplot(2, 2, 1)
        self.ax_bar = self.fig.add_subplot(2, 2, 2)
        self.ax_line = self.fig.add_subplot(2, 1, 2)
        self.fig.subplots_adjust(hspace=0.4, wspace=0.3, left=0.08, right=0.95, top=0.93, bottom=0.1)

        self.chart_canvas = FigureCanvasTkAgg(self.fig, master=tab)
        self.chart_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

    def _style_axes(self, ax, title):
        ax.set_facecolor(COLORS["surface"])
        ax.set_title(title, color=COLORS["text"], fontsize=12, fontweight="bold")
        ax.tick_params(colors=COLORS["text"], labelsize=9)
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

    def refresh_charts(self):
        """ציור מחדש של שלושת הגרפים לפי הנתונים הנוכחיים."""
        self.ax_pie.clear()
        self.ax_bar.clear()
        self.ax_line.clear()

        total_value = sum(p["shares"] * p["current_price"] for p in self.portfolio)

        # ----- גרף 1: עוגה — התפלגות משקלים -----
        self._style_axes(self.ax_pie, "התפלגות התיק לפי משקל")
        if self.portfolio and total_value > 0:
            labels = [p["symbol"] for p in self.portfolio]
            sizes = [p["shares"] * p["current_price"] for p in self.portfolio]
            wedges, texts, autotexts = self.ax_pie.pie(
                sizes, labels=labels, autopct="%1.1f%%", startangle=90,
                textprops={"color": COLORS["text"], "fontsize": 9},
            )
            for at in autotexts:
                at.set_color("#FFFFFF")
                at.set_fontsize(8)
        else:
            self.ax_pie.text(0.5, 0.5, "אין נתונים", ha="center", va="center",
                             color=COLORS["muted"], transform=self.ax_pie.transAxes)

        # ----- גרף 2: עמודות — רווח/הפסד לפי פוזיציה -----
        self._style_axes(self.ax_bar, "רווח/הפסד $ לפי פוזיציה")
        if self.portfolio:
            symbols = [p["symbol"] for p in self.portfolio]
            pnls = [p["shares"] * p["current_price"] - p["shares"] * p["entry_price"] for p in self.portfolio]
            bar_colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in pnls]
            self.ax_bar.bar(symbols, pnls, color=bar_colors)
            self.ax_bar.axhline(0, color=COLORS["muted"], linewidth=0.8)
            self.ax_bar.tick_params(axis="x", rotation=45)
        else:
            self.ax_bar.text(0.5, 0.5, "אין נתונים", ha="center", va="center",
                             color=COLORS["muted"], transform=self.ax_bar.transAxes)

        # ----- גרף 3: קו — שווי התיק לאורך זמן -----
        self._style_axes(self.ax_line, "שווי התיק לאורך זמן")
        if len(self.history) >= 1:
            values = [h["value"] for h in self.history]
            x = list(range(len(values)))
            self.ax_line.plot(x, values, color=COLORS["accent"], linewidth=2, marker="o", markersize=3)
            self.ax_line.fill_between(x, values, color=COLORS["accent"], alpha=0.15)
            # תוויות תאריך דלילות
            step = max(1, len(values) // 8)
            ticks = x[::step]
            self.ax_line.set_xticks(ticks)
            self.ax_line.set_xticklabels(
                [self.history[i]["timestamp"][5:16] for i in ticks],
                rotation=30, ha="right", fontsize=8,
            )
        else:
            self.ax_line.text(0.5, 0.5, "אין היסטוריה עדיין", ha="center", va="center",
                              color=COLORS["muted"], transform=self.ax_line.transAxes)

        self.chart_canvas.draw()

    # ---------------------------------------------------------------
    def _on_tab_changed(self, _event):
        """רענון גרפים בעת מעבר לטאב הגרפים."""
        if self.notebook.index(self.notebook.select()) == 3:
            self.refresh_charts()


def main():
    app = StockTrackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
