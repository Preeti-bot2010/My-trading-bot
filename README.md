# Options Paper Trading Bot — Free, Mobile-Only Setup (No Server, No Cost)

## ⚠️ Options Ke Baare Me Padhna Zaroori Hai

Yeh bot ab **Nifty options (CE/PE buying)** trade karta hai, equity nahi.
Options me risk ka nature equity se bahot alag hai:
- **Time decay (theta)** — premium roz apne aap girta hai, chahe Nifty
  kahin na jaaye
- Chhoti si move bhi premium ko 30-50%+ move kar sakti hai — **dono taraf**
- Yeh purely **option buying** karta hai (selling/writing nahi) — isliye
  aapka max loss hamesha **premium tak limited** hai, unlimited nahi. Yeh
  jaan-boojh kar simplest/safest structure choose kiya gaya hai.

## Aapke Diye Rules Implement Kiye Gaye

| Aapka Rule | Kaise Implement Kiya (config.py me) |
|---|---|
| Expiry ≤4 din bache toh next week ka option lo | `MIN_DAYS_TO_EXPIRY = 4` — `pick_expiry()` automatically roll karta hai |
| Same din close, carry forward nahi | `SQUARE_OFF_TIME = "15:20"` — chahe SL/target hit ho ya na ho, force exit |
| (Extra) Opening/closing volatility avoid karo | `NO_NEW_ENTRY_BEFORE = "09:30"`, `NO_NEW_ENTRY_AFTER = "14:45"` |
| (Extra) Ek time pe zyada risk mat lo | `MAX_CONCURRENT_OPTION_POSITIONS = 1` |
| (Extra) Premium-based SL/target (underlying-based nahi) | `OPTION_SL_PCT = 30`, `OPTION_TARGET_PCT = 60` |

Sab config.py me hain — aap chaho toh yeh numbers tweak kar sakte ho, but
backtest/paper-trade karke pehle dekhna better hai kaunse values kaam
karte hain.

## Important: Instrument Schema Verify Karna Padega

`angel_data_feed.py` me option-chain aur index-lookup logic AngelOne ke
standard instrument master schema pe based hai, lekin main isse live
credentials ke bina test nahi kar saka (mere paas aapke API keys nahi
hain). Pehli baar chalane pe agar `get_index_ltp` ya `get_option_contract`
error de, toh `instruments_cache.json` file (jo pehla run download karega)
me apne index/option ka exact `symbol`/`name` field dhundh ke
`config.INDEX_SPOT_SYMBOL` ya related fields match kar lena — chhoti si
naming difference ho sakti hai jo main yahan predict nahi kar sakta.

## Equity + Options Dono Ek Saath

Bot ab har cycle me **dono** check karta hai — equity watchlist (5 stocks)
aur Nifty options — **do alag virtual portfolios** ke saath (dono ka
apna-apna ₹1,00,000 virtual capital, apna P&L, apna trade log). Dashboard
pe dono sections alag-alag dikhte hain, taaki aap dono strategies ka
accuracy independently compare kar sakein. Kisi ek ka result dusre ko
affect nahi karta.

## Telegram Notifications (Optional, Recommended)

Jab bhi bot koi trade le (entry ya exit), aapko turant Telegram pe message
mil jayega — dashboard khole bina bhi. Setup 2 minute ka hai:

1. Telegram me **@BotFather** ko search karke open karo, `/newbot` bhejo,
   ek naam do — woh aapko ek **token** dega (jaisa
   `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)
2. Apne naye bot ko Telegram me search karke ek **koi bhi message bhej do**
   (isse zaroori hai warna next step kaam nahi karega)
3. Browser me yeh URL kholo (apna token daal ke):
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   Isme aapko `"chat":{"id":123456789,...}` jaisa kuch dikhega — woh number
   hi aapka **chat ID** hai
4. GitHub repo → Settings → Secrets and variables → Actions → do naye
   secrets add karo: `TELEGRAM_TOKEN` aur `TELEGRAM_CHAT_ID`

Bas. Agla bot run se hi Telegram pe alerts aana shuru ho jaayenge (entry
aur exit dono ke liye, equity aur options dono trades ke liye). Agar yeh
secrets add nahi karte, bot bina kisi error ke normally chalta rahega —
Telegram sirf optional hai.

---


## Kaise Kaam Karta Hai

- **GitHub Actions** har 10 minute me (market hours ke dauraan) GitHub ke apne
  free servers pe bot ka ek "check cycle" chalata hai — login, data fetch,
  scoring, paper trade entry/exit. **Aapka phone ya browser khula hona zaroori
  nahi hai** — yeh GitHub ke servers pe chalta hai, aapke device pe nahi.
- Har run ke baad, result ek `status.json` file me save hoke wapas repo me
  commit ho jaata hai.
- **GitHub Pages** ek free web link deta hai (`index.html` dashboard) jo
  `status.json` padhkar mobile pe dikhata hai — bilkul AngelOne app jaisa,
  bas link open karo aur dekho.
- Poora setup **sirf mobile browser se** ho sakta hai (github.com pe login
  karke) — koi laptop/PC zaroori nahi.

## Mobile Se Setup — Step by Step

### 1. GitHub account banao (agar nahi hai)
github.com pe mobile browser se free account bana lo.

### 2. Naya repository banao
- github.com pe "+" icon → "New repository"
- Naam do (jaise `my-trading-bot`), **Public** rakho (Private bhi chalega,
  bas Actions minutes limited honge free tier me)
- "Create repository" dabao

### 3. Saari files add karo

**Sabse reliable mobile tarika:** "Add file" → **"Upload files"** try karo
pehle (agar aapka phone folder-structure preserve karke upload kar leta
hai, to sabse fast yehi hai — saari files ek saath drag/select karo).

**Agar upload folder structure preserve nahi karta** (mobile browsers me
kabhi-kabhi aisa hota hai, especially `.github/workflows/bot.yml` wali
nested file ke liye), tab yeh guaranteed-to-work tarika use karo:
- "Add file" → **"Create new file"**
- Filename box me **poora path type karo**, jaise `.github/workflows/bot.yml`
  — GitHub khud folder bana dega
- Us file ka content paste karo, "Commit changes" dabao
- Har file ke liye yeh repeat karo (config.py, strategy.py,
  angel_data_feed.py, paper_trader.py, run_once.py, backtest.py,
  requirements.txt, index.html, status.json, .gitignore)

Thoda time lagega (9 files), lekin mobile se 100% kaam karega.

**Important:** `.env.example` upload karna optional hai — usme real
secrets nahi hain. Real secrets kabhi bhi kisi file me nahi jaate, woh
sirf step 4 wale secure "Secrets" section me jaate hain.

### 4. Secrets add karo (yeh secure hai, code me kahin nahi dikhta)
Repo → **Settings** → **Secrets and variables** → **Actions** → **New
repository secret**. Yeh secrets ek-ek karke add karo:

| Secret Name | Value |
|---|---|
| `ANGEL_API_KEY` | Aapki SmartAPI key |
| `ANGEL_CLIENT_CODE` | Aapka login client code |
| `ANGEL_PIN` | Aapka 4-digit trading MPIN |
| `ANGEL_TOTP_SECRET` | 2FA setup ke waqt mila secret key |
| `TELEGRAM_TOKEN` (optional) | @BotFather se mila bot token |
| `TELEGRAM_CHAT_ID` (optional) | @userinfobot se mila aapka chat ID |

Telegram alerts optional hain — agar in do secrets ko khaali chhod do,
bot bina Telegram ke normal chalega, bas alerts nahi aayenge.

**⚠️ Agar aapne kabhi bhi yeh credentials kisi chat/message me paste kiye
hain (jaise humne is conversation me kiya), unhe turant regenerate/rotate
kar lein pehle** — TOTP secret AngelOne SmartAPI portal se, Telegram token
@BotFather se `/revoke` karke.

### 5. Actions enable karo
Repo → **Actions** tab → agar prompt aaye "I understand my workflows,
enable them" → click kardo.

### 6. Bot ko pehli baar manually chalao (test ke liye)
Actions tab → left side "Paper Trading Bot" → **Run workflow** button →
Run. 1-2 minute me complete ho jaayega. Agar error aaye, "run-bot" job
kholke red X wali step ka log padho — usually credential ya symbol name
ki galti hoti hai.

### 7. Dashboard (GitHub Pages) enable karo
Repo → **Settings** → **Pages** (left sidebar) → "Source" me "Deploy from
a branch" select karo → Branch: `main`, folder: `/ (root)` → Save.

1-2 minute baad wahi page pe ek link milega jaisa:
`https://yourusername.github.io/my-trading-bot/`

**Yehi link aapka "app" hai** — isse phone ke home screen pe "Add to Home
Screen" karke bilkul app icon jaisa bana sakte ho. Isi link ko roz kholke
progress dekho.

## Roz Kya Hoga

- Bot automatically 9:15 AM - 3:30 PM (Mon-Fri) ke beech har ~10 min me
  check karega, watchlist ke stocks pe scoring strategy chalayega, aur
  jo bhi grade A+/B mile, paper trade "lega".
- Dashboard link kholke aap live dekh sakte ho: kaunsa position open hai,
  kitna virtual profit/loss hua, aur har trade ka record.
- Koi bhi real paisa involve nahi — yeh purely paper trading hai jab tak
  aap khud `LIVE_TRADING` badalke `place_live_order()` implement na karo
  (`paper_trader.py` me — jaan-boojh kar disabled rakha hai).

## Free Tier Limits (Honestly Batana Zaroori Hai)

- Public repo → GitHub Actions **unlimited free minutes**. Private repo →
  2000 min/month free (yeh bot ~40 runs/day × ~1-2 min = kaafi kam use
  karega, limit tak nahi pahunchega).
- Cron scheduling **exact time guarantee nahi karta** — GitHub load ke
  hisaab se 5-15 min tak delay ho sakta hai. 15-min candle strategy ke
  liye theek hai, second-level scalping ke liye nahi.
- Agar bot ko aur zyada frequent (jaise har 1 min) chalana ho ya truly
  continuous websocket-based live monitoring chahiye ho, tab hi ek real
  server (jaisa pehle discuss kiya tha) ka fayda milega — abhi ke liye,
  jab tak accuracy prove nahi hoti, yeh free setup kaafi hai.

## Purane Documents Se Farak

Aapko ab kuch bhi manually upload/run nahi karna — ek baar upar wale steps
follow karke setup karne ke baad, sab kuch automatic hai. Dashboard link
hi aapka daily touchpoint hai.
