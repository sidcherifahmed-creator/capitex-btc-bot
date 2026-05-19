import os, requests, pandas as pd, numpy as np
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TWELVE_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
RR_TP1, RR_TP2 = 2.0, 3.0

# ── نفس دوال المؤشرات من bot_v3 ───────────────────────────────────────────────
def rsi(s,p=14):
    d=s.diff(); g=d.clip(lower=0).ewm(com=p-1,min_periods=p).mean()
    l=(-d.clip(upper=0)).ewm(com=p-1,min_periods=p).mean()
    return 100-100/(1+g/l)

def macd(s):
    m=s.ewm(span=12,adjust=False).mean()-s.ewm(span=26,adjust=False).mean()
    sig=m.ewm(span=9,adjust=False).mean(); return m,sig,m-sig

def bb(s,p=20,k=2):
    mid=s.rolling(p).mean(); std=s.rolling(p).std()
    return mid+k*std, mid, mid-k*std

def atr(df,p=14):
    tr=pd.concat([df.high-df.low,(df.high-df.close.shift()).abs(),
                  (df.low-df.close.shift()).abs()],axis=1).max(axis=1)
    return tr.ewm(com=p-1,min_periods=p).mean()

def supertrend(df,p=10,m=3):
    a=atr(df,p); hl2=(df.high+df.low)/2
    up=hl2+m*a; dn=hl2-m*a
    trend=pd.Series(1,index=df.index)
    for i in range(1,len(df)):
        if df.close.iloc[i]>up.iloc[i-1]: trend.iloc[i]=1
        elif df.close.iloc[i]<dn.iloc[i-1]: trend.iloc[i]=-1
        else: trend.iloc[i]=trend.iloc[i-1]
    return trend

def stoch(df,k=14,d=3):
    lo=df.low.rolling(k).min(); hi=df.high.rolling(k).max()
    K=100*(df.close-lo)/(hi-lo+1e-9); return K,K.rolling(d).mean()

def mfi(df,p=14):
    tp=(df.high+df.low+df.close)/3
    v=pd.Series(np.ones(len(df)),index=df.index)
    mf=tp*v
    pos=mf.where(tp>tp.shift(),0).rolling(p).sum()
    neg=mf.where(tp<tp.shift(),0).rolling(p).sum()
    return 100-100/(1+pos/(neg+1e-9))

def cci(df,p=20):
    tp=(df.high+df.low+df.close)/3
    return (tp-tp.rolling(p).mean())/(0.015*tp.rolling(p).apply(lambda x:np.mean(np.abs(x-x.mean()))))

def williams_r(df,p=14):
    hi=df.high.rolling(p).max(); lo=df.low.rolling(p).min()
    return -100*(hi-df.close)/(hi-lo+1e-9)

def dmi(df,p=14):
    hi_diff=(df.high-df.high.shift()).clip(lower=0)
    lo_diff=(df.low.shift()-df.low).clip(lower=0)
    plus_dm=hi_diff.where(hi_diff>lo_diff,0)
    minus_dm=lo_diff.where(lo_diff>hi_diff,0)
    a=atr(df,p)
    plus_di=100*plus_dm.ewm(com=p-1,min_periods=p).mean()/a
    minus_di=100*minus_dm.ewm(com=p-1,min_periods=p).mean()/a
    dx=100*(plus_di-minus_di).abs()/(plus_di+minus_di+1e-9)
    return plus_di, minus_di, dx.ewm(com=p-1,min_periods=p).mean()

def vwap(df):
    tp=(df.high+df.low+df.close)/3
    v=pd.Series(np.ones(len(df)),index=df.index)
    return (tp*v).cumsum()/v.cumsum()

def compute_all(df):
    df=df.copy(); c=df.close
    df["ema9"]   = c.ewm(span=9,  adjust=False).mean()
    df["ema21"]  = c.ewm(span=21, adjust=False).mean()
    df["ema50"]  = c.ewm(span=50, adjust=False).mean()
    df["rsi"]    = rsi(c)
    m,sig,hist   = macd(c)
    df["macd"]=m; df["macd_sig"]=sig; df["macd_hist"]=hist
    bbu,bbm,bbl  = bb(c)
    df["bb_upper"]=bbu; df["bb_lower"]=bbl
    df["atr"]    = atr(df)
    df["vwap"]   = vwap(df)
    df["st_trend"]= supertrend(df)
    K,D          = stoch(df); df["stoch_k"]=K; df["stoch_d"]=D
    df["mfi"]    = mfi(df)
    df["cci"]    = cci(df)
    df["willr"]  = williams_r(df)
    pdi,mdi,adx  = dmi(df)
    df["plus_di"]=pdi; df["minus_di"]=mdi; df["adx"]=adx
    return df.dropna().reset_index(drop=True)

def score_signal(df):
    r=df.iloc[-1]; p=df.iloc[-2]
    bs=0; ss=0

    if r.ema9>r.ema21 and p.ema9<=p.ema21: bs+=1.5
    if r.ema9<r.ema21 and p.ema9>=p.ema21: ss+=1.5
    if r.close>r.ema50: bs+=0.5
    else: ss+=0.5
    if r.rsi<35: bs+=1
    elif r.rsi>65: ss+=1
    if r.macd_hist>0 and p.macd_hist<=0: bs+=1.5
    if r.macd_hist<0 and p.macd_hist>=0: ss+=1.5
    if r.close<r.bb_lower: bs+=1
    if r.close>r.bb_upper: ss+=1
    if r.st_trend==1 and p.st_trend==-1: bs+=1.5
    if r.st_trend==-1 and p.st_trend==1: ss+=1.5
    if r.close>r.vwap: bs+=0.5
    else: ss+=0.5
    if r.stoch_k<25 and r.stoch_k>r.stoch_d: bs+=0.5
    if r.stoch_k>75 and r.stoch_k<r.stoch_d: ss+=0.5
    if r.adx>25:
        if r.plus_di>r.minus_di: bs+=0.5
        else: ss+=0.5
    if r.mfi<30: bs+=0.5
    elif r.mfi>70: ss+=0.5
    if r.cci<-100: bs+=0.5
    elif r.cci>100: ss+=0.5
    if r.willr<-80: bs+=0.5
    elif r.willr>-20: ss+=0.5

    if bs>=5 and bs>ss: return "BULLISH", round(bs,1)
    if ss>=5 and ss>bs: return "BEARISH", round(ss,1)
    return "NEUTRAL", 0

def find_ob(df, direction):
    n=len(df)
    for i in range(n-2,max(n-15,1),-1):
        c=df.iloc[i]
        body=abs(c.close-c.open)
        avg=df.close.iloc[max(0,i-10):i].sub(df.open.iloc[max(0,i-10):i]).abs().mean()
        if avg==0: continue
        if direction=="BULLISH" and c.close<c.open and body>avg*0.5:
            if i+1<n and df.close.iloc[i+1]>c.high:
                return {"high":c.high,"low":c.low,"mid":(c.high+c.low)/2}
        if direction=="BEARISH" and c.close>c.open and body>avg*0.5:
            if i+1<n and df.close.iloc[i+1]<c.low:
                return {"high":c.high,"low":c.low,"mid":(c.high+c.low)/2}
    return None

def find_fvg(df, direction):
    n=len(df)
    for i in range(n-3,max(n-12,1),-1):
        c1=df.iloc[i-1]; c3=df.iloc[i+1]
        if direction=="BULLISH" and c3.low>c1.high:
            return {"mid":(c3.low+c1.high)/2}
        if direction=="BEARISH" and c3.high<c1.low:
            return {"mid":(c1.low+c3.high)/2}
    return None

# ── جلب البيانات ───────────────────────────────────────────────────────────────
def get_data(outputsize=2000):
    try:
        r=requests.get("https://api.twelvedata.com/time_series",
            params={"symbol":"BTC/USD","interval":"15min",
                    "outputsize":outputsize,"apikey":TWELVE_API_KEY},timeout=20)
        data=r.json()
    except Exception as e:
        print(f"[API] {e}"); return None
    if "values" not in data:
        print(f"[Data] {data}"); return None
    df=pd.DataFrame(data["values"])
    for c in ["open","high","low","close"]:
        df[c]=pd.to_numeric(df[c])
    df["datetime"]=pd.to_datetime(df["datetime"])
    df=df.iloc[::-1].reset_index(drop=True)
    print(f"البيانات: {len(df)} شمعة | {df.datetime.iloc[0].date()} -> {df.datetime.iloc[-1].date()}")
    return df

# ── محرك الـ Backtest ──────────────────────────────────────────────────────────
def run_backtest(df_raw, min_score=5):
    df_full = compute_all(df_raw)
    trades = []
    last_idx = -5

    print(f"\nتحليل {len(df_full)} شمعة...\n")

    for i in range(60, len(df_full)-30):
        if i - last_idx < 4: continue

        window = df_full.iloc[max(0,i-60):i+1].reset_index(drop=True)
        if len(window) < 40: continue

        direction, score = score_signal(window)
        if direction == "NEUTRAL" or score < min_score: continue

        ob  = find_ob(window, direction)
        fvg = find_fvg(window, direction)

        price = df_full.close.iloc[i]
        if direction == "BULLISH":
            sl_base = ob["low"] if ob else df_full.low.iloc[i-3:i].min()
            sl      = sl_base - price*0.0005
            limit   = ob["mid"] if ob else (fvg["mid"] if fvg else price*0.999)
            risk    = limit - sl
            if risk <= 0 or risk/limit < 0.001: continue
            tp1 = limit + risk*RR_TP1
            tp2 = limit + risk*RR_TP2
        else:
            sl_base = ob["high"] if ob else df_full.high.iloc[i-3:i].max()
            sl      = sl_base + price*0.0005
            limit   = ob["mid"] if ob else (fvg["mid"] if fvg else price*1.001)
            risk    = sl - limit
            if risk <= 0 or risk/limit < 0.001: continue
            tp1 = limit - risk*RR_TP1
            tp2 = limit - risk*RR_TP2

        if risk/limit < 0.0015: continue

        # محاكاة الصفقة
        result = None; tp1_hit = False
        for j in range(i+1, min(i+48, len(df_full))):
            h=df_full.high.iloc[j]; l=df_full.low.iloc[j]
            if direction=="BULLISH":
                if l<=sl: result="SL"; break
                if not tp1_hit and h>=tp1: tp1_hit=True
                if tp1_hit and h>=tp2: result="TP2"; break
            else:
                if h>=sl: result="SL"; break
                if not tp1_hit and l<=tp1: tp1_hit=True
                if tp1_hit and l<=tp2: result="TP2"; break

        if result is None:
            result = "TP1" if tp1_hit else None
        if result is None: continue

        R = RR_TP2 if result=="TP2" else (RR_TP1 if result=="TP1" else -1.0)

        trades.append({
            "date": df_full.datetime.iloc[i].strftime("%Y-%m-%d %H:%M"),
            "dir":  direction,
            "score": score,
            "entry": round(limit,1),
            "sl":    round(sl,1),
            "tp1":   round(tp1,1),
            "tp2":   round(tp2,1),
            "result": result,
            "R":     R,
        })
        last_idx = i

    return trades

# ── تقرير ──────────────────────────────────────────────────────────────────────
def report(trades, min_score):
    if not trades:
        print(f"لا صفقات بنقاط >= {min_score}")
        return 0

    df_t = pd.DataFrame(trades)
    total  = len(df_t)
    wins   = len(df_t[df_t.result.isin(["TP1","TP2"])])
    losses = len(df_t[df_t.result=="SL"])
    wr     = wins/total*100
    total_r= df_t.R.sum()
    avg_r  = df_t.R.mean()

    gw = df_t[df_t.R>0].R.sum()
    gl = abs(df_t[df_t.R<0].R.sum())
    pf = round(gw/gl,2) if gl>0 else 999

    dd=0; cur=0
    for r in df_t.R:
        cur=cur+1 if r<0 else 0
        dd=max(dd,cur)

    signals_per_day = total / max(1, (pd.to_datetime(df_t.date.iloc[-1])-pd.to_datetime(df_t.date.iloc[0])).days)

    print("="*52)
    print(f"  Capitex v3 Backtest | نقاط >= {min_score}")
    print("="*52)
    print(f"إجمالي الصفقات      : {total}")
    print(f"إشارات/يوم          : {signals_per_day:.1f}")
    print(f"نسبة الفوز          : {wins}/{total}  ({wr:.1f}%)")
    print(f"TP2 مكتمل           : {len(df_t[df_t.result=='TP2'])}")
    print(f"TP1 فقط             : {len(df_t[df_t.result=='TP1'])}")
    print(f"SL                  : {losses}")
    print("-"*52)
    print(f"إجمالي R            : {total_r:+.1f}R")
    print(f"متوسط R/صفقة        : {avg_r:+.2f}R")
    print(f"Profit Factor       : {pf}")
    print(f"أسوأ خسائر متتالية  : {dd}")
    print("="*52)

    print(f"\nآخر 15 صفقة (نقاط >= {min_score}):")
    print(f"{'التاريخ':<17} {'اتجاه':<8} {'نقاط':<5} {'نتيجة':<5} {'R':>5}")
    print("-"*45)
    for _,row in df_t.tail(15).iterrows():
        icon="✅" if row.result in ["TP1","TP2"] else "❌"
        print(f"{row.date:<17} {row.dir:<8} {row.score:<5} {icon}{row.result:<4} {row.R:>+.1f}R")

    df_t.to_csv(f"backtest_v3_score{min_score}.csv", index=False)
    print(f"\nتم الحفظ: backtest_v3_score{min_score}.csv")
    return wr

# ── التشغيل ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Capitex v3 Backtest — جلب البيانات...")
    df = get_data(outputsize=2000)
    if df is None: exit()

    # نختبر بثلاثة مستويات من النقاط لنجد الأفضل
    for min_s in [5, 6, 7]:
        trades = run_backtest(df, min_score=min_s)
        wr = report(trades, min_s)
        print()
