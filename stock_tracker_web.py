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
import html
import datetime
from collections import Counter

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# משיכת נתונים עדכניים מהאינטרנט (אופציונלי) - yfinance / Yahoo Finance
try:
    import yfinance as yf
    YF_AVAILABLE = True
except Exception:
    YF_AVAILABLE = False

# ניתוח חכם של חדשות (אופציונלי) - Claude API
try:
    import anthropic
    from pydantic import BaseModel, Field
    ANTHROPIC_AVAILABLE = True

    class NewsAnalysis(BaseModel):
        related_tickers: list[str] = Field(description="רשימת טיקרים של מניות הקשורות לכתבה")
        intro: str = Field(description="משפט הקדמה קצר בעברית")
        sentiment: str = Field(description="האם הכתבה חיובית / שלילית / ניטרלית למניות הקשורות")
        summary: str = Field(description="סיכום תמציתי של הכתבה בעברית")
        recommendation: str = Field(description="המלצת הסוכן בעברית לגבי הכותרת")
        urgency: int = Field(description="ציון חשיבות/דחיפות מ-1 (לא דחוף) עד 5 (הכי דחוף)")
except Exception:
    ANTHROPIC_AVAILABLE = False


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
#  משיכת נתונים מהאינטרנט (Yahoo Finance / yfinance)
# ===================================================================
# רשימת השדות הפונדמנטליים והטכניים (תואם ללשונית הניתוח)
FUND_KEYS = ["revenue_growth", "gross_margin", "net_margin", "fcf", "pe",
             "forward_pe", "ev_ebitda", "peg", "debt_equity", "roe", "insider"]
TECH_KEYS = ["price", "ma50", "ma150", "ma200", "rsi", "atr", "vol_ratio",
             "high52", "low52"]


def _rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)
    return float(rsi.iloc[-1])


def _atr_pct(h, price, period=14):
    high, low, close = h["High"], h["Low"], h["Close"]
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period).mean().iloc[-1]
    return float(atr) / price * 100 if price else None


def fetch_price(ticker):
    """מחזיר (מחיר, שגיאה) - מחיר נוכחי בלבד, מהיר."""
    if not YF_AVAILABLE:
        return None, "מודול המשיכה לא זמין"
    try:
        t = yf.Ticker(ticker)
        price = None
        try:
            fi = t.fast_info
            price = fi.get("lastPrice") if hasattr(fi, "get") else getattr(fi, "last_price", None)
        except Exception:
            price = None
        if price is None:
            h = t.history(period="5d")
            if len(h):
                price = float(h["Close"].iloc[-1])
        if price:
            return round(float(price), 2), None
        return None, "לא נמצא מחיר לטיקר %s" % ticker
    except Exception as exc:
        return None, str(exc)[:120]


def fetch_quote(ticker):
    """מחזיר (מחיר, שם חברה, שגיאה) - מהיר, למילוי טופס הפוזיציה."""
    if not YF_AVAILABLE:
        return None, "", "מודול המשיכה לא זמין"
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            price, _ = fetch_price(ticker)
        name = info.get("shortName") or info.get("longName") or ""
        if not price:
            return None, name, "לא נמצא מחיר לטיקר %s" % ticker
        return round(float(price), 2), name, None
    except Exception as exc:
        return None, "", str(exc)[:120]


def fetch_fundamentals(ticker):
    """מחזיר (נתונים, שגיאה) - תמונה פונדמנטלית + טכנית רחבה."""
    if not YF_AVAILABLE:
        return None, "מודול המשיכה לא זמין"
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        h = t.history(period="1y")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None and len(h):
            price = float(h["Close"].iloc[-1])
        if not price and not info.get("trailingPE"):
            return None, "לא נמצאו נתונים לטיקר %s (אולי שגוי?)" % ticker

        def pct(v):
            return round(v * 100, 2) if isinstance(v, (int, float)) else None

        def r2(v):
            return round(v, 2) if isinstance(v, (int, float)) else None

        de = info.get("debtToEquity")
        data = {
            "revenue_growth": pct(info.get("revenueGrowth")),
            "gross_margin": pct(info.get("grossMargins")),
            "net_margin": pct(info.get("profitMargins")),
            "fcf": info.get("freeCashflow"),
            "pe": r2(info.get("trailingPE")),
            "forward_pe": r2(info.get("forwardPE")),
            "ev_ebitda": r2(info.get("enterpriseToEbitda")),
            "peg": r2(info.get("trailingPegRatio") or info.get("pegRatio")),
            "debt_equity": r2(de / 100) if isinstance(de, (int, float)) else None,
            "roe": pct(info.get("returnOnEquity")),
            "insider": pct(info.get("heldPercentInsiders")),
            "price": r2(price),
            "ma50": r2(info.get("fiftyDayAverage")),
            "ma200": r2(info.get("twoHundredDayAverage")),
            "high52": r2(info.get("fiftyTwoWeekHigh")),
            "low52": r2(info.get("fiftyTwoWeekLow")),
            "ma150": None, "rsi": None, "atr": None, "vol_ratio": None,
        }
        if len(h) >= 150:
            data["ma150"] = r2(float(h["Close"].rolling(150).mean().iloc[-1]))
        if len(h) >= 30:
            try:
                data["rsi"] = r2(_rsi(h["Close"]))
            except Exception:
                pass
            try:
                data["atr"] = r2(_atr_pct(h, price))
            except Exception:
                pass
            try:
                vol = h["Volume"]
                avg14 = float(vol.iloc[-15:-1].mean())
                data["vol_ratio"] = round(float(vol.iloc[-1]) / avg14, 2) if avg14 else None
            except Exception:
                pass
        # שם החברה (בונוס)
        data["_name"] = info.get("shortName") or info.get("longName") or ""
        return data, None
    except Exception as exc:
        return None, str(exc)[:120]


def _fmt_cell(val):
    """פורמט תא בטבלה: מספרים עם פסיקים, ריק -> מקף."""
    if val is None:
        return "-"
    if isinstance(val, float):
        if val != val:  # NaN
            return "-"
        if val == int(val):
            return "{:,}".format(int(val))
        return "{:,.2f}".format(val)
    if isinstance(val, int):
        return "{:,}".format(val)
    s = str(val).strip()
    return s if s else "-"


def render_table(df, color_cols=()):
    """
    מצייר טבלה בעברית מימין-לשמאל (RTL), שמתאימה את עצמה לרוחב המסך
    בלי גלילה אופקית. עמודות צבועות (רווח/הפסד) מקבלות ירוק/אדום.
    """
    cols = list(df.columns)
    headers = "".join(
        '<th style="padding:7px 4px; text-align:center; font-weight:bold;'
        ' border-bottom:2px solid %s; word-wrap:break-word;">%s</th>' % (COLORS["bg"], c)
        for c in cols
    )
    body = ""
    for i, (_, row) in enumerate(df.iterrows()):
        bg = COLORS["surface"] if i % 2 == 0 else COLORS["bg"]
        cells = ""
        for c in cols:
            val = row[c]
            style = "padding:6px 4px; text-align:center; border-bottom:1px solid %s; word-wrap:break-word;" % COLORS["bg"]
            if c in color_cols and isinstance(val, (int, float)) and val == val:
                clr = COLORS["green"] if val > 0 else (COLORS["red"] if val < 0 else COLORS["text"])
                style += " color:%s; font-weight:bold;" % clr
            cells += '<td style="%s">%s</td>' % (style, _fmt_cell(val))
        body += '<tr style="background:%s;">%s</tr>' % (bg, cells)

    html = (
        '<div style="direction:rtl; width:100%; overflow-x:hidden;">'
        '<table style="width:100%; border-collapse:collapse; direction:rtl;'
        f' table-layout:fixed; font-size:12px; color:{COLORS["text"]};">'
        f'<thead><tr style="background:{COLORS["accent"]}; color:white;">{headers}</tr></thead>'
        f'<tbody>{body}</tbody></table></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ===================================================================
#  סורק שוק (Market Scanner)
# ===================================================================
SECTOR_ETFS = {
    "XLK": "טכנולוגיה", "XLF": "פיננסים", "XLE": "אנרגיה", "XLV": "בריאות",
    "XLI": "תעשייה", "XLY": "צריכה מחזורית", "XLP": "צריכה בסיסית",
    "XLB": "חומרים", "XLRE": "נדל\"ן", "XLU": "תשתיות", "XLC": "תקשורת",
}
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META",
                     "TSLA", "AMD", "NFLX", "AVGO"]


@st.cache_data(ttl=900, show_spinner=False)
def scan_sectors():
    """מומנטום סקטורים: תשואות שבוע/חודש/3 חודשים ל-11 קרנות הסקטור."""
    try:
        d = yf.download(list(SECTOR_ETFS), period="6mo", progress=False)["Close"]
    except Exception:
        return None
    rows = []
    for etf, name in SECTOR_ETFS.items():
        if etf not in d:
            continue
        s = d[etf].dropna()
        if len(s) < 30:
            continue
        last = float(s.iloc[-1])

        def ret(n):
            return round((last / float(s.iloc[-n]) - 1) * 100, 2) if len(s) > n else None

        rows.append({"סקטור": name, "ETF": etf, "שבוע %": ret(5),
                     "חודש %": ret(21), "3 חודשים %": ret(63)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("חודש %", ascending=False, na_position="last").reset_index(drop=True)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def scan_stocks(tickers):
    """סורק סיגנלים על רשימת מעקב. מחזיר טבלה ממוינת לפי 'ציון' (0-5)."""
    tickers = list(tickers)
    try:
        data = yf.download(tickers, period="1y", progress=False, group_by="ticker")
    except Exception:
        return None
    if data is None or len(data) == 0:
        return None
    multi = isinstance(data.columns, pd.MultiIndex)
    rows = []
    for tk in tickers:
        try:
            df = data[tk] if multi else data
            close = df["Close"].dropna()
            vol = df["Volume"].dropna()
            if len(close) < 60:
                continue
            price = float(close.iloc[-1])
            ma50 = float(close.rolling(50).mean().iloc[-1])
            ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
            r = _rsi(close)
            high52 = float(close.tail(252).max())
            from_high = (price / high52 - 1) * 100
            avg_vol = float(vol.tail(20).mean())
            vol_spike = (float(vol.iloc[-1]) / avg_vol) if avg_vol else None
            score, flags = 0, []
            if price > ma50:
                score += 1; flags.append("מעל MA50")
            if ma200 and price > ma200:
                score += 1; flags.append("מעל MA200")
            if r and 50 <= r <= 72:
                score += 1; flags.append("RSI חיובי")
            if from_high > -5:
                score += 1; flags.append("קרוב לשיא")
            if vol_spike and vol_spike > 1.5:
                score += 1; flags.append("קפיצת נפח")
            rows.append({
                "טיקר": tk, "מחיר": round(price, 2), "ציון": score,
                "מרחק משיא %": round(from_high, 1),
                "RSI": round(r, 1) if r else None,
                "נפח X": round(vol_spike, 2) if vol_spike else None,
                "סיגנלים": ", ".join(flags) or "-",
            })
        except Exception:
            continue
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("ציון", ascending=False).reset_index(drop=True)
    return df


@st.cache_data(ttl=900, show_spinner=False)
def get_news(ticker, limit=6):
    """כותרות חדשות אחרונות לטיקר (תומך במבנה הישן והחדש של yfinance)."""
    if not YF_AVAILABLE:
        return []
    try:
        items = yf.Ticker(ticker).news or []
    except Exception:
        return []
    out = []
    for it in items[:limit]:
        c = it.get("content", it) if isinstance(it, dict) else {}
        title = c.get("title") or (it.get("title") if isinstance(it, dict) else None)
        if not title:
            continue
        url = ""
        for k in ("canonicalUrl", "clickThroughUrl"):
            v = c.get(k)
            if isinstance(v, dict) and v.get("url"):
                url = v["url"]; break
        if not url and isinstance(it, dict):
            url = it.get("link", "")
        prov = c.get("provider")
        prov = prov.get("displayName", "") if isinstance(prov, dict) else (it.get("publisher", "") if isinstance(it, dict) else "")
        t = c.get("pubDate") or c.get("displayTime") or ""
        summary = c.get("summary") or c.get("description") or (it.get("summary") if isinstance(it, dict) else "") or ""
        out.append({"title": title, "url": url, "provider": prov,
                    "time": str(t)[:10], "summary": summary})
    return out


# ----- ניתוח חדשות חכם (Claude API) -----
NEWS_SYSTEM = (
    "אתה אנליסט שוק הון מנוסה. תקבל כותרת ותקציר של כתבת חדשות על מניות וול-סטריט. "
    "נתח אותה והחזר בעברית: טיקרים קשורים, משפט הקדמה, האם היא חיובית/שלילית/ניטרלית, "
    "סיכום תמציתי, המלצת סוכן מעשית לגבי הכותרת, וציון חשיבות/דחיפות מ-1 (לא דחוף) עד 5 "
    "(חדשות מהותית שמזיזה שוק). ענה תמציתי וענייני, בעברית בלבד."
)


def _anthropic_key():
    try:
        k = st.secrets["ANTHROPIC_API_KEY"]
        return str(k) if k else None
    except Exception:
        return None


def _anthropic_model():
    try:
        m = st.secrets["ANTHROPIC_MODEL"]
        return str(m) if m else "claude-opus-4-8"
    except Exception:
        return "claude-opus-4-8"


def analyze_news_item(title, summary):
    """מנתח כתבה בודדת ב-Claude ומחזיר (dict, שגיאה)."""
    if not ANTHROPIC_AVAILABLE:
        return None, "מודול ה-AI אינו מותקן"
    key = _anthropic_key()
    if not key:
        return None, "לא הוגדר מפתח API"
    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.parse(
            model=_anthropic_model(),
            max_tokens=1024,
            system=NEWS_SYSTEM,
            messages=[{
                "role": "user",
                "content": "כותרת הכתבה: %s\n\nתקציר/תיאור: %s" % (title, summary or "(אין תקציר)"),
            }],
            output_format=NewsAnalysis,
        )
        a = resp.parsed_output
        return {
            "tickers": list(a.related_tickers or []),
            "intro": a.intro,
            "sentiment": a.sentiment,
            "summary": a.summary,
            "recommendation": a.recommendation,
            "urgency": max(1, min(5, int(a.urgency))),
        }, None
    except anthropic.AuthenticationError:
        return None, "מפתח ה-API אינו תקין"
    except anthropic.RateLimitError:
        return None, "חריגה ממכסת הבקשות — נסה שוב מאוחר יותר"
    except Exception as exc:
        return None, str(exc)[:160]


def render_news_analysis(a):
    """מציג את ניתוח ה-AI של כתבה בעברית, מימין לשמאל."""
    urg = a["urgency"]
    ucolor = COLORS["red"] if urg >= 4 else (COLORS["accent"] if urg == 3 else COLORS["muted"])
    sent = a["sentiment"]
    scolor = COLORS["green"] if "חיוב" in sent else (COLORS["red"] if "שליל" in sent else COLORS["muted"])
    tickers = ", ".join(a["tickers"]) if a["tickers"] else "—"

    def esc(x):
        return html.escape(str(x))

    dots = "●" * urg + "○" * (5 - urg)
    block = (
        '<div style="direction:rtl; background:%s; border-right:4px solid %s;'
        ' padding:10px 12px; border-radius:8px; margin:2px 0 12px 0; font-size:13px;'
        ' color:%s; line-height:1.7;">'
        '<div>🎯 <b>טיקרים קשורים:</b> %s</div>'
        '<div>📝 %s</div>'
        '<div>סנטימנט: <b style="color:%s">%s</b></div>'
        '<div><b>סיכום:</b> %s</div>'
        '<div>🤖 <b>המלצת הסוכן:</b> %s</div>'
        '<div>🚨 <b>חשיבות:</b> <span style="color:%s">%s (%d/5)</span></div>'
        '</div>'
    ) % (COLORS["surface"], ucolor, COLORS["text"], esc(tickers), esc(a["intro"]),
         scolor, esc(sent), esc(a["summary"]), esc(a["recommendation"]),
         ucolor, dots, urg)
    st.markdown(block, unsafe_allow_html=True)


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

    # ניקוי שדות הטופס לאחר הוספה מוצלחת
    if st.session_state.pop("_clear_pf_form", False):
        for _k in ("pf_symbol", "pf_name", "pf_shares", "pf_entry", "pf_current", "pf_fetch_tk"):
            st.session_state.pop(_k, None)

    # ----- טופס הזנה -----
    with st.expander("➕ הזנת / עדכון פוזיציה", expanded=not pf):
        # משיכת מחיר ושם אוטומטית
        if YF_AVAILABLE:
            ff1, ff2 = st.columns([3, 1])
            ftk = ff1.text_input("📥 משיכה אוטומטית — הזן סימבול (לדוגמה AAPL)", key="pf_fetch_tk")
            ff2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if ff2.button("📥 משוך מחיר ושם", key="pf_fetch_btn"):
                tk = (ftk or "").strip().upper()
                if not tk:
                    st.warning("הזן סימבול תחילה")
                else:
                    with st.spinner("מושך נתונים עדכניים..."):
                        price, cname, err = fetch_quote(tk)
                    if err:
                        st.error("שגיאה: %s" % err)
                    else:
                        st.session_state["pf_symbol"] = tk
                        if price is not None:
                            st.session_state["pf_current"] = str(price)
                        if cname:
                            st.session_state["pf_name"] = cname
                        st.success("✓ נמשך מחיר %s עבור %s. השלם מניות ומחיר כניסה, ולחץ הוסף." % (price, tk))

        f1, f2, f3, f4, f5 = st.columns(5)
        symbol = f5.text_input("סימבול (AAPL)", key="pf_symbol")
        name = f4.text_input("שם החברה", key="pf_name")
        shares = f3.text_input("מספר מניות", key="pf_shares")
        entry = f2.text_input("מחיר כניסה $", key="pf_entry")
        current = f1.text_input("מחיר נוכחי $", key="pf_current")
        if st.button("➕ הוסף / עדכן פוזיציה"):
            _add_position(symbol, name, shares, entry, current)

    # ----- עדכון מחירים מהאינטרנט -----
    if pf and YF_AVAILABLE:
        u1, u2 = st.columns([3, 1])
        u1.caption("עדכון אוטומטי של המחיר הנוכחי לכל הפוזיציות מ-Yahoo Finance")
        if u2.button("📥 עדכן מחירים"):
            updated, failed = 0, []
            with st.spinner("מושך מחירים עדכניים..."):
                for p in st.session_state.portfolio:
                    price, err = fetch_price(p["symbol"])
                    if price:
                        p["current_price"] = price
                        updated += 1
                    else:
                        failed.append(p["symbol"])
            save_json(PORTFOLIO_FILE, st.session_state.portfolio)
            log_history()
            msg = "עודכנו %d מחירים ✓" % updated
            if failed:
                msg += " (לא נמצאו: %s)" % ", ".join(failed)
            st.session_state.flash = msg
            st.rerun()

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
        render_table(df, color_cols=["רווח/הפסד $", "רווח/הפסד %"])
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
    st.session_state["_clear_pf_form"] = True
    st.rerun()


# ===================================================================
#  מודול 2: ניתוח מניה
# ===================================================================
def tab_analysis():
    st.subheader("🔍 ניתוח מניה")

    # ----- משיכת נתונים עדכניים מהאינטרנט -----
    if YF_AVAILABLE:
        fc1, fc2 = st.columns([3, 1])
        fetch_tk = fc1.text_input("📥 משיכת נתונים אוטומטית — הזן טיקר (לדוגמה AAPL)", key="fetch_ticker_an")
        fc2.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if fc2.button("📥 משוך נתונים", key="fetch_an_btn"):
            tk = (fetch_tk or "").strip().upper()
            if not tk:
                st.warning("הזן טיקר תחילה")
            else:
                with st.spinner("מושך נתונים עדכניים מ-Yahoo Finance..."):
                    data, err = fetch_fundamentals(tk)
                if err:
                    st.error("שגיאה במשיכה: %s" % err)
                else:
                    st.session_state["analysis_symbol"] = tk
                    for k in FUND_KEYS:
                        v = data.get(k)
                        st.session_state["fa_%s" % k] = "" if v is None else str(v)
                    for k in TECH_KEYS:
                        v = data.get(k)
                        st.session_state["ta_%s" % k] = "" if v is None else str(v)
                    st.success("✓ הנתונים של %s נמשכו ומולאו אוטומטית. בדוק, השלם תזה, ושמור." % tk)
    else:
        st.info("משיכת נתונים אוטומטית אינה זמינה (חבילת yfinance חסרה).")

    with st.form("analysis_form"):
        symbol = st.text_input("סימבול מניה לניתוח", key="analysis_symbol")

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
        render_table(pd.DataFrame(rows))


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
        render_table(pd.DataFrame(rows))
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
#  שער סיסמה (Password gate)
# ===================================================================
def _expected_password():
    """הסיסמה נשמרת ב-Secrets של Streamlit (app_password). אם לא הוגדרה - אין נעילה."""
    try:
        pw = st.secrets["app_password"]
        return str(pw) if pw else None
    except Exception:
        return None


def check_password():
    """
    שער כניסה: אם הוגדרה סיסמה ב-Secrets, חוסמים עד שמזינים אותה נכון.
    אם לא הוגדרה סיסמה כלל - הגישה חופשית (כדי למנוע נעילה בטעות).
    """
    expected = _expected_password()
    if not expected:
        return True  # לא הוגדרה סיסמה - גישה חופשית
    if st.session_state.get("auth_ok"):
        return True

    st.markdown("## 🔒 כניסה מוגנת")
    st.caption("האפליקציה מוגנת בסיסמה. הזן את הסיסמה כדי להמשיך.")
    pw = st.text_input("סיסמה", type="password", key="pw_input")
    if st.button("כניסה"):
        if pw == expected:
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("סיסמה שגויה ❌")
    return False


# ===================================================================
#  מודול 5: סורק שוק
# ===================================================================
def tab_scanner():
    st.subheader("🔎 סורק שוק")
    if not YF_AVAILABLE:
        st.info("הסורק דורש חיבור לאינטרנט (חבילת yfinance).")
        return
    st.caption("⚠️ הסורק מסמן מועמדים בולטים לפי סיגנלים — אלו לא הבטחות. שיקול הדעת תמיד שלך.")
    if st.button("🔄 רענן נתונים"):
        st.cache_data.clear()
        st.rerun()

    # ----- מומנטום סקטורים -----
    st.markdown("### 📊 מומנטום סקטורים")
    with st.spinner("טוען נתוני סקטורים..."):
        sec = scan_sectors()
    if sec is not None and not sec.empty:
        render_table(sec, color_cols=["שבוע %", "חודש %", "3 חודשים %"])
        top = sec.iloc[0]
        if top["חודש %"] is not None:
            st.success("🔥 הסקטור החזק החודש: %s (%+.1f%%)" % (top["סקטור"], top["חודש %"]))
    else:
        st.warning("לא ניתן לטעון נתוני סקטורים כרגע. נסה 'רענן נתונים'.")

    # ----- סורק מניות -----
    st.markdown("### 🎯 סורק מניות (רשימת מעקב)")
    default = ",".join(DEFAULT_WATCHLIST)
    wl_text = st.text_input("רשימת מעקב — טיקרים מופרדים בפסיק", value=default, key="watchlist_text")
    tickers = tuple(t.strip().upper() for t in wl_text.split(",") if t.strip())
    if tickers:
        with st.spinner("סורק מניות..."):
            scan = scan_stocks(tickers)
        if scan is not None and not scan.empty:
            render_table(scan, color_cols=["מרחק משיא %"])
            st.caption("**ציון** = כמה סיגנלים חיוביים (0–5): מעל MA50, מעל MA200, RSI חיובי, קרוב לשיא, קפיצת נפח. ככל שגבוה — בולט יותר.")
        else:
            st.warning("לא נמצאו נתונים לרשימה. בדוק שהטיקרים תקינים.")

    # ----- חדשות אחרונות -----
    st.markdown("### 📰 חדשות אחרונות")
    if tickers:
        sel = st.selectbox("בחר טיקר לחדשות", tickers, key="news_ticker")
        ai_on = False
        if ANTHROPIC_AVAILABLE and _anthropic_key():
            ai_on = st.toggle("🤖 הוסף ניתוח חכם (AI) בעברית מתחת לכל כתבה", value=False, key="news_ai_toggle")
        elif ANTHROPIC_AVAILABLE:
            st.caption("💡 לניתוח AI בעברית: הוסף ANTHROPIC_API_KEY ב-Settings → Secrets של Streamlit.")
        with st.spinner("טוען חדשות..."):
            news = get_news(sel)
        if news:
            ai_cache = st.session_state.setdefault("news_ai_cache", {})
            for n in news:
                title = "[%s](%s)" % (n["title"], n["url"]) if n["url"] else n["title"]
                meta = "  \n<small>%s · %s</small>" % (n["provider"] or "—", n["time"] or "")
                st.markdown("• **%s**%s" % (title, meta), unsafe_allow_html=True)
                if ai_on:
                    ckey = n["title"]
                    if ckey not in ai_cache:
                        with st.spinner("מנתח כתבה ב-AI..."):
                            ai_cache[ckey] = analyze_news_item(n["title"], n.get("summary", ""))
                    data, err = ai_cache[ckey]
                    if data:
                        render_news_analysis(data)
                    else:
                        st.caption("⚠️ ניתוח AI לא זמין: %s" % err)
                st.markdown("<hr style='margin:6px 0; border-color:%s'>" % COLORS["surface"], unsafe_allow_html=True)
        else:
            st.info("אין חדשות זמינות לטיקר זה כרגע.")


# ===================================================================
#  ראשי
# ===================================================================
def main():
    st.set_page_config(page_title="Stock Tracker Pro", page_icon="📈", layout="wide")
    inject_css()

    # שער סיסמה - רק מי שיודע את הסיסמה ייכנס
    if not check_password():
        st.stop()

    load_state()

    st.title("📈 Stock Tracker Pro")
    st.caption("מעקב תיק מניות מקצועי — כל הנתונים מוזנים ידנית")

    # הודעת הצלחה ששורדת rerun
    if st.session_state.get("flash"):
        st.success(st.session_state.pop("flash"))

    t1, t5, t2, t3, t4 = st.tabs(
        ["📊 תיק מניות", "🔎 סורק שוק", "🔍 ניתוח מניה", "📒 יומן מסחר", "📈 גרפים"])
    with t1:
        tab_portfolio()
    with t5:
        tab_scanner()
    with t2:
        tab_analysis()
    with t3:
        tab_journal()
    with t4:
        tab_charts()


if __name__ == "__main__":
    main()
