"""Hinglish / Gen Z short-form fixer: rewrites chat slang so the voice reads it properly."""
import os
import re

on_unknown = None   # optional callback(word) for short words we do not know yet


def has_devanagari(t):
    return re.search(r"[\u0900-\u097F]", t) is not None


# ---------- Hinglish / Gen Z short-form fixer ----------
# Format: short1,short2=replacement   (Devanagari replacement makes the Hindi voice say it properly)
WORDS_TXT = """
kr=कर
krna,karna=करना
krde,krdo,kardo,krdena=कर दो
kro,karo=करो
rha,raha=रहा
rhi,rahi=रही
rhe,rahe=रहे
nhi,nahi,nhin,nai,nhii,nahin=नहीं
hn,hnn,haan,han=हाँ
hnji,hanji=हाँ जी
h,hai,hae=है
hoga,hga=होगा
hogi,hgi=होगी
hoge,hge=होगे
hu,hun,hoon=हूँ
ho=हो
bht,bhot,bohot,bahut,bhut=बहुत
bhai,bhaiya,bhaii=भाई
bhi,bhii=भी
kyu,kyun,kyon,kyo=क्यों
kya,kyaa=क्या
kb,kab=कब
kse,kaise=कैसे
kaisa,ksa=कैसा
kaun,kon=कौन
kch,kuch=कुछ
kahan,kaha=कहाँ
mera,mra=मेरा
meri,mri=मेरी
mere,mre=मेरे
mujhe,mje,mjhe,muje=मुझे
tumhara,tmhara=तुम्हारा
tumhe,tmhe,tumhein=तुम्हें
tumko,tmko=तुमको
tum,tm=तुम
tu=तू
hum=हम
ye,yeh=ये
vo,wo,woh=वो
isko=इसको
usko=उसको
apna=अपना
ka=का
ke=के
ki=की
ko=को
na=ना
ji=जी
bas=बस
sab=सब
sabko,sbko=सबको
acha,accha,achha,achaa,acchaa=अच्छा
thik,theek,thk,thikk=ठीक
yaar,yar,yr,yaarr=यार
abhi,abi=अभी
aur=और
lekin,lkn,lekn=लेकिन
par,pr=पर
mtlb,matlab=मतलब
smjh,samjh,samaj=समझ
pta,pata=पता
gana,gaana,gna=गाना
mast,mst=मस्त
sahi,shi=सही
badhiya,bdiya,bdhiya,badiya=बढ़िया
jldi,jaldi=जल्दी
chalo,chlo=चलो
chal,chl=चल
dekho,dkho=देखो
dekh,dkh=देख
suno,sunoo=सुनो
aao,ao=आओ
jao,jaao=जाओ
jaa=जा
gajab,gjb,gazab=गज़ब
kamaal,kamal,kmaal=कमाल
maza,mja,mazaa=मज़ा
bakwas,bkwas=बकवास
bolo,blo=बोलो
bol=बोल
kitna,ktna=कितना
kitne=कितने
kabhi,kbhi=कभी
sirf,srf=सिर्फ़
bilkul,blkul=बिल्कुल
zaroor,zrur,jaroor=ज़रूर
wapas,wps=वापस
kal=कल
aaj=आज
phir,fir=फिर
dhanyawad,dhanyavaad=धन्यवाद
shukriya,shukriyaa=शुक्रिया
namaste,nmste,namaskar=नमस्ते
dost=दोस्त
dosto,dsto=दोस्तों
lol,lmao,lmfao,rofl=haha
omg=oh my god
gg=good game
wtf=what the heck
brb=be right back
afk=away from keyboard
idk=I don't know
btw=by the way
ty,thx,tysm=thank you
pls,plz=please
ikr=I know right
imo,imho=in my opinion
nvm=never mind
rn=right now
tbh=to be honest
fr=for real
ngl=not gonna lie
smh=shaking my head
np=no problem
yw=you're welcome
ez=easy
gm=good morning
gn=good night
u=you
ur=your
r=are
k=okay
y=why
# ---- extra Hinglish chat / Gen Z words ----
tk=ठीक
ni=नहीं
haa=हाँ
kar=कर
kiya,kia=किया
diya,dia=दिया
liya,lia=लिया
gya,gaya=गया
aya,aaya=आया
hua=हुआ
tha=था
thi=थी
ab=अब
mai=मैं
mein=में
tujhe=तुझे
tera=तेरा
teri=तेरी
tere=तेरे
uska=उसका
uski=उसकी
uske=उसके
wala,vala=वाला
wali,vali=वाली
wale,vale=वाले
yahan,yha,yaha=यहाँ
wahan,vha,waha=वहाँ
idhar=इधर
udhar=उधर
sath,sth=साथ
sabse,sbse=सबसे
zyada,jyada,jada,zyda=ज़्यादा
thoda,thda=थोड़ा
chahiye,chiye,chahie,chahiyeh=चाहिए
sakta,skta=सकता
sakte,skte=सकते
lagta,lgta=लगता
dekhna,dkhna=देखना
batao,btao=बताओ
bata,bta=बता
ekdum,ekdm=एकदम
jabardast,zabardast,jbrdst=ज़बरदस्त
shandar,shandaar=शानदार
badhai,bdhai=बधाई
mubarak=मुबारक
arey,arre,arrey=अरे
pagal,paagal=पागल
sach=सच
didi=दीदी
behen,behan,bahan=बहन
faltu,faaltu=फ़ालतू
bindaas,bindas=बिंदास
jhakaas,jhakkas,jhakas=झक्कास
jugaad=जुगाड़
timepass=टाइमपास
fatafat=फटाफट
radhe=राधे
kk,okk=okay
xd=haha
w=win
l=loss
frfr=for real for real
ong=on god
iykyk=if you know you know
istg=I swear to god
ofc=of course
abt=about
tho=though
cuz,bcz,bcoz,coz=because
gud=good
gr8=great
msg=message
sry=sorry
srsly=seriously
tmrw,tmr=tomorrow
rly=really
ppl=people
thnx,tnx=thanks
ily=I love you
ilysm=I love you so much
wyd=what are you doing
wbu=what about you
hbu=how about you
hru=how are you
gtg,g2g=got to go
ttyl=talk to you later
jk=just kidding
irl=in real life
fyi=for your information
asap=as soon as possible
dw=don't worry
gl=good luck
hf=have fun
glhf=good luck have fun
wp=well played
ggwp=good game well played
nt=nice try
"""
USER_FILE_HELP = """# Add your own short forms here, one per line:  short1,short2=how it should be spoken
# Use Devanagari for Hindi words (best pronunciation). Lines starting with # are ignored.
# Example:
# bhaiya,bhaiyaa=भैया
"""
# phrase patterns that span two words, e.g. "kr rha", "krra", "kar rhi"
PHRASES = [
    (re.compile(r"(?<![A-Za-z])k(?:a)?rr?\s*(?:r?ha|ra|raha)(?![A-Za-z])", re.I), "कर रहा"),
    (re.compile(r"(?<![A-Za-z])k(?:a)?rr?\s*(?:r?hi|ri|rahi)(?![A-Za-z])", re.I), "कर रही"),
    (re.compile(r"(?<![A-Za-z])k(?:a)?rr?\s*(?:r?he|re|rahe)(?![A-Za-z])", re.I), "कर रहे"),
    (re.compile(r"(?<![A-Za-z])jai\s+(?:shree|shri|sri)\s+ram(?![A-Za-z])", re.I), "जय श्री राम"),
    (re.compile(r"(?<![A-Za-z])radhe\s+radhe(?![A-Za-z])", re.I), "राधे राधे"),
    (re.compile(r"(?<![A-Za-z])har\s+har\s+mahadev(?![A-Za-z])", re.I), "हर हर महादेव"),
    (re.compile(r"(?<![A-Za-z])jai\s+hind(?![A-Za-z])", re.I), "जय हिन्द"),
    (re.compile(r"(?<![A-Za-z])ram\s+ram(?![A-Za-z])", re.I), "राम राम"),
]
EMOJI_RX = re.compile(
    r"[0-9#*]\uFE0F?\u20E3"                                  # keycap emoji like 1️⃣ (removes the digit too)
    r"|[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u2600-\u27BF\u2900-\u297F\u2B00-\u2BFF"
    r"\u203C\u2049\u2122\u2139\u24C2\u3030\u303D\u3297\u3299\uFE0F\u200D\u20E3]")
# YouTube sends emoji and channel emotes as :name: codes (always start with a letter or underscore)
SHORTCODE_RX = re.compile(r":[A-Za-z_][^:\s]{0,60}:")
KEEP_AS_IS = {"tv", "pc", "ps", "gb", "mb", "hd", "fps", "gpu", "cpu", "ssd", "hmm", "hmmm", "shh", "ok", "vs"}
word_map = {}
unknown_seen = set()


def parse_words(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys, val = line.split("=", 1)
        for k in keys.split(","):
            if k.strip():
                out[k.strip().lower()] = val.strip()
    return out


def load_words(user_path=None):
    """Load the built-in list, then the user's own hinglish_words.txt (creating it on first run)."""
    global word_map
    word_map = parse_words(WORDS_TXT)
    if user_path:
        try:
            if not os.path.exists(user_path):
                with open(user_path, "w", encoding="utf-8") as f:
                    f.write(USER_FILE_HELP)
            with open(user_path, encoding="utf-8") as f:
                word_map.update(parse_words(f.read()))
        except Exception:
            pass
    return len(word_map)


def normalize(text):
    text = SHORTCODE_RX.sub(" ", text)
    text = EMOJI_RX.sub("", text)
    for rx, rep in PHRASES:
        text = rx.sub(rep, text)

    def fix(m):
        w = m.group(0)
        lw = re.sub(r"(.)\1{2,}", r"\1", w.lower())       # kyaaaa -> kya
        if lw in word_map:
            return word_map[lw]
        if 2 <= len(lw) <= 6 and not re.search(r"[aeiouy]", lw) and lw not in KEEP_AS_IS and lw not in unknown_seen:
            unknown_seen.add(lw)
            if on_unknown:
                on_unknown(lw)
        return w

    return re.sub(r"\s+", " ", re.sub(r"(?<![A-Za-z0-9])[A-Za-z]+(?![A-Za-z0-9])", fix, text)).strip()


load_words()
