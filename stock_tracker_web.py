#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stock Tracker Pro - Web Edition
===============================
גרסת ה-Web של אפליקציית מעקב תיק המניות, בנויה ב-Streamlit.
עובדת בדפדפן - גם במחשב וגם בטלפון (אותו עיצוב, אותם נתונים).

הרצה מקומית:
    streamlit run stock_tracker_web.py

הנתונים נשמרים אוטומטית בקבצי JSON מקומיים (זהים לגרסת השולחן):
    portfolio.json, analyses.json, journal.json, history.json
"""

import os
import json
import datetime
from collections import Counter

import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# ===================================================================
#  קבועים (Constants)
# ===================================================================
COLORS = {
    "bg": "#1E2A3A", "surface": "#2C3E50", "accent": "#2980B9",
    "green": "#27AE60", "red": "#E74C3C", "text": "#ECF0F1", "muted": "#95A5A6",
}

ALERT_TAKE_PROFIT = 15.0
ALERT_STOP_LOSS = -8.0
ALERT_CONCENTRATION = 25.0

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
ANALYSES_FILE = os.path.join(BASE_DIR, "analyses.json")
JOURNAL_FILE = os.path.join(BASE_DIR, "journal.json")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")


# ===================================================================
#  שכבת נתונים (Persistence)
# ===================================================================
def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        st.error("שגיאה בשמירת הנתונים: %s" % exc)


def load_state():
    """טעינת כל הנתונים ל-session_state פעם אחת."""
    if "loaded" not in st.session_state:
        st.session_state.portfolio = load_json(PORTFOLIO_FILE, [])
        st.session_state.analyses = load_json(ANALYSES_FILE, [])
        st.session_state.journal = load_json(JOURNAL_FILE, [])
        st.session_state.history = load_json(HISTORY_FILE, [])
        st.session_state.loaded = True


def log_history():
    total = sum(p["shares"] * p["current_price"] for p in st.session_state.portfolio)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.history.append({"timestamp": ts, "value": round(total, 2)})
    save_json(HISTORY_FILE, st.session_state.history)


# ===================================================================
#  עיצוב (Theme + RTL CSS)
# ===================================================================
def inject_css():
    st.markdown(
        """
        <style>
        .stApp { background-color: %(bg)s; color: %(text)s; }
        html, body, [class*="css"] { direction: rtl; }
        .main .block-container { direction: rtl; text-align: right; padding-top: 2rem; }
        h1, h2, h3, h4, label, p, span, div { color: %(text)s; }
        section[data-testid="stSidebar"] { background-color: %(surface)s; }
        .stTabs [data-baseweb="tab-list"] { gap: 6px; direction: rtl; }
        .stTabs [data-baseweb="tab"] {
            background-color: %(surface)s; border-radius: 6px 6px 0 0;
            padding: 10px 18px; color: %(muted)s; font-weight: bold;
        }
        .stTabs [aria-selected="true"] { background-color: %(accent)s; color: white; }
        div[data-testid="stMetric"] {
            background-color: %(surface)s; border-radius: 10px;
            padding: 14px; text-align: center;
        }
        div[data-testid="stMetricValue"] { font-size: 1.6rem; }
        .stButton button {
            background-color: %(accent)s; color: white; border: none;
            border-radius: 6px; font-weight: bold; padding: 8px 16px; width: 100%%;
        }
        .stDataFrame { direction: ltr; }
        input, textarea { direction: rtl; text-align: right; }
        </style>
        """ % COLORS,
        unsafe_allow_html=True,
    )


def num(x):
    """המרה בטוחה למספר (None אם ריק/לא תקין)."""
    try:
        s = str(x).strip()
        return float(s) if s != "" else None
    except (ValueError, TypeError):
        return None


# ===================================================================
#  מודול 1: תיק מניות
# ===================================================================
def tab_portfolio():
    pf = st.session_state.portfolio

    total_value = sum(p["shares"] * p["current_price"] for p in pf)
    total_cost = sum(p["shares"] * p["entry_price"] for p in pf)
    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0.0

    # ----- כרטיסי סיכום -----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("מספר פוזיציות", len(pf))
    c2.metric("רווח/הפסד כולל %", "%+.2f%%" % total_pnl_pct)
    c3.metric("רווח/הפסד כולל $", "{:+,.2f}$".format(total_pnl))
    c4.metric("שווי תיק כולל", "${:,.2f}".format(total_value))

    st.divider()

    # ----- טופס הזנה -----
    with st.expander("➕ הזנת / עדכון פוזיציה", expanded=not pf):
        with st.form("pf_form", clear_on_submit=True):
            f1, f2, f3, f4, f5 = st.columns(5)
            symbol = f5.text_input("סימבול (AAPL)")
            name = f4.text_input("שם החברה")
            shares = f3.text_input("מספר מניות")
            entry = f2.text_input("מחיר כניסה $")
            current = f1.text_input("מחיר נוכחי $")
            b1, b2 = st.columns(2)
            add = b1.form_submit_button("➕ הוסף / עדכן פוזיציה")
            if add:
                _add_position(symbol, name, shares, entry, current)

    # ----- מחיקה -----
    if pf:
        d1, d2 = st.columns([3, 1])
        to_del = d1.selectbox("בחר פוזיציה למחיקה", [p["symbol"] for p in pf], key="del_sel")
        if d2.button("🗑️ מחק פוזיציה"):
            st.session_state.portfolio = [p for p in pf if p["symbol"] != to_del]
            save_json(PORTFOLIO_FILE, st.session_state.portfolio)
            log_history()
            st.rerun()

    # ----- התראות -----
    alerts = []
    for p in pf:
        ec = p["shares"] * p["entry_price"]
        cv = p["shares"] * p["current_price"]
        pnl_pct = ((cv - ec) / ec * 100) if ec else 0.0
        weight = (cv / total_value * 100) if total_value else 0.0
        if pnl_pct >= ALERT_TAKE_PROFIT:
            alerts.append(("success", "🟢 %s: רווח %+.2f%% — שקול מימוש רווחים (Take Profit)" % (p["symbol"], pnl_pct)))
        if pnl_pct <= ALERT_STOP_LOSS:
            alerts.append(("error", "🔴 %s: הפסד %+.2f%% — שקול סטופ-לוס (Stop Loss)" % (p["symbol"], pnl_pct)))
        if weight > ALERT_CONCENTRATION:
            alerts.append(("warning", "🟡 %s: משקל %.1f%% בתיק — סיכון ריכוזיות" % (p["symbol"], weight)))
    if alerts:
        st.subheader("⚠ התראות")
        for kind, msg in alerts:
            getattr(st, kind)(msg)

    # ----- טבלה -----
    st.subheader("📊 טבלת התיק")
    if pf:
        rows = []
        for p in pf:
            ec = p["shares"] * p["entry_price"]
            cv = p["shares"] * p["current_price"]
            pnl = cv - ec
            pnl_pct = (pnl / ec * 100) if ec else 0.0
            weight = (cv / total_value * 100) if total_value else 0.0
            rows.append({
                "סימבול": p["symbol"], "שם": p["name"], "מניות": p["shares"],
                "מחיר כניסה $": round(p["entry_price"], 2),
                "מחיר נוכחי $": round(p["current_price"], 2),
                "עלות $": round(ec, 2), "שווי $": round(cv, 2),
                "רווח/הפסד $": round(pnl, 2), "רווח/הפסד %": round(pnl_pct, 2),
                "משקל %": round(weight, 2),
            })
        df = pd.DataFrame(rows)

        def color_pnl(v):
            color = COLORS["green"] if v > 0 else (COLORS["red"] if v < 0 else COLORS["text"])
            return "color: %s" % color

        styled = df.style.map(color_pnl, subset=["רווח/הפסד $", "רווח/הפסד %"])
        st.dataframe(styled, width="stretch", hide_index=True)
    else:
        st.info("התיק ריק. הוסף פוזיציה כדי להתחיל.")


def _add_position(symbol, name, shares, entry, current):
    symbol = symbol.strip().upper()
    if not symbol:
        st.error("יש להזין סימבול")
        return
    s, e = num(shares), num(entry)
    c = num(current)
    if s is None or s <= 0:
        st.error("מספר מניות חייב להיות מספר חיובי")
        return
    if e is None or e <= 0:
        st.error("מחיר כניסה חייב להיות מספר חיובי")
        return
    if c is None or c <= 0:
        c = e  # ברירת מחדל: מחיר נוכחי = מחיר כניסה
    data = {"symbol": symbol, "name": name.strip() or symbol,
            "shares": s, "entry_price": e, "current_price": c}
    for p in st.session_state.portfolio:
        if p["symbol"] == symbol:
            p.update(data)
            break
    else:
        st.session_state.portfolio.append(data)
    save_json(PORTFOLIO_FILE, st.session_state.portfolio)
    log_history()
    st.session_state.flash = "הפוזיציה %s נשמרה ✓" % symbol
    st.rerun()


# ===================================================================
#  מודול 2: ניתוח מניה
# ===================================================================
def tab_analysis():
    st.subheader("🔍 ניתוח מניה")
    with st.form("analysis_form"):
        symbol = st.text_input("סימבול מניה לניתוח")

        st.markdown("##### סקציה A — ניתוח פונדמנטלי")
        fa = {}
        fund = [
            ("revenue_growth", "צמיחת הכנסות YoY %"), ("gross_margin", "מרווח גולמי %"),
            ("net_margin", "מרווח נקי %"), ("fcf", "תזרים חופשי $"),
            ("pe", "P/E"), ("forward_pe", "Forward P/E"), ("ev_ebitda", "EV/EBITDA"),
            ("peg", "PEG"), ("debt_equity", "Debt/Equity"), ("roe", "ROE %"),
            ("insider", "אחזקת מנהלים %"),
        ]
        cols = st.columns(4)
        for i, (k, lbl) in enumerate(fund):
            fa[k] = cols[i % 4].text_input(lbl, key="fa_%s" % k)

        st.markdown("##### סקציה B — ניתוח טכני")
        tech = [
            ("price", "מחיר נוכחי $"), ("ma50", "MA 50"), ("ma150", "MA 150"),
            ("ma200", "MA 200"), ("rsi", "RSI (14)"), ("atr", "ATR% (14)"),
            ("vol_ratio", "יחס נפח (14)"), ("high52", "שיא 52ש"), ("low52", "שפל 52ש"),
        ]
        cols = st.columns(4)
        for i, (k, lbl) in enumerate(tech):
            fa[k] = cols[i % 4].text_input(lbl, key="ta_%s" % k)

        st.markdown("##### סקציה C — בניית תזה")
        bull = [st.text_area("טיעון שורי %d" % (i + 1), key="bull_%d" % i, height=68) for i in range(3)]
        bear = [st.text_area("סיכון דובי %d" % (i + 1), key="bear_%d" % i, height=68) for i in range(2)]
        d1, d2, d3 = st.columns(3)
        verdict = d1.selectbox("הכרעה", ["שורי (Bullish)", "ניטרלי (Neutral)", "דובי (Bearish)"])
        recommend = d2.selectbox("המלצה", ["קנייה (Buy)", "החזקה (Hold)", "מכירה (Sell)"])
        confidence = d3.selectbox("רמת ביטחון", ["גבוהה (High)", "בינונית (Medium)", "נמוכה (Low)"])
        e1, e2 = st.columns(2)
        horizon = e1.text_input("אופק זמן")
        target = e2.text_input("יעד מחיר $")

        if st.form_submit_button("💾 שמור ניתוח"):
            sym = symbol.strip().upper()
            if not sym:
                st.error("יש להזין סימבול לניתוח")
            else:
                st.session_state.analyses.append({
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": sym,
                    "fundamental_technical": {k: num(v) for k, v in fa.items()},
                    "bullish": [b.strip() for b in bull], "bearish": [b.strip() for b in bear],
                    "verdict": verdict, "recommendation": recommend, "confidence": confidence,
                    "time_horizon": horizon.strip(), "price_target": num(target),
                })
                save_json(ANALYSES_FILE, st.session_state.analyses)
                st.session_state.flash = "הניתוח של %s נשמר ✓" % sym
                st.rerun()

    # רשימת ניתוחים שמורים
    if st.session_state.analyses:
        st.markdown("##### ניתוחים שמורים")
        rows = [{
            "תאריך": a["timestamp"], "סימבול": a["symbol"], "הכרעה": a.get("verdict", ""),
            "המלצה": a.get("recommendation", ""),
            "יעד $": a.get("price_target"),
        } for a in st.session_state.analyses]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ===================================================================
#  מודול 3: יומן מסחר
# ===================================================================
def tab_journal():
    st.subheader("📒 יומן מסחר")
    with st.expander("➕ הוספת עסקה", expanded=not st.session_state.journal):
        with st.form("journal_form", clear_on_submit=True):
            c = st.columns(4)
            date = c[3].date_input("תאריך", datetime.date.today())
            symbol = c[2].text_input("סימבול")
            name = c[1].text_input("שם החברה")
            quantity = c[0].text_input("כמות")
            c2 = st.columns(4)
            entry = c2[3].text_input("מחיר כניסה $")
            target = c2[2].text_input("מחיר יעד $")
            stop = c2[1].text_input("סטופ לוס $")
            exit_price = c2[0].text_input("מחיר יציאה $ (אופ')")
            c3 = st.columns(2)
            action = c3[1].selectbox("פעולה", ["קנייה (Buy)", "מכירה (Sell)", "מעקב (Watch)"])
            status = c3[0].selectbox("סטטוס", ["פתוחה (Open)", "סגורה (Closed)"])
            thesis = st.text_area("תזה / נימוק", height=80)
            lesson = st.text_area("לקח שנלמד", height=80)
            if st.form_submit_button("➕ הוסף עסקה"):
                sym = symbol.strip().upper()
                if not sym:
                    st.error("יש להזין סימבול")
                else:
                    st.session_state.journal.append({
                        "date": date.isoformat(), "symbol": sym, "name": name.strip() or sym,
                        "action": action, "quantity": num(quantity), "entry_price": num(entry),
                        "target_price": num(target), "stop_loss": num(stop),
                        "exit_price": num(exit_price), "status": status,
                        "thesis": thesis.strip(), "lesson": lesson.strip(),
                    })
                    save_json(JOURNAL_FILE, st.session_state.journal)
                    st.session_state.flash = "העסקה נוספה ✓"
                    st.rerun()

    jr = st.session_state.journal

    # סטטיסטיקה
    def pnl_pct(t):
        e, x = t.get("entry_price"), t.get("exit_price")
        if not e or x is None:
            return None
        p = (x - e) / e * 100
        return -p if "Sell" in str(t.get("action", "")) else p

    closed_pnls = [pnl_pct(t) for t in jr if "Closed" in str(t.get("status", ""))]
    closed_pnls = [p for p in closed_pnls if p is not None]
    wins = sum(1 for p in closed_pnls if p > 0)
    win_rate = (wins / len(closed_pnls) * 100) if closed_pnls else 0.0
    avg_pnl = (sum(closed_pnls) / len(closed_pnls)) if closed_pnls else 0.0
    top = Counter(t["symbol"] for t in jr if t.get("symbol")).most_common(3)
    top_str = ", ".join("%s(%d)" % (s, c) for s, c in top) if top else "-"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("סך עסקאות", len(jr))
    m2.metric("אחוז הצלחה", "%.1f%%" % win_rate)
    m3.metric("ממוצע רווח/הפסד %", "%+.2f%%" % avg_pnl)
    m4.metric("סימבולים נסחרים", top_str)

    # טבלה + מחיקה
    if jr:
        rows = [{
            "תאריך": t["date"], "סימבול": t["symbol"], "פעולה": t["action"],
            "כמות": t.get("quantity"), "מחיר כניסה": t.get("entry_price"),
            "יעד": t.get("target_price"), "סטופ": t.get("stop_loss"),
            "סטטוס": t["status"],
        } for t in jr]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        d1, d2 = st.columns([3, 1])
        idx = d1.selectbox("בחר עסקה למחיקה (לפי שורה)",
                           list(range(len(jr))),
                           format_func=lambda i: "%d: %s %s" % (i + 1, jr[i]["date"], jr[i]["symbol"]))
        if d2.button("🗑️ מחק עסקה"):
            del st.session_state.journal[idx]
            save_json(JOURNAL_FILE, st.session_state.journal)
            st.rerun()
    else:
        st.info("היומן ריק.")


# ===================================================================
#  מודול 4: גרפים
# ===================================================================
def tab_charts():
    st.subheader("📈 גרפים")
    pf = st.session_state.portfolio
    layout = dict(paper_bgcolor=COLORS["bg"], plot_bgcolor=COLORS["surface"],
                  font=dict(color=COLORS["text"]), margin=dict(t=40, b=40, l=40, r=40))

    col1, col2 = st.columns(2)

    # עוגה
    with col1:
        st.markdown("##### התפלגות התיק לפי משקל")
        total = sum(p["shares"] * p["current_price"] for p in pf)
        if pf and total > 0:
            fig = go.Figure(go.Pie(
                labels=[p["symbol"] for p in pf],
                values=[p["shares"] * p["current_price"] for p in pf],
                hole=0.3, textinfo="label+percent",
            ))
            fig.update_layout(**layout)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("אין נתונים")

    # עמודות
    with col2:
        st.markdown("##### רווח/הפסד $ לפי פוזיציה")
        if pf:
            syms = [p["symbol"] for p in pf]
            pnls = [p["shares"] * (p["current_price"] - p["entry_price"]) for p in pf]
            bar_colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in pnls]
            fig = go.Figure(go.Bar(x=syms, y=pnls, marker_color=bar_colors))
            fig.update_layout(**layout)
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("אין נתונים")

    # קו
    st.markdown("##### שווי התיק לאורך זמן")
    hist = st.session_state.history
    if hist:
        fig = go.Figure(go.Scatter(
            x=[h["timestamp"] for h in hist], y=[h["value"] for h in hist],
            mode="lines+markers", line=dict(color=COLORS["accent"], width=2),
            fill="tozeroy", fillcolor="rgba(41,128,185,0.15)",
        ))
        fig.update_layout(**layout)
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("אין היסטוריה עדיין")


# ===================================================================
#  ראשי
# ===================================================================
def main():
    st.set_page_config(page_title="Stock Tracker Pro", page_icon="📈", layout="wide")
    inject_css()
    load_state()

    st.title("📈 Stock Tracker Pro")
    st.caption("מעקב תיק מניות מקצועי — כל הנתונים מוזנים ידנית")

    # הודעת הצלחה ששורדת rerun
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))

    t1, t2, t3, t4 = st.tabs(["📊 תיק מניות", "🔍 ניתוח מניה", "📒 יומן מסחר", "📈 גרפים"])
    with t1:
        tab_portfolio()
    with t2:
        tab_analysis()
    with t3:
        tab_journal()
    with t4:
        tab_charts()


if __name__ == "__main__":
    main()
