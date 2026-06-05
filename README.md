# Stock Tracker Pro 📈

אפליקציית שולחן עבודה מקצועית למעקב תיק מניות (Wall Street – NYSE/NASDAQ),
כתובה ב‑Python + Tkinter. כל הנתונים מוזנים **ידנית** – ללא APIs חיצוניים.

A professional desktop stock portfolio tracker built with Python + Tkinter.
All data is entered manually – no external APIs. UI is in Hebrew (RTL) with a dark theme.

## תכונות (Features)

- **📊 תיק מניות** – טבלת פוזיציות עם חישוב אוטומטי של עלות, שווי, רווח/הפסד ($ ו‑%),
  משקל בתיק, כרטיסי סיכום והתראות חכמות (Take Profit / Stop Loss / Concentration Risk).
- **🔍 ניתוח מניה** – טופס ניתוח פונדמנטלי + טכני + בניית תזה (Bull/Bear), שמירת ניתוחים עם חותמת זמן.
- **📒 יומן מסחר** – תיעוד עסקאות, סטטיסטיקות (Win Rate, ממוצע רווח, סימבולים נסחרים).
- **📈 גרפים** – עוגת התפלגות תיק, עמודות רווח/הפסד, וגרף שווי תיק לאורך זמן.

## דרישות (Requirements)

```bash
pip install matplotlib pandas
```

`tkinter` מגיע בדרך כלל עם Python (בלינוקס: `sudo apt install python3-tk`).

## הרצה (Run)

```bash
python stock_tracker.py
```

## שמירת נתונים (Data)

הנתונים נשמרים אוטומטית בקבצי JSON מקומיים באותה תיקייה:
`portfolio.json`, `analyses.json`, `journal.json`, `history.json`.
