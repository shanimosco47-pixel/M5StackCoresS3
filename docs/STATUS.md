# מצב העבודה — 21 בנובמבר 2026

## המכשיר והשרת כעת

קושחת Relay החדשה נצרבה ל־CoreS3 ונבדקה מול שירות הענן. לאחר שהמשתמש הפעיל מחדש
את ההוטספוט, המכשיר התחבר, קיבל שמע ב־16kHz והשמיע תשובות לפי לוגי הניגון.
אישור המשתמש לתצוגת הכתוביות, לחיפוש ולקטיעה בגרסה החדשה עדיין ממתין.

המסלול הנוכחי: Groq Whisper לתמלול בעברית, `openai/gpt-oss-120b` דרך Groq לשיחה,
Tavily לחיפוש ו־Google `he-IL-Standard-A` להפקת קול. אין צורך בחשבון Azure.
המשתמש אישר במפורש חיפוש רגיל לאחר שנמסר שתנאי Tavily מאפשרים שימוש בשאילתות לשיפור מודלים.
OpenRouter ו־Azure נשארו חלופות ניתנות להגדרה; לא נרכשו קרדיטים או מנויים.

## מה אומת

- שרשרת ענן אמיתית מקלט קולי בעברית עד תשובה קולית עם ארבעה מקורות.
- שירות `voice-relay`, פרויקט `m5stack-515405`, אזור `europe-west1`, גרסה `voice-relay-00008-r6v`.
- גישה ישירה מהתקן: בדיקות בריאות ומוכנות מחזירות 200; קול ללא סוד מכשיר או עם סוד שגוי נדחה ב־401.
- בקשה כפולה נדחתה ב־409 גם לאחר החלפת מופע השרת, בלי לשנות את המונה העמיד.
- מגבלות Firestore: 6 פניות בדקה, 100 ביום, ושמירת תקציב של עד 3 מיליון תווי TTS בחודש.
  כל פנייה שומרת 1,000 תווים מראש, ללא החזר על כישלון; אין במונים תמלולים או תוכן שיחות.
- 71 בדיקות שרת/ספקים/תקציב ומגבלות עברו, ועוד 8 בדיקות של שער הסקירה העצמאית.
- בדיקות ליבת הקושחה עברו: WAV, מעטפת v3, VAD, הפסקה/חזרה להקלטה ומגבלת עומק JSON.
- שתי בניות ESP-IDF 5.5.5 עברו אחרי תיקוני הסקירה. הקושחה משתמשת ב־Quad PSRAM וב־16MB Flash.
- הצריבה אימתה גיבובים. האפליקציה בלבד ב־`0x1a0000`; טבלאות האתחול והשחזור נשמרו.
- נלקח גיבוי מקומי מלא חדש של 16MB. נשמרו Wi-Fi, עוצמה 180 ו־`bargein_en=1`.
- ההגדרות הפרטיות עודכנו רק עבור ספק Relay, כתובת השרת וסוד המכשיר, עם בדיקת CRC ושימור יתר הרשומות.

## תיקונים שאותרו בבדיקה

הסקירה העצמאית מצאה ותיקנו עיכוב בחזרה להקלטה לאחר קטיעה, וסיכון לעומק JSON.
בדיקת המכשיר איתרה כשלי TLS לסירוגין; נבחרה אסטרטגיית RX יציבה של הספרייה לאחר ההזדהות,
והמכשיר השמיע תשובה בגרסה המתוקנת. נשארו הודעות poll לא־קטלניות בזמן המתנה לרשת.
יש להפריד בין הודעות אלה לבין כשל תשובה ממשי, ולבחון יציבות לפי בדיקות המשתמש.

## עלות, פרטיות ומצב הסיום

תקרת שירות Cloud Run בסך 5 ILS לחודש אומתה. התראת פרויקט כללית בסכום זה אינה תקרה קשיחה.
בנייה, אחסון, Firestore, Google TTS וספקים אחרים אינם נעצרים באמצעות תקרת Cloud Run.
המגבלות העמידות מגבילות את קריאות האפליקציה ואינן התחייבות לאפס עלות בכל החשבון.

לא מופץ מפתח Google JSON. ההתקן משתמש בסוד אקראי אישי, ומפתחות הספקים נשארים בענן.
אין שמירת היסטוריה או פרסונה אישית בגרסה הזו. אין טענה לאפס שמירה אצל כל ספק.

הסקירה העצמאית ב־GitHub פועלת ואישרה את שרת `e601a44` ללא ממצאים; שינוי הקושחה
והתיעוד האחרון דורש סקירה חדשה על ראש ה־PR. גרסאות ותוצאות נוספות נשמרות ב־PR1.
הודעת הסיום החד־פעמית טרם הופעלה: תופעל רק אחרי אישור בדיקות המכשיר.

ראו `CLOUD_DEPLOYMENT.md`, `BUILD_AND_RECOVERY.md`, `VALIDATION.md` ו־`project_active_session.md`.

## User feedback and responsive status — 2026-11-21

User confirmed Hebrew conversation worked, then reported a black screen. Device audio/task logs remained
alive; USB reset restored faces (user confirmed). Cause is not established; no speculative PMIC repair.
Added render frame/brightness/phase metadata. Latest app flashed/hash verified: Hebrew status badge
shows ready/hearing/thinking/speaking/error and immediate400ms touch acknowledgement. Brief VAD noise
returns to ready. Loggedrenderframes1449/brightness127, interruption, then new speech capture.
Final user confirmation of the badge/search/interrupt remains pending; completion notice is unarmed.

Generic Tavily snippets still yielded an old dollar quote in live testing. CurrentUSD/ILSquestions now
use BankofIsrael official API directly, validate rate/unit/currency/date (at most4daysold, not future),
and speak an exact representative quote with publicationdate, never relabeled a live market quote.
Live local lookup returned the20.11.2026publication. Other changing facts force search and receiveUTCdate.
71server tests pass, including stale/future/malformed/unavailable rate regressions.

Context and latency question: current turns are stateless and audio is a complete WAV before playback.
Short conversation memory and streaming remain follow-up work, not implemented features.
