# Stock Tracker Pro 📈

אפליקציית מעקב תיק מניות מקצועית (Wall Street – NYSE/NASDAQ). כל הנתונים מוזנים **ידנית** – ללא APIs חיצוניים.
זמינה בשתי גרסאות:

- **🖥️ גרסת שולחן עבודה** (`stock_tracker.py`) – Python + Tkinter, רצה כחלון על המחשב.
- **🌐 גרסת Web** (`stock_tracker_web.py`) – Python + Streamlit, נפתחת בדפדפן – גם במחשב וגם **בטלפון**.

שתי הגרסאות חולקות את אותם קבצי נתונים (JSON), כך שאפשר לעבור ביניהן.

## תכונות (Features)

- **📊 תיק מניות** – טבלת פוזיציות עם חישוב אוטומטי של עלות, שווי, רווח/הפסד ($ ו‑%),
  משקל בתיק, כרטיסי סיכום והתראות חכמות (Take Profit / Stop Loss / Concentration Risk).
- **🔍 ניתוח מניה** – טופס ניתוח פונדמנטלי + טכני + בניית תזה (Bull/Bear), שמירת ניתוחים עם חותמת זמן.
- **📒 יומן מסחר** – תיעוד עסקאות, סטטיסטיקות (Win Rate, ממוצע רווח, סימבולים נסחרים).
- **📈 גרפים** – עוגת התפלגות תיק, עמודות רווח/הפסד, וגרף שווי תיק לאורך זמן.

## הרצה — גרסת שולחן עבודה (Desktop)

```bash
pip install matplotlib pandas
python stock_tracker.py
```

`tkinter` מגיע בדרך כלל עם Python (בלינוקס: `sudo apt install python3-tk`).

## הרצה — גרסת Web (לרבות מהטלפון)

```bash
pip install -r requirements.txt
streamlit run stock_tracker_web.py
```

יתפתח דף בדפדפן (ברירת מחדל: http://localhost:8501).

### גישה מהטלפון באותו WiFi
כשהאפליקציה רצה, Streamlit מציג גם כתובת **Network URL** (למשל `http://192.168.1.20:8501`).
הקלד אותה בדפדפן של הטלפון כשהוא מחובר לאותו WiFi כמו המחשב.
> בווינדוז, אם זה לא נטען – אשר ל-Python גישה ברשת ב-Windows Firewall, או הרץ עם:
> `streamlit run stock_tracker_web.py --server.address=0.0.0.0`

### גישה מכל מקום (ענן חינמי)
דחוף את הריפו ל-GitHub והעלה ל-[Streamlit Community Cloud](https://share.streamlit.io):
בחר את הריפו, את הענף, וקובץ ראשי `stock_tracker_web.py`. תקבל קישור קבוע שנפתח בכל טלפון.
> בענן הנתונים זמניים (filesystem ארעי); לשימוש אישי זה תקין, אך לא לאחסון לטווח ארוך.

## שמירת נתונים (Data)

הנתונים נשמרים אוטומטית בקבצי JSON מקומיים באותה תיקייה:
`portfolio.json`, `analyses.json`, `journal.json`, `history.json`.
