# פריסת הבדיקה ב־Google Cloud

## מצב נוכחי

- פרויקט: **M5Stack**, מזהה `m5stack-515405`. זהו היעד העדכני במקום `hey-usa`.
- אזור: `europe-west1`, שירות: `voice-relay`.
- הפרויקט קושר לחשבון חיוב פתוח. מזהה חשבון החיוב אינו נשמר במאגר.
- שירות בדיקה פרטי נוצר ב־Cloud Run; נדרשת זהות Google מורשית כדי לקרוא לו.
- גרסת Google מקוד `aa49bb8` נפרסה; `voice-relay-00003-x28` אומתה: גישה אנונימית ל־`/health` נחסמת ב־403,
  גישה מורשית מחזירה200עם `ok:true`, ו־`/ready` מחזיר503עם `configured:false`.
- מפתחות Groq, OpenRouter ו־Tavily נשמרו: גרסה1פעילה בכל סוד, נבדקו מטא־נתונים בלבד.
- המשתמש אישר Google Text-to-Speech במקום Azure לאחר שנדרש שדרוג חשבון Azure.
- המכשיר עדיין משתמש בקושחה הקודמת; הוא לא מחובר לשירות הזה.

גרסאות שנפרסו ותוצאות בדיקות חיות נרשמות ב־[PR1](https://github.com/shanimosco47-pixel/M5StackCoresS3/pull/1).
הרצה חוזרת של כלי ההכנה אומתה גם היא ושמרה על גרסת סוד המכשיר הקיימת.
תשובת מוכנות שלילית בלי מפתחות היא התוצאה הרצויה בשלב זה, ואינה בדיקת שיחה אמיתית.

## הגבלת עלויות

נוצרה ואומתה תקרת **Cloud Run** חודשית של **5ILS**, במצב `CONFIGURED`, בפרויקט זה בלבד.
זו תקרת שירות לפי עלות משוערת ברוטו, לא תקרת חיוב כוללת לכל החשבון.
בנוסף הוגדר תקציב התראות של5ILSלכל עלויות הפרויקט. ההתראה הכוללת אינה עוצרת חיובים.
Cloud Build, Artifact Registry, אחסון, Google Text-to-Speech וספקי AI חיצוניים אינם נעצרים באמצעות תקרת Cloud Run.
בקשות שכבר רצות ועלויות מתמשכות עשויות להמשיך בהתאם למגבלות המתועדות של Google.

הגדרות השירות: אפס מופעים מינימליים, מופע מקסימלי אחד, CPUאחד,256MiB,
תהליך ASGIאחד ועד4בקשותHTTPבמקביל, כדי לאפשר ביטול ובדיקות בזמן טיפול בשיחה.
האפליקציה עצמה מתירה שיחה אחת בלבד בכל רגע. מגבלות הבקשות בזיכרון אינן מגבלות חיוב עמידות.

מקורות: [תקרות הוצאה](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps),
[חיוב Cloud Run](https://docs.cloud.google.com/run/docs/configuring/billing-settings).

## זהויות וסודות

`m5-voice-runtime` הוא חשבון השירות של זמן הריצה, ללא מפתחות JSON מקומיים.
ניתנה לו הרשאת `secretAccessor` רק למכולות הסודות של העוזר.
`m5-voice-builder` הוא חשבון נפרד לבנייה עם `roles/run.builder`, ללא הרשאת קריאת סודות העוזר.

ב־Secret Manager הוכנו:

| שם הסוד | תוכן בשלב זה |
|---|---|
| `voice-relay-device-secret` | סוד אקראי שנוצר ולא הוצג או נשמר בקוד |
| `voice-relay-groq` | גרסה1פעילה; תקינות מול הספק טרם נבדקה |
| `voice-relay-openrouter` | גרסה1פעילה; תקינות מול הספק טרם נבדקה |
| `voice-relay-azure` | ריק ואינו נדרש במסלול Google |
| `voice-relay-tavily` | גרסה1פעילה; תקינות מול הספק טרם נבדקה |

בגרסה `voice-relay-00004-52k` מופו בנוסף שלושת סודות הספקים, כל אחד לגרסה1קבועה.
מודל שיחה טרם נקבע, וברירת המחדל `PRIVATE_PROVIDERS_APPROVED=false` נשמרת.
כלי deploy_private.ps1 יוצר מחדש סביבת בדיקה בסיסית עם סוד המכשיר בלבד; מיפויי ספקים
והגדרות המודל דורשים שחזור מפורש לאחר הרצה חוזרת שלו.

## כלים לשחזור התהליך

נדרשים Google Cloud SDK והתחברות לחשבון בעל הרשאות בפרויקט. יש להפעיל בפרויקט את
Cloud Run, Secret Manager, Cloud Build, Artifact Registry, IAM, Cloud Billing ו־Billing Budgets APIs,
ולהכין את שני חשבונות השירות לעיל ואת הרשאות הבונה לפני ההפעלה.

`tools/cloud/bootstrap.py` מאמת את שיוך החיוב, יוצר או מאמת תקרה והתראה, ומכין סודות והרשאות.
הוא מסרב להחליף תקציב קיים בעל הגדרות שונות, ואינו מציג ערכי סודות או אסימוני גישה.
`tools/cloud/deploy_private.ps1` מפעיל בדיקת תקרה לפני הבנייה ופורש שירות פרטי.

לדוגמה, משורש המאגר ב־PowerShell:

```powershell
$m5BillingAccount = (gcloud billing projects describe m5stack-515405 --project=m5stack-515405 --format='value(billingAccountName)').Trim() -replace '^billingAccounts/', ''
./tools/cloud/deploy_private.ps1 -ProjectId m5stack-515405 -BillingAccountId $m5BillingAccount -CloudRunMonthlyCap 5
python tools/cloud/verify_private.py --project=m5stack-515405
```

בדיקה חיה תקינה אמורה לאמת חסימת גישה אנונימית, `/health` עם200למשתמש מורשה,
ו־`/ready` עם503ו־`configured:false` כל עוד אין מפתחות. בדיקה זו אינה מפעילה ספק AI.
אין להשתמש ב־`/healthz` בענן: Google Frontend חסם אותו עוד לפני האפליקציה.
נוספו `/health` ו־`/ready`, ונתיבי zנשארו רק לתאימות מקומית.
[מגבלת הנתיבים הרשמית](https://docs.cloud.google.com/run/docs/known-issues#reserved-url-paths).

## הזנת מפתחות בהמשך

לא לשלוח מפתחות בצ׳אט או לשמור אותם בקובץ במאגר. ניתן להזין גרסאות חדשות ישירות
ב־[Secret Manager של הפרויקט](https://console.cloud.google.com/security/secret-manager?project=m5stack-515405),
או להריץ **במסוף האישי שלך**:

```powershell
python tools/cloud/set_provider_secrets.py --project=m5stack-515405
```

הקלט מוסתר ונשלח ל־Secret Manager דרך stdin, בלי ארגומנט שמכיל מפתח ובלי קובץ זמני.
קלט ריק מדלג על ספק, וערכים קודמים נשמרים כגרסאות. הכלי מסרב לפעול בלי מסוף אינטראקטיבי.
הוא אינו מאמת מפתח מול ספק ואינו מפעיל שיחה או גישה ציבורית.

לאחר מכן נצטרך לאמת קריאות אמיתיות ומודל OpenRouter מאושר,
למפות את הסודות לשירות, לאמת פרטיות ומגבלות עלות אצל הספקים, ולממש ולבדוק את מתאם המכשיר.
יש להשאיר את השירות פרטי עד להשלמת הגנות העלות והאימות. הודעת סיום העדכון במכשיר
תופעל רק לאחר ששיחה, עברית, חיפוש וקטיעה נבדקו עליו בפועל.

## Google במקום Azure — 21 בנובמבר 2026

הופעל `texttospeech.googleapis.com`. לזהות הריצה בלבד נוספה הרשאת
`roles/serviceusage.serviceUsageConsumer`; לא נוצר או הורד מפתח JSON.
הגדרות ההפעלה החדשות: `TTS_PROVIDER=google`, `GOOGLE_CLOUD_PROJECT=m5stack-515405`.
הקול קבוע בקוד: `he-IL-Standard-A`, פלט LINEAR16 בקצב16kHz עם כותרת WAV.
סוד Azure ואזור Azure אינם נדרשים. כלי הזנת המפתחות הישן עדיין מציע Azure כאפשרות — אפשר לדלג.

קריאת Google אמיתית בזהות משתמש ה־CLI החזירה200וקובץ תקין באורך5.893375שניות,
188632בתים, מונו PCM16. בנוסף, אותו קוד מאותה תמונת שרת עבר בדיקת זהות Cloud Run בפועל,
בחשבון `m5-voice-runtime`: משימת בדיקה `voice-relay-tts-check-w6bzr` הפיקה WAVתקין,
117632בתים/3.674625שניות. המשימה הוסרה; לא הוגדרה הרצה חוזרת. אין בכך בדיקת שמיעה במכשיר.
המפתחות והאסימונים נשארו בזיכרון התהליך ולא הוצגו. השרת אינו תומך אוטומטית בזהות CLI מקומית.

מחיר Standard הרשמי שנבדק: 4מיליון תווים לחודש ללא עלות, ואחריהם $4למיליון תווים.
אין לראות במכסה התחייבות לאפס חיוב כולל, ותקרת Cloud Run אינה מכסה את השירות הזה.
[מחירון Google](https://cloud.google.com/text-to-speech/pricing),
[אימות בזהות השירות](https://docs.cloud.google.com/docs/authentication/rest).

בדיקות ספקים עם קלט סינתטי/ציבורי בלבד: Groq תמלל את קטע Google, Tavily החזיר4מקורות,
ואימות מפתח OpenRouter החזיר200. ניסיונות יצירת תשובה בשלושה מודלים חינמיים נכשלו;
ב־Gemma26Bאובחנה תשובת429מהספק. אין עדיין מודל מאומת או שיחה מלאה; לא נרכשו קרדיטים.
