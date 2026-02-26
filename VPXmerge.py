import tkinter as tk
from tkinter import filedialog, ttk
from tkinterdnd2 import DND_FILES, TkinterDnD
import olefile, os, shutil, json, threading, subprocess, re, random, urllib.request, urllib.error
from PIL import Image, ImageTk
import io

VERSION = "1.0"

# ── Media fuzzy matching helpers ──────────────────────────────────────────────
_MEDIA_NOISE = {
    'limited','edition','le','pro','premium','vr','vpw','mod','sg1','vpu',
    'the','a','an','and','of','in','remaster','vpx','remake','ultimate',
    'deluxe','special','anniversary','collector','classic','night','jp','fizx'
}

def _mnorm(s):
    """Normalize a name for fuzzy media matching."""
    s = s.lower()
    s = re.sub(r"_s\b", "s", s)               # Bugs_Bunny_s → Bugs Bunnys
    s = re.sub(r"['\u2019\u2018`]", "", s)     # strip apostrophes
    s = re.sub(r"[^a-z0-9\s]", " ", s)        # non-alphanum → space
    return re.sub(r"\s+", " ", s).strip()

def _mstrip(s):
    """Strip manufacturer, year, version, author noise."""
    s = re.sub(r'\s*\([^)]*\d{4}[^)]*\)', '', s)          # (Stern 2013)
    s = re.sub(r'\s*\([^)]*\)', '', s)                      # any remaining ()
    s = re.sub(r'\s+v\d+[\d.]*\b.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+\d+\.\d+[\d.]*\b.*$', '', s)
    s = re.sub(r'\s+(VPW|MOD|VR|LE|SE|CE|PRO|PREM|JP|FizX)\b.*$', '', s, flags=re.IGNORECASE)
    return s.strip()

def _mkeywords(s):
    return set(_mnorm(_mstrip(s)).split()) - _MEDIA_NOISE

def _detect_rom(script):
    """Extract ROM name from VPX/VBS script using multiple fallback patterns."""
    if not script:
        return None
    patterns = [
        # Primary: cGameName, GameName, RomName, cRomName (with optional Const)
        r'(?:Const\s+)?c?(?:Game|Rom)Name\s*=\s*(["\'])([^"\']+)\1',
        # OptRom = "value"
        r'OptRom\s*=\s*(["\'])([^"\']+)\1',
        # TableROM = "value" / cRom = "value" / ROM = "value"
        r'(?:Const\s+)?(?:Table)?c?Rom\s*=\s*(["\'])([^"\']+)\1',
        # Controller.GameName = "value" / PinMAME.GameName = "value"
        r'(?:Controller|PinMAME)\s*\.\s*GameName\s*=\s*(["\'])([^"\']+)\1',
        # Bare .GameName = "value"
        r'\.GameName\s*=\s*(["\'])([^"\']+)\1',
    ]
    for pat in patterns:
        m = re.search(pat, script, re.IGNORECASE)
        if m:
            val = m.group(2).strip()
            # ROM names are alphanumeric/underscore, max 32 chars
            if val and len(val) <= 32 and re.match(r'^[a-zA-Z0-9_]+$', val):
                return val
    return None

def _mfuzzy(a, b):
    """Return keyword overlap score 0.0–1.0 between two table names."""
    ka, kb = _mkeywords(a), _mkeywords(b)
    if not ka or not kb: return 0.0
    return len(ka & kb) / max(len(ka), len(kb))

# ══════════════════════════════════════════════════════════════════════
# VPS TABLE LOOKUP - Embedded Database
# Generated from pinballxdatabase.csv
# Total tables: 2668
# Format: table_name.lower() → VPS Table ID
# ══════════════════════════════════════════════════════════════════════

VPS_TABLE_LOOKUP = {
    "!wow! (mills novelty company 1932)": "OHdDfWkU9L",
    "'300' (gottlieb 1975)": "9pDvjPBe",
    "'roid belt racers (original 2025)": "pQLG-PB_Vt",
    "1-2-3 (automaticos 1973)": "xZZeK5j5Df",
    "1024 bytes (original 2006)": "R_qTJYElLc",
    "12 days of christmas, the (original 2016)": "ks3awkNa",
    "2 in 1 (bally 1964)": "pWAo_yo9E5",
    "2001 (gottlieb 1971)": "YTj1TmfZ",
    "2001 - a space odyssey (original 2025)": "iGEvF6towb",
    "24 (stern 2009)": "01rWOPkk",
    "250 cc (inder 1992)": "Gw5kOfmC",
    "3-in-line (bally 1963)": "ykWYxaFn",
    "300 (maresa 1975)": "UDkd2BZr-i",
    "300 prepare for glory (original 2008)": "5N-mukLuWM",
    "301 bullseye (grand products 1986)": "A-hCQg6qtb",
    "4 aces (williams 1970)": "6McUBzM2Bz",
    "4 queens (bally 1970)": "j76bd-z1Hz",
    "4 roses (williams 1962)": "i9f19gIR",
    "4 square (gottlieb 1971)": "F3Gjxwi6uo",
    "4x4 (atari 1983)": "QavDV54N",
    "50/50 (bally 1965)": "kMelEC_hFi",
    "5th element, the (original 2011)": "8CXiYfA4_0",
    "8 ball (williams 1952)": "mM7s-smhZk",
    "8 ball (williams 1966)": "q0lDgv1ddV",
    "a charlie brown christmas (original 2023)": "IW7Z0lOheZ",
    "a christmas carol pinball (original 2020)": "qeDM8b0g",
    "a real american hero - operation p.i.n.b.a.l.l. (original 2017)": "_KXlqEFX",
    "a real american hero - operation p.i.n.b.a.l.l. - reduced resource edition (original 2017)": "0Rxh6B5G52",
    "a samurai’s vengeance (zen studios 2023)": "N4kr_a9zOQ",
    "a-go-go (williams 1966)": "dc_uxjjW",
    "a-ha (original 2025)": "lycB2u5Gfs",
    "a-team, the (original 2023)": "qcCYQYUoow",
    "aaron spelling (data east 1992)": "YS5Mj1_B",
    "abba (original 2020)": "uXXdWqEP",
    "abra ca dabra (gottlieb 1975)": "8opN48IpkJ",
    "ac/dc (let there be rock limited edition) (stern 2012)": "VXDslC2VHJ",
    "ac/dc (luci premium) (stern 2013)": "LahrbarV",
    "ac/dc (luci vault edition) (stern 2018)": "wZkuBN4Co7",
    "ac/dc (original 2012)": "s7_F1d9EzQ",
    "ac/dc (premium) (stern 2012)": "D1RnYimjsX",
    "ac/dc (pro vault edition) (stern 2017)": "zFOcOPpA2Y",
    "ac/dc (pro) (stern 2012)": "ixxXOqm0lU",
    "ac/dc back in black (limited edition) (stern 2012)": "6cmA5qu0X9",
    "ac/dc power up (original 2022)": "X8LdfyNfY5",
    "accept (original 2019)": "kbl7AgR8",
    "ace high (gottlieb 1957)": "s-0YrAh4lu",
    "ace of speed (original 2019)": "LMOYSJWc",
    "ace ventura - pet detective (original 2019)": "kXXV7M26",
    "aces & kings (williams 1970)": "RYeImzsV",
    "aces high (bally 1965)": "9nVwCL1T",
    "action (chicago coin 1969)": "MWx8gRFOYh",
    "action (exhibit 1943)": "mJc8qRkO49",
    "addams family, the (bally 1992)": "sCl2ocQq8C",
    "addams family, the - 20th anniversary edition (bally 1992)": "n3w-BL8-gj",
    "addams family, the - b&w edition (bally 1992)": "VXT4c02V",
    "addams family, the - the addams family revised slamt1lt edition (bally 1992)": "4cCGBsju8c",
    "addams family, the - ultimate pro edition (bally 1992)": "S9uvEb051b",
    "adventure (sega 1979)": "ZK76ku-2R2",
    "adventure land (zen studios 2017)": "bYA3xjuh",
    "adventure time - rainy day daydream (original 2022)": "Q6YhRd-a",
    "adventures of rocky and bullwinkle and friends (data east 1993)": "lAd7NJam",
    "adventures of tintin, the (original 2021)": "286PGDGxxZ",
    "aerobatics (zaccaria 1977)": "HTXFS26o",
    "aerosmith (original 2019)": "g6FaArugYd",
    "aerosmith (pro) (stern 2017)": "UYsEyTmIhb",
    "agents 777 (game plan 1984)": "UEkko9GL",
    "aiq (original 2022)": "JQwYSJ0Jjm",
    "air aces (bally 1975)": "eB3j1Bd4tC",
    "airborne (capcom 1996)": "RqUjS70P",
    "airborne (j. esteban 1979)": "XmdDqX4Q35",
    "airborne avenger (atari 1977)": "KICM9nRF",
    "airport (gottlieb 1969)": "1ybsJAoKRm",
    "airwolf (original 2020)": "AMMUKkyeY5",
    "akira (original 2021)": "slnxn2Qq",
    "al capone (ltd do brasil 1984)": "ZU-z3zCO",
    "al's garage band goes on a world tour (alvin g. 1992)": "aKVryC6h",
    "aladdin's castle (bally 1976)": "RntCfn5odI",
    "alaska (interflip 1978)": "3O_4BiCNAE",
    "albator - the movie (original 2022)": "_2O5qSD0BR",
    "albator 78 (original 2022)": "UxGItXAlSF",
    "alcatrazz (original 2025)": "WSGyU738qB",
    "alfred hitchcock's psycho (original 2019)": "9sZqCCMq",
    "algar (williams 1980)": "5Iym9nqp",
    "ali (stern 1980)": "vmjnVO35vQ",
    "alice cooper's nightmare castle (original 2019)": "Kq14NS5lzg",
    "alice in chains pinball (original 2021)": "wYP6nduu",
    "alice in wonderland (gottlieb 1948)": "EQParLHs3z",
    "alice in wonderland (original 2026)": "PDq0O6tENW",
    "alien (original 2019)": "n1BL9FIVNG",
    "alien 2 (original 2023)": "vT8GAYFX00",
    "alien covenant (original 2023)": "btrCEC3jq7",
    "alien isolation pinball (zen studios 2016)": "mMrnaVpK",
    "alien nostromo - ultimate edition (original 2022)": "Zom-fzgc",
    "alien nostromo 2 (original 2024)": "xv3vAr2_5N",
    "alien poker (williams 1980)": "rAc_qaAtkF",
    "alien resurrection (original 2019)": "QrFRtq5Ck0",
    "alien star (gottlieb 1984)": "dBqQx-MQ",
    "alien trilogy (original 2019)": "tVFy4-sr",
    "alien vs predator pinball (zen studios 2016)": "vM5fPJrC",
    "alien warrior (ltd do brasil 1982)": "v77pvUzwAY",
    "aliens (original 2020)": "2m2xM6aM",
    "aliens from outer space (original 2021)": "FOgS11LO1k",
    "aliens legacy (original 2005)": "nu1DVKGW4O",
    "aliens legacy - game over, man (original 2005)": "_i1IjV1yps",
    "aliens legacy - hardcore (original 2005)": "7w2VUcHA-1",
    "aliens legacy - legendary edition (original 2005)": "bH_jCKBxEN",
    "aliens legacy - ultimate badass (original 2005)": "6m6hBKvJrN",
    "aliens legacy - ultimate pro (original 2005)": "DF9Qa8pxHi",
    "aliens pinball (zen studios 2016)": "Zy4hSBsD",
    "alive (brunswick 1978)": "Wa9yvPob",
    "all-star basketball (gottlieb 1952)": "Q5KADFiccd",
    "alley cats (williams 1985)": "D-fr2bD-",
    "aloha (gottlieb 1961)": "k11etpm7LK",
    "alvin and the chipmunks (original 2021)": "9a1ENG7ROR",
    "amazing dr. nim, the (e.s.r. inc 1965)": "mltZQLF8i2",
    "amazing spider-man, the (gottlieb 1980)": "wSAPHaD6",
    "amazing spider-man, the - sinister six edition (gottlieb 1980)": "7q1Na5E1Rw",
    "amazon (ltd do brasil 1979)": "BxrzYG6vZ6",
    "amazon hunt (gottlieb 1983)": "5nZWcwTL",
    "america 1492 (juegos populares 1986)": "O6cU9C0K",
    "america's most haunted (spooky pinball 2014)": "Ci5Gq3Uc",
    "american country (original 2024)": "4Z17QM5WhA",
    "american dad! pinball (zen studios 2015)": "xfnLSrgD",
    "american graffiti (original 2024)": "uGcJaW0-_x",
    "amigo (bally 1974)": "KY8zTUDu",
    "amy winehouse (original 2025)": "vuL-g3tbCe",
    "andromeda (game plan 1985)": "kRv9J170vV",
    "andromeda - tokyo 2074 edition (game plan 1985)": "u61rMeS921",
    "animal (original 2017)": "gfnXzmnv",
    "animal crossing pinball (original 2021)": "UylqoheR",
    "animal world (original 2020)": "SC2bszCVOW",
    "anna's colours (original 2006)": "p22cf-ZWty",
    "annabelle (original 2020)": "Me8czadv",
    "antar (playmatic 1979)": "ablqTmmV4-",
    "antworld (original 2015)": "8evxGHbNHy",
    "apache (playmatic 1975)": "MB3WhUQ0ds",
    "apache! (taito do brasil 1978)": "Q9Wxt1m8",
    "apollo (williams 1967)": "sZPreFcdyX",
    "apollo 13 (sega 1995)": "wSWbGBjQ",
    "aqualand (juegos populares 1986)": "TsxVsbO9",
    "aquaman (original 2024)": "QtBIw2dKpe",
    "aquarius (gottlieb 1970)": "yH7xECvX5I",
    "archer pinball (zen studios 2015)": "r1f-iEaI",
    "arena (gottlieb 1987)": "JoHSrEPG",
    "argentine (genco 1941)": "FXvr9EXnOA",
    "argosy (williams 1977)": "jry86GAbNq",
    "aristocrat (williams 1979)": "B5R4uvrM",
    "arizona (ltd do brasil 1977)": "0Q1p36q5",
    "arizona (united 1943)": "2B2poIuohF",
    "army of the dead (original 2021)": "CB4edMs6",
    "aspen (brunswick 1979)": "GA_jDMNg",
    "asterix the twelve tasks (original 2022)": "QcrLSEu8cS",
    "asteroid annie and the aliens (gottlieb 1980)": "EBIlxsRP",
    "asteroids (original 2016)": "1qKvF0zV",
    "astral defender (original 2018)": "SsU3cQRN",
    "astro (gottlieb 1971)": "2XJqy5NS",
    "astronaut (chicago coin 1969)": "YDS9FYcDz3",
    "atari 2600 (original 2022)": "6i3-20eepR",
    "atari centipede pinball (original 2020)": "E7KkzK1S",
    "atari centipede pinball - color balls edition (original 2020)": "4bgjShr8kP",
    "atarians, the (atari 1976)": "1MHNQ4qsaq",
    "atlantis (bally 1989)": "KOwCZeHrfY",
    "atlantis (gottlieb 1975)": "yC8HU7YjL0",
    "atlantis (ltd do brasil 1978)": "J6VuW7MU",
    "atleta (inder 1991)": "t1zIsnJn",
    "attack & revenge from mars (original 2015)": "XdhJ9wO9",
    "attack (playmatic 1980)": "moxhopOZwv",
    "attack from mars (bally 1995)": "RZ228N1t",
    "attack of the killer tomatoes (original 2023)": "1HpX8lzP7b",
    "attack on titan (original 2022)": "zHtxZ8_cbI",
    "attila the hun (game plan 1984)": "YIPTzaeg",
    "austin powers (stern 2001)": "z7ov9r5U",
    "auto race (gottlieb 1956)": "jbN8YZvrNj",
    "avatar - the last airbender (original 2024)": "ePZRCp90yq",
    "avenged sevenfold (original 2022)": "K2LfgrOOgB",
    "avengers (original 2020)": "j4NAOJLSXD",
    "avengers (pro), the (stern 2012)": "SSs1SuUS5F",
    "avengers - tv series, the (original 2023)": "LGFAsFgty5",
    "aztec (williams 1976)": "0XCN-Z25",
    "aztec - high-tap edition (williams 1976)": "fKmPMjN8Bp",
    "b.b. king (original 2025)": "1mxoZ-0X5A",
    "baby leland (stoner 1933)": "2e875By0Dc",
    "baby pac-man (bally 1982)": "ruMrSKqj",
    "baby shark (original 2021)": "FU5S65uwfq",
    "babylon 5 (original 2022)": "Z56S1ZOhdQ",
    "back to the future (data east 1990)": "6B5MLeQt",
    "back to the future (original 2013)": "5Ys2oXHWAG",
    "back to the future - ultimate (data east 1990)": "G--6xdB6nH",
    "back to the future pinball (zen studios 2017)": "VSp-ud62",
    "back to the future trilogy (original 2022)": "uZYfAkiyAU",
    "backstreet boys (original 2025)": "TJUFEw4M0N",
    "bad (original 2022)": "prbriwuT5e",
    "bad brains (original 2013)": "HUi9UDQuMi",
    "bad cats (williams 1989)": "bsD81LF7z1",
    "bad cats in space (original 2026)": "YAx8-eDPIy",
    "bad girls (gottlieb 1988)": "qgSPY2K7",
    "bad girls - alternate edition (gottlieb 1988)": "maoy2mTTDj",
    "bad girls - tooned-up version (gottlieb 1988)": "Sffc8dldwX",
    "bad girls from space (original 2026)": "3wY0nQ_K8f",
    "bad lieutenant (original 2020)": "3-vMj412",
    "bad santa 2 pinball xl (original 2017)": "DBwNJ8CI",
    "bad santa pinball (original 2017)": "wrbdHMtx",
    "balls-a-poppin (bally 1956)": "kMlNg8sd",
    "bally game show, the (bally 1990)": "D7XvKi6-",
    "bally hoo (bally 1969)": "d0d6Fis1",
    "ballyhoo (bally 1932)": "VJpCfhHQzt",
    "band wagon (bally 1965)": "wHzwxrnyae",
    "bang (genco 1939)": "TSbokcKzcc",
    "bank shot (gottlieb 1976)": "cQzj7peR",
    "bank-a-ball (gottlieb 1965)": "fs7UVdck",
    "bank-a-ball (j.f. linck 1932)": "RhJlGESe7u",
    "banzai run (williams 1988)": "8vIWYV3L",
    "barb wire (gottlieb 1996)": "_zPej-G6",
    "barbarella (automaticos 1972)": "5QhVnHbE",
    "barnacle bill (gottlieb 1948)": "Pnjw8Mdalk",
    "barnstorming (original 2024)": "KL_qEMz_Ph",
    "barracora (williams 1981)": "9oOdp7IM",
    "barry manilow (original 2023)": "BIOohAu6wx",
    "bart vs. the space mutants (original 2017)": "tFFqVH-B",
    "baseball (gottlieb 1970)": "hKjC0Rw_r1",
    "basketball (idsa 1986)": "rS3h2tv7",
    "bat-em (in & outdoor 1932)": "yPb5Knvkcl",
    "batgirl (original 2019)": "myYb-oQe",
    "batman '66 (original 2018)": "uM7VnH7n",
    "batman (66 premium) (stern 2016)": "WpGbZCWX__",
    "batman (data east 1991)": "6XbWUJ-R",
    "batman (stern 2008)": "3NbnW6F4",
    "batman - joker edition - ultimatum (original 2015)": "Y7fGSrsolQ",
    "batman - the animated series (original 2020)": "-Z8JCoCog8",
    "batman forever (sega 1995)": "N9VFK-cH20",
    "batman returns (original 2018)": "u_MRzVf_",
    "batman returns (original 2019)": "a1WK7yxZLl",
    "batman, the (original 2022)": "PD-noMpv3v",
    "batter up (gottlieb 1970)": "hJehuZ-_",
    "battle for the down (original 2023)": "QQfqdMXYAx",
    "battle of the planets (original 2018)": "HX5_nHhUUO",
    "battlestar galactica (original 2018)": "k6kb5xyR",
    "battlestar galactica pinball - table_170 (zen studios 2024)": "tSHpE3g60f",
    "baywatch (sega 1995)": "iBaOwyy4NM",
    "beach bums (original 2018)": "dTh5IRBP",
    "beach goblinball (original 2025)": "GLxymi86TB",
    "beastie boys (original 2025)": "7e3nbMe8Bn",
    "beastmaster, the (original 2021)": "iN0a9uCT",
    "beat box (digital illusions 1992)": "jumiciQdA6",
    "beat the clock (bally 1985)": "grYVrWxO",
    "beat the clock (williams 1963)": "d0PWr3jm1O",
    "beat time (williams 1967)": "J00ZvcTe",
    "beat time - beatles edition (williams 1967)": "1XN74l-c",
    "beatles (original 2013)": "1zcwwougtb",
    "beatles, the (stern 2018)": "oO-Hofw7",
    "beavis and butt-head pinball stupidity (original 2023)": "JCnmBfOopT",
    "beavis and butt-head pinballed (original 2024)": "LeutE8df4g",
    "beetlejuice (original 2021)": "sVvami0J",
    "beetlejuice (original 2023)": "4W651LZTSI",
    "beisbol (maresa 1971)": "FcpQ4ZUKRw",
    "bell ringer (gottlieb 1990)": "O2mP_qD9",
    "bella dama (original 2023)": "UaTkWjVJ56",
    "ben hur (staal 1977)": "I71olqHtkd",
    "ben ten (original 2024)": "sDtbtgUS8C",
    "berzerk (original 2016)": "gRk9Tyy5",
    "beverly hills cop (original 2019)": "cWPmZKXR",
    "biene maja (original 2022)": "S170U4eyiV",
    "big bang bar (capcom 1996)": "zgPRlUWkAv",
    "big ben (williams 1975)": "rgwmMQht",
    "big brave (gottlieb 1974)": "sjdat4-ssU",
    "big brave (maresa 1974)": "LSOFi9iwEa",
    "big brave - b&w edition (gottlieb 1974)": "MP410esOYr",
    "big buck hunter pro (stern 2010)": "KHyis7rN",
    "big casino (gottlieb 1961)": "1CzBIXSAmV",
    "big chief (williams 1965)": "eO8nIlId",
    "big daddy (williams 1963)": "mYIbxcXUG7",
    "big deal (williams 1963)": "SWdyjDjv",
    "big deal (williams 1977)": "iukrTmepLv",
    "big dick (fabulous fantasies 1996)": "kMsaRVE5",
    "big dick - orphaned on vpinball.com (fabulous fantasies 1996)": "pXybOKhbm2",
    "big flush (ltd do brasil 1983)": "Tgkcat4myq",
    "big game (rock-ola 1935)": "2bd7UUsa63",
    "big game (stern 1980)": "kxub6rxM-V",
    "big guns (williams 1987)": "4xDEQGwa",
    "big hit (gottlieb 1977)": "cPkc1Y1cdq",
    "big horse (maresa 1975)": "64HEuwQyPj",
    "big house (gottlieb 1989)": "V8f4aNM1",
    "big indian (gottlieb 1974)": "IfhBqAD8sE",
    "big injun (gottlieb 1974)": "J-XhiQmMz8",
    "big lebowski pinball, the (original 2016)": "kYdU2SUFdt",
    "big lebowski pinball, the - pup-pack edition (original 2016)": "Gi_FZ3oSrE",
    "big shot (gottlieb 1974)": "llNv0Tfo",
    "big show (bally 1974)": "_Gc5W_zj",
    "big spender (original 2013)": "HF1Baj6M8U",
    "big star (williams 1972)": "K7XsT-fCxe",
    "big top (gottlieb 1964)": "v6iCytO3_8",
    "big top (gottlieb 1988)": "lhX0R32WSh",
    "big top (wico 1977)": "OJ6WKxpKKh",
    "big town (playmatic 1978)": "mtu8UDTWTV",
    "big trouble in little china (original 2020)": "uJc3LJ6VlR",
    "big trouble in little china (original 2022)": "v5SPO362VR",
    "big valley (bally 1970)": "wDJ9H7pL",
    "biker mice from mars (original 2024)": "cp3_H7bSBA",
    "billion dollar gameshow (digital illusions 1992)": "HPg2wWLxMa",
    "billy idol (original 2025)": "ogL3kiSA1c",
    "biolab (zen studios 2010)": "FACUwLcD",
    "bird fly (original 2022)": "GqB5xVoCL2",
    "black & red (inder 1975)": "fXNUcHqzJe",
    "black belt (bally 1986)": "RgQCiZvA",
    "black belt (zaccaria 1986)": "6i7e1vlnug",
    "black fever (playmatic 1980)": "WAFkDPpphk",
    "black gold (williams 1975)": "Y0PEcEeK",
    "black hole (gottlieb 1981)": "g5bgoRp7",
    "black hole (ltd do brasil 1982)": "m9Dqv4YIs6",
    "black jack (ss) (bally 1978)": "jP37249wk_",
    "black knight (williams 1980)": "qKc20XVgoR",
    "black knight 2000 (williams 1989)": "TFzkVEOW",
    "black knight sword of rage (stern 2019)": "W3hUkYG_",
    "black magic 4 (recel 1980)": "FD7syId0L-",
    "black pyramid (bally 1984)": "GdMAQebh",
    "black rose (bally 1992)": "USW-4L1A",
    "black sabbath 80s (original 2012)": "ZKO7g23Fas",
    "black sabbath the '70s (original 2020)": "qHAzm7OU",
    "black sheep squadron (astro games 1979)": "1mqb7295",
    "black tiger pinball (original 2022)": "FyWFUi9ToG",
    "black velvet (game plan 1978)": "tKYolhxEiB",
    "blackout (williams 1980)": "8Xuj_Gg6",
    "blackwater 100 (bally 1988)": "XJFLeAxM",
    "blade (zen studios 2013)": "YxfZF4b9",
    "blade runner - replicant edition (original 2020)": "NiRdYX2g6k",
    "blade runner - ultimate pro (original 2020)": "OfrrtT9SU5",
    "blade runner 2049 (original 2020)": "6EaJ-DE3",
    "blade runner 2049 - pup-pack edition (original 2020)": "gd7UTVkvre",
    "blank table with scoring (original 2016)": "hv4eJW0Uh5",
    "blaze and the monster machines (original 2021)": "lGLWeP_9",
    "bleach (original 2023)": "Kp1MnBEmOT",
    "blink 182 (original 2025)": "NAp9NxANLX",
    "blizzard of ozz, the (original 2025)": "ecjSchd5Od",
    "blood machines (original 2022)": "8ptfy_gf-Q",
    "bloodsport (original 2019)": "rHu1dzMXO4",
    "bloodsport (original 2023)": "vZwvmbeonk",
    "blue chip (williams 1976)": "V73AxWb2",
    "blue note (gottlieb 1978)": "kP1QfvFo",
    "blue ribbon (bally 1965)": "Xl4u3KcxJo",
    "blue vs pink (original 2009)": "1fYH6sMrml",
    "blue vs pink - bam edition (original 2009)": "XVoPsDVysV",
    "blues brothers 40th anniversary, the (original 2020)": "XaKQp-UQ",
    "blues brothers, the (original 2020)": "eASOmQYp",
    "bluey (original 2021)": "67fuXDV9",
    "bmx (bally 1983)": "evrGskgKBK",
    "bmx - rad edition (bally 1983)": "CFfWE7YdjT",
    "bmx - radical rick edition (bally 1983)": "L6m7MREzV2",
    "bob cuspe (original 2025)": "mFMtQFfnE4",
    "bob marley (original 2024)": "XiA05LJE3E",
    "bob seger (original 2025)": "sbHmV9Y7Wf",
    "bob's burgers (original 2024)": "0Fca7dO02t",
    "bob's burgers pinball (zen studios 2015)": "chmo0utL",
    "bobby orr power play (bally 1978)": "T3W8qNSq",
    "bobsbop (original 2012)": "gDeWq72XIW",
    "bon jovi (original 2024)": "amfRIq_F3h",
    "bon voyage (bally 1974)": "XJSysphY",
    "bonanza (original 2022)": "PPPwjBymSj",
    "bond 50th (original 2013)": "G7ggl_DFuV",
    "bond 60th (limited edition) (original 2023)": "7p9eGKNTR5",
    "bond 60th (original 2022)": "_xt4j3-2S6",
    "bone busters inc. (gottlieb 1989)": "1FY7wgPy",
    "boomerang (bally 1974)": "gusmzWSq",
    "boop-a-doop (pace 1932)": "Kk4Z35Ltt2",
    "border town (gottlieb 1940)": "dJRiQCbZ3H",
    "borderlands - vault hunter pinball (zen studios 2023)": "2W43yVadTj",
    "boston (original 2025)": "uATqOF-Dbc",
    "bounty hunter (gottlieb 1985)": "dx6fplYl",
    "bourne identity, the - challenge edition (original 2024)": "MUySNKWjfM",
    "bourne identity, the - pup-pack edition (original 2024)": "Gj9WF9h0KT",
    "bourne identity, the - treadstone edition (original 2024)": "tmZjWCuwZm",
    "bow and arrow (em) (bally 1975)": "oFcgfiEr",
    "bow and arrow (ss) (bally 1974)": "NZiStTUF6r",
    "bowie star man (original 2019)": "_RFAr5HyLo",
    "bowling - alle neune (nsm 1976)": "HR_-Qd4W-p",
    "bowling champ (gottlieb 1949)": "c6J8JkkrOc",
    "bowling league (gottlieb 1947)": "QvjEyjCxry",
    "boxster pinball (original 2010)": "TufXBYTBVN",
    "brady bunch, the (original 2025)": "cffBbydlKD",
    "brainscan (original 2019)": "uhz6C-agkm",
    "bram stoker's dracula (williams 1993)": "hR9T1IRoAn",
    "bram stoker's dracula - blood edition (williams 1993)": "KjMMHuiqs4",
    "brave team (inder 1985)": "lSz5Sccejh",
    "bravestarr (original 2021)": "74IzDopjY8",
    "break (video dens 1986)": "iF7th8WSeM",
    "breakin (original 2025)": "IJuwQPfso_",
    "breaking bad (original 2021)": "kqlTDuc3uP",
    "breaking bad (original 2022)": "FoQ46b4MD0",
    "breakshot (capcom 1996)": "vsIePTHl",
    "bristol hills (gottlieb 1971)": "zjCeR3gq",
    "britney spears (original 2021)": "2PnUb6fy",
    "bronco (gottlieb 1977)": "JhwSEjW-Hs",
    "bronco buster (original 2013)": "iHRCsb2zjL",
    "brothers in arms - win the war pinball (zen studios 2023)": "OoZLVfH87q",
    "bubba the redneck werewolf (original 2017)": "cGzy2IxA",
    "bubble bobble (original 2006)": "WgwHg4f_my",
    "bubblegum crisis megatokyo 2035 (original 2011)": "ZymQp95azO",
    "buccaneer (gottlieb 1948)": "x0nI03UAD8",
    "buccaneer (gottlieb 1976)": "NNba1DWP8y",
    "buccaneer (j. esteban 1976)": "hGIvqA3IND",
    "buck rogers (gottlieb 1980)": "SKZ0WE4B",
    "buckaroo (gottlieb 1965)": "iWMfJpQ1",
    "bud spencer & terence hill (original 2024)": "iYSkgvkU8G",
    "buffy the vampire slayer (original 2022)": "FTM21j1pvH",
    "bugs and jokers (original 2023)": "3gTX30qbA4",
    "bugs bunny's birthday ball (bally 1990)": "_UC_pbMD1k",
    "bumper (bill port 1977)": "2mm75EYBEa",
    "bumper - b&w edition (bill port 1977)": "R4YkPBk1q-",
    "bumper pool (gottlieb 1969)": "btMwxcqs",
    "bunnyboard (marble games 1932)": "MGTRwK6r",
    "bushido (inder 1993)": "k4ytvysp",
    "buzz off! (original 2026)": "rsh3gXthlJ",
    "c.o.d. (williams 1953)": "WO0XPqbWs-",
    "caballeros del zodiaco (original 2022)": "9JlQXRDu",
    "cabaret (williams 1968)": "J_t55Pfm24",
    "cactus canyon (bally 1998)": "2mGdjGXkXV",
    "cactus canyon continued (original 2019)": "R0tbYz3t",
    "cactus jack's (gottlieb 1991)": "f49X77IP",
    "caddie (playmatic 1970)": "0etIoaEg",
    "caddie (playmatic 1975)": "73b6Y2Wisi",
    "camel caravan (genco 1949)": "ngs0VQeWi4",
    "camping trip! (original 2025)": "EqXGLF1BKL",
    "canada dry (gottlieb 1976)": "MumP-aVp",
    "canasta 86 (inder 1986)": "bGGbkTi_cQ",
    "cannes (segasa 1976)": "hfRYbjMyTQ",
    "cannon fodder (original 2018)": "zRFXbIqR",
    "capersville (bally 1966)": "eRMSr3iN",
    "capt. card (gottlieb 1974)": "Fv2aE5DK",
    "capt. fantastic and the brown dirt cowboy (bally 1976)": "Lz3gQiqm",
    "captain america (zen studios 2011)": "Dz_LUHPv",
    "captain future (original 2022)": "1GxLbKPIZb",
    "captain nemo dives again (quetzal pinball 2015)": "WGti4uli",
    "captain nemo dives again - steampunk flyer edition (quetzal pinball 2015)": "iNcPRGH3vl",
    "captain spaulding's museum of monsters and madmen (original 2025)": "EPN4NNJbgS",
    "car hop (gottlieb 1991)": "ie63-29F",
    "carcariass pinball chaos (original 2021)": "GVRPa_GE",
    "card king (gottlieb 1971)": "dX9vXjOmp3",
    "card trix (gottlieb 1970)": "Em9BhnyO",
    "card whiz (gottlieb 1976)": "0gKQFfkI",
    "carnaval no rio (ltd do brasil 1977)": "sGNvMGFmFo",
    "carnival games (original 2025)": "FXkaLs96KX",
    "carnival queen (bally 1958)": "_ANGQjWY",
    "carrie underwood (original 2021)": "a9PLW_WrvD",
    "cars - lightning edition (original 2024)": "1je67-gqsM",
    "cartoons rc (original 2017)": "Vrb-13GNk_",
    "casino (williams 1958)": "vTUsqIGwCT",
    "castlestorm (zen studios 2015)": "60h351PT",
    "castlevania - symphony of the night (original 2022)": "4SUOovOShP",
    "cat burglars (original 2024)": "yApb21FFAI",
    "catacomb (stern 1981)": "tlCgHiM-",
    "cavalcade (stoner 1935)": "DluQcYY4",
    "cavaleiro negro (taito do brasil 1980)": "tYaz9Mlq",
    "cavalier (recel 1979)": "yptAexIL",
    "caveman (gottlieb 1982)": "cYWhCpGl",
    "cenobite (original 2023)": "PQ_fKPgxwG",
    "centaur (bally 1981)": "Nvk-Qp2Wfv",
    "centigrade 37 (gottlieb 1977)": "YeHFhctP",
    "central park (gottlieb 1966)": "lLdJ5r2D",
    "cerberus (playmatic 1983)": "9ZGJz7SxwF",
    "cerebral maze, the (original 2022)": "F4szVAyL",
    "champ (bally 1974)": "_zcBRUKT",
    "champion (bally 1939)": "Sq6OsE_0EN",
    "champion pub, the (bally 1998)": "b3iKqnmp",
    "champions league - libertadores narracao brasileira (original 2020)": "ifP_oLUS",
    "champions league - season 2017 (original 2017)": "A8Ksdzpm",
    "champions league - season 2018 (original 2017)": "cYw3ydyE",
    "champions league - season 2018 (st. pauli) (original 2018)": "3BBgrMEX",
    "champions league - season 2020 (original 2020)": "3elhDm0e",
    "champions league - season 2023 (original 2023)": "iFxghtiFM5",
    "champions league 2021 (original 2020)": "y66OwYVI",
    "chance (playmatic 1974)": "5S1_lKIea7",
    "chance (playmatic 1978)": "Zbc-lhgu8U",
    "charlie's angels (gottlieb 1978)": "az33FXuy",
    "charlie's angels (gottlieb 1979)": "0gVdHuUWOb",
    "check (recel 1975)": "Nzi-NCuRsX",
    "check mate (recel 1975)": "ScvOU0wwpb",
    "check mate (taito do brasil 1977)": "XvPZZ2lJI1",
    "checkpoint (data east 1991)": "mLe602Zz",
    "cheech & chong - road-trip'pin (original 2021)": "1wscbBj9",
    "cheese squad (original 2023)": "pj7LTGYYba",
    "cheese squad 2 (original 2024)": "yNHj-XmLdH",
    "cheetah (stern 1980)": "QjgTwfslRw",
    "chef-ball (original 2025)": "nwDyjSS2zW",
    "cherry coke (original 2020)": "RRDQie1n",
    "chicago cubs 'triple play' (gottlieb 1985)": "REw9XH0E",
    "child's play (original 2017)": "vrAIS6i9",
    "child's play (original 2023)": "BP2fWpYJ1T",
    "chime speed test table (original 2021)": "puQd1lL0",
    "chris cornell (original 2020)": "2L5_jrN3",
    "christmas pinball (original 2018)": "TMxh57kO",
    "christmas vaction (original 2019)": "E9BeTWGZuG",
    "chrono trigger (original 2022)": "pp-6iuZE9F",
    "chuck berry (original 2020)": "mmlgiRV7",
    "circus (bally 1973)": "rf4BbpWC",
    "circus (brunswick 1980)": "f2kVMXHx",
    "circus (gottlieb 1980)": "a2UA5tUw",
    "circus (zaccaria 1977)": "P8m7c4to",
    "circus starr (original 2016)": "1EdP-G6quL",
    "circus starr - basic version (original 2016)": "RZjNP5RP8Y",
    "cirqus voltaire (bally 1997)": "YXT6zmZu",
    "city hunter (original 2025)": "WUQkJu9X5Q",
    "city on the moon - murray leinster (original 2024)": "xxdTpHWfjf",
    "city ship (j. esteban 1978)": "4K1paJclVM",
    "city slicker (bally 1987)": "4cV9S736",
    "civil war (zen studios 2012)": "kvhi2F1q",
    "clash pro - audio ammunition, the (original 2020)": "7fc9Q_rm",
    "clash, the (original 2018)": "8SQcWsUM",
    "class of 1812 (gottlieb 1991)": "-BtIYqiJ",
    "class of 1984 (original 2024)": "FWDWP6jDh0",
    "cleopatra (ss) (gottlieb 1977)": "fdJAoNpE",
    "clever & smart (original 2023)": "vCZOOTc7Zm",
    "clock of eternal fog (original 2024)": "STKj6XJEoc",
    "clockwork orange (original 2022)": "LebSSspqMe",
    "close encounters of the third kind (gottlieb 1978)": "pjGpjCnqNC",
    "cloudy with a chance of meatballs (original 2021)": "Mg7uscN4",
    "clown (inder 1988)": "p7V8dybdek",
    "clown (playmatic 1971)": "z7rgM-zIHt",
    "clue (original 2018)": "u4uUIFMZ",
    "clutch (original 2021)": "XErMu-OiWc",
    "cobra (nuova bell games 1987)": "MxYaBP7Vom",
    "cobra (original 2022)": "7BKoftieTO",
    "cobra (playbar 1987)": "tWxgKel3BQ",
    "cobretti (original 2025)": "t-KI5JXxJ-",
    "coldplay pinball (original 2020)": "aTx6Jiw1",
    "college queens (gottlieb 1969)": "qE9Vqey6VM",
    "columbia (ltd do brasil 1983)": "S-wlJTz4",
    "combination rotation (gottlieb 1982)": "3dfPFIDGDJ",
    "comet (williams 1985)": "Y-LRa4KI",
    "comic book guy (original 2021)": "4pfqrR3sVf",
    "commando - schwarzenegger (original 2019)": "YVXz_CFC",
    "conan (rowamet 1983)": "aTZnjiDR",
    "concorde (emagar 1975)": "ReYIhAcr",
    "congo (williams 1995)": "V9UYtCZ-",
    "conjuring, the (original 2020)": "HWrICeFW",
    "conjury contraption (original 2024)": "eAZXruxRym",
    "conquest 200 (playmatic 1976)": "lzfmGCpU",
    "contact (williams 1978)": "AXdNzBYZ",
    "contact master (pamco 1934)": "QGWum4wkQ1",
    "contest (gottlieb 1958)": "G39qFg1Y",
    "continental cafe (gottlieb 1957)": "UcoRcYrj3g",
    "contra (original 2019)": "aTM3GBpd",
    "cool spot (original 2019)": "VhWyqqUU",
    "copa libertadores 2018 (original 2018)": "yaZeNEDL",
    "corinthian master bagatelle (abbey 1951)": "sXlFwBOc",
    "coronation (gottlieb 1952)": "ZHX93Hjge3",
    "corsario (inder 1989)": "bUsGoqXV",
    "corvette (bally 1994)": "N-fRLIEe",
    "cosmic (taito do brasil 1980)": "ta-gzB8U",
    "cosmic battle girls (original 2025)": "aMU9JWYhVK",
    "cosmic carnival (original 2019)": "jsBlV_Zinb",
    "cosmic gunfight (williams 1982)": "fFBG56lw",
    "cosmic lady (original 2018)": "Xixsx8xZ",
    "cosmic princess (stern 1979)": "crgeefCDsC",
    "cosmic princess - fizx 3.3 (stern 1979)": "ByGBJ6d_Vd",
    "cosmic venus (tilt movie 1978)": "30Vs0AOK",
    "count-down (gottlieb 1979)": "nmkuiqRO",
    "counterforce (gottlieb 1980)": "soCdaX_vEY",
    "courage the cowardly dog pinball (original 2025)": "4TkGNZB34Z",
    "cover girl (gottlieb 1962)": "cqoFB8hgvz",
    "cover girl (keeney 1947)": "MK1KGzKwgO",
    "cow poke (gottlieb 1965)": "-uF0SaGo",
    "cowboy bebop (original 2024)": "rASwgtPBvd",
    "cowboy bebop pinball (original 2024)": "d9hIhz9voX",
    "cowboy eight ball (ltd do brasil 1981)": "LAxl5M9f",
    "cowboy eight ball 2 (ltd do brasil 1981)": "IbxhSMtlDW",
    "crash bandicoot (original 2018)": "mdILafgLON",
    "crazy cats demo derby (original 2023)": "ZIOsEji_sm",
    "crazy rocket (original 2024)": "mcMGimRHss",
    "creature from the black lagoon (bally 1992)": "_DRn8e8n",
    "creature from the black lagoon - b&w edition (bally 1992)": "8sr1SUVC",
    "creature from the black lagoon - nude edition (bally 1992)": "LZg9YHhG",
    "creepshow (original 2022)": "VcsBp0F_",
    "creepy house (original 2006)": "YXbJl0EZLu",
    "crescendo (gottlieb 1970)": "YhHlqFFC",
    "criterium 75 (recel 1975)": "nBeLIzDK",
    "criterium 77 (taito do brasil 1977)": "DyCvx9fW",
    "cross country (bally 1963)": "7Fd34jD4xo",
    "cross town (gottlieb 1966)": "IMmptpqd",
    "crossword (williams 1959)": "Qbg_XNGqoN",
    "crow, the (original 2025)": "TSyjlYXAmn",
    "crypt of the necrodancer pinball (zen studios 2023)": "vq5sBd4C_u",
    "crysis (original 2018)": "8eBqlcV5",
    "crystal-ball (automaticos 1970)": "MzE5Y6Cqhi",
    "csi (stern 2008)": "WL0FlwLN",
    "cue (stern 1982)": "vHJEO00n",
    "cue ball wizard (gottlieb 1992)": "DdZxfXxH",
    "cue-t (williams 1968)": "7aln6MDTqR",
    "cuphead (original 2019)": "JjN8_FJNgT",
    "cuphead pro (perdition edition) (original 2020)": "WqVCVjSP",
    "cuphead pro (perdition edition) - pup-pack edition (original 2020)": "vKDukaWtBU",
    "cure, the (original 2025)": "_AeHUJXFOT",
    "curse of the mummy (zen studios 2022)": "5YD-2cDlcp",
    "cyber race (original 2023)": "peImTeYd43",
    "cybernaut (bally 1985)": "KExbnLum",
    "cyclone (williams 1988)": "gsNMhPtF",
    "cyclopes (game plan 1985)": "8LIyIJGKkJ",
    "daft punk (original 2020)": "zx-__ko_",
    "daft punk - interstella 5555 (original 2024)": "FFP3WL00JW",
    "daho (original 2024)": "9TSYLMUglM",
    "daisy may (gottlieb 1954)": "upVgRA3rvz",
    "dale jr. (stern 2007)": "S3oiJYNlKP",
    "daniel tiger's neighborhood (original 2025)": "QsQ0H1GQgr",
    "dante's inferno (original 2022)": "dah_hFPs",
    "daredevil and the defenders (original 2024)": "Ejy2hgO_3r",
    "dark (1986) (original 2024)": "IXQvQ32HLk",
    "dark chaos (original 2025)": "ePSwAxXZi6",
    "dark crystal pinball, the (original 2020)": "3W46guJa",
    "dark princess (original 2020)": "jPLxVR4b",
    "dark rider (geiger 1984)": "rl0o2_hrtP",
    "dark shadow (nuova bell games 1986)": "_ydUavcN",
    "darkest dungeon (original 2023)": "8neiKBTNGj",
    "darling (williams 1973)": "IoyTRq7U",
    "darth maul (original 2025)": "3mdHplEJ3U",
    "darth vader (original 2020)": "7A6jUmDfq5",
    "daughtry (original 2025)": "Y-jkNziOwK",
    "day of the tentacle (original 2023)": "zRx3nFzgEu",
    "days of thunder (original 2022)": "Qh3f5yn7IF",
    "de-icer (williams 1949)": "UUhKKEFSTp",
    "deadly weapon (gottlieb 1990)": "qpESHWvn",
    "deadpool (zen studios 2014)": "564hUGaz",
    "deadpool - special edition (stern 2018)": "dr_WogaS6Q",
    "dealer's choice (williams 1973)": "FOI4uq80",
    "death note (original 2024)": "S0RzPJWZdQ",
    "death proof (original 2021)": "Qa-4XdNy",
    "death proof - pup-pack edition (original 2021)": "Q7exB47tYh",
    "death race 2000 (original 2022)": "AX1V-lGKrI",
    "death wish 3 (original 2019)": "dqizRgwb",
    "deep purple - smoke on the water (original 2024)": "6_HZDGxOTd",
    "deep purple - smoke on the water - b&w edition (original 2024)": "TApFsmzAzX",
    "def leppard (original 2020)": "I3QrbMa7ls",
    "def leppard (original 2025)": "4GkzXouk9h",
    "def leppard hits vegas (original 2025)": "qmdlSBJBug",
    "defender (williams 1982)": "T9udbILn",
    "deftones (original 2025)": "GdV6qInTcs",
    "delta force, the (original 2019)": "xZOb-NFL",
    "demogorgon (original 2020)": "oBmm_18A",
    "demolition man (williams 1994)": "l8B0QJLS",
    "demolition man - limited cryo edition (williams 1994)": "6zBxgxe9S2",
    "demon's tilt (wiznwar, flarb llc 2019)": "IoMbg4AA-g",
    "dennis lillee's howzat! (hankin 1980)": "dzVmTBQejX",
    "depeche mode pinball (original 2021)": "QcKJDX97q6",
    "desert city (fipermatic 1977)": "N7EpM8Dt",
    "devil riders (zaccaria 1984)": "nEMQHvrr",
    "devil's dare (gottlieb 1982)": "ZK9fmtmI",
    "dexter (original 2022)": "X9el-XgPFm",
    "diablo pinball (original 2017)": "ZYHTqanh",
    "diadem (original 2023)": "ximTjF2eH3",
    "diamond jack (gottlieb 1967)": "2uFODTjY",
    "diamond lady (gottlieb 1988)": "jMsTMNP7",
    "diana (rowamet 1981)": "blKtzBn0mh",
    "dick tracy (original 2024)": "akMIGL--vZ",
    "die hard trilogy (original 2023)": "C1m5TY2-TY",
    "dimension (gottlieb 1971)": "1SqKewmT",
    "dimmu borgir (original 2019)": "ONElOQ0V",
    "diner (williams 1990)": "sEAFGfaY",
    "dipsy doodle (williams 1970)": "LY1wXtXK",
    "dire straits (original 2025)": "swsHmMtLWN",
    "dirty dancing (original 2022)": "lxdOLIkolA",
    "dirty harry (williams 1995)": "PSyhidSh",
    "disco (stern 1977)": "RVztKhVhMl",
    "disco dancing (ltd do brasil 1979)": "3ukBNGX9zq",
    "disco fever (williams 1978)": "veGC70ND",
    "discotek (bally 1965)": "bLhlWP_Msc",
    "disney aladdin (original 2020)": "XivUYqh-",
    "disney descendants (original 2020)": "2AndLEcx",
    "disney encanto (original 2022)": "ljhUi_Fj",
    "disney frozen (original 2016)": "VaqqJGuW",
    "disney hotel transylvania (original 2021)": "ymOB5JW1h6",
    "disney moana (original 2021)": "dXEc3K6j",
    "disney pin-up pinball (original 2023)": "X7NT4ADL_8",
    "disney pixar brave (original 2021)": "Y_xZYQdB",
    "disney pixar luca (original 2021)": "Vdykbo08",
    "disney pixar onward (original 2021)": "hnkB8ni5",
    "disney princesses (original 2016)": "YokvtrwA",
    "disney raya and friends pinball (original 2022)": "b5iJ7QjJ55",
    "disney tangled (original 2021)": "tSNqqj4x",
    "disney the lion king (original 2020)": "3xGXn_NP",
    "disney the little mermaid (original 2021)": "r4ygx-GG",
    "disney tron legacy (limited edition) (stern 2011)": "9swLN43M",
    "disney tron legacy (limited edition) - pup-pack edition (stern 2011)": "uDsIDklt",
    "disney vaiana (original 2021)": "NakAX1E6",
    "dixieland (bally 1968)": "izwhH0Ls",
    "django unchained (original 2022)": "bx_SLr8nlg",
    "doctor strange (original 2023)": "8C3LSbZgp6",
    "doctor strange (zen studios 2013)": "N-s_SIR0",
    "doctor who (bally 1992)": "43M-oCwo",
    "dodge city (gottlieb 1965)": "mbsax1uERX",
    "dof test table (original 2017)": "QD06vr79Cp",
    "dogelon mars pinball (original 2024)": "7ah8EVyXTj",
    "dogies (bally 1968)": "sQeDDsLf5p",
    "dokken pinball (original 2022)": "0mPLJAk_67",
    "dolly parton (bally 1979)": "78i61S4Lky",
    "dolphin (chicago coin 1974)": "tnx6lzQR",
    "dominatrix (original 2022)": "7_7XkDDnFx",
    "domino (gottlieb 1968)": "bUZwaoP6",
    "domino (gottlieb 1983)": "LUUvQhmr5s",
    "donald duck phantomias (original 2022)": "8Wtb-OZiQn",
    "doodle bug (williams 1971)": "7FDxD6KY",
    "doom classic edition (original 2019)": "jdBIpe3N",
    "doom eternal (original 2022)": "QLK2fXw4P_",
    "doom pinball (zen studios 2016)": "DxaWgQIf",
    "doors, the (original 2025)": "G1ITiw8H44",
    "doraemon (original 2020)": "5UWNSkR6",
    "double barrel (williams 1961)": "eXH0RXfLSm",
    "double dragon neon (original 2020)": "BoBe2TD0",
    "double-up (bally 1970)": "IBEtFC9x",
    "dr. dude and his excellent ray (bally 1990)": "Rpe37kzf",
    "dr. jekyll and mr. hyde (original 2022)": "jLfgyOFvAP",
    "dr. rollover's laboratory (original 2025)": "Xk2goZZd7A",
    "dracula (stern 1979)": "w5DdzzJBfA",
    "dragon (gottlieb 1978)": "GULd2OEYzI",
    "dragon (interflip 1977)": "LmmsiB9s",
    "dragon (ss) (gottlieb 1978)": "Ou9Yf-Ml",
    "dragon ball z (original 2018)": "wBrV24MW",
    "dragon ball z budokai (original 2023)": "ehHkc5K5aJ",
    "dragon flames (original 2024)": "GW7_boODg6",
    "dragon's lair (original 2023)": "u6kSJiJi_D",
    "dragonball - super saiyan edition (original 2025)": "8Hpif81vOV",
    "dragonette (gottlieb 1954)": "yXV3jNH5OF",
    "dragonfire (original 2021)": "bWXYgQoG",
    "dragonfist (stern 1981)": "cwjR63kne3",
    "dragoon (recreativos franco 1977)": "q9esdcQK",
    "drakor (taito do brasil 1979)": "k_z5EGE_",
    "dready 4-bushes (original 2021)": "SNheyDEhSO",
    "dream daddy - the dad dating simulator (original 2020)": "FZCi2ZMa",
    "dream theater (original 2025)": "x_yJGLEBn3",
    "dreamworks how to train your dragon pinball (zen studios 2021)": "3Gu1yLUiGa",
    "dreamworks kung fu panda pinball (zen studios 2021)": "KyM7G8IGE4",
    "dreamworks megamind (original 2021)": "03C3Eg2Q",
    "dreamworks trolls (original 2021)": "8CmT88bg",
    "dreamworks trolls pinball (zen studios 2021)": "nafFGXrzkT",
    "drink absolut (original 2015)": "ut3NdgGp",
    "drop-a-card (gottlieb 1971)": "kECiKW_B",
    "drunken santa (original 2020)": "UqxQ7Vvs",
    "ducktales (original 2014)": "TFcefpZOLX",
    "ducktales (original 2020)": "Ei0X_rAG",
    "dude, the (original 2020)": "OPfMir43re",
    "duke nukem 3d (original 2020)": "OQ7hzDVr",
    "dukes of hazzard, the (original 2022)": "g1WwIyskTw",
    "dune (original 2024)": "ocXi-7dQ2e",
    "dungeons & dragons (bally 1987)": "9iv-xn8_",
    "duotron (gottlieb 1974)": "i0c0IGoe",
    "duran duran (original 2025)": "dAuH9rCu0i",
    "dutch pool (a.b.t. 1931)": "LYBuOI9onC",
    "e.t. pinball (zen studios 2017)": "iTUWMuYe",
    "eager beaver (williams 1965)": "HmZjdb6M",
    "earth defense (zen studios 2013)": "DWdw5pkz",
    "earth wind fire (zaccaria 1981)": "_N4iUovT",
    "earthshaker (williams 1989)": "UCSx9Q_v",
    "eclipse (gottlieb 1982)": "pJQlLh6_",
    "eddie (original 2019)": "es9g51l5",
    "egg head (gottlieb 1961)": "gGoZTni00k",
    "eight ball (bally 1977)": "jihF7ko0",
    "eight ball champ (bally 1985)": "-FCJD9TCu2",
    "eight ball deluxe (bally 1981)": "ktfL5Wp5",
    "el bueno el feo y el malo (original 2015)": "EPqSRnCC",
    "el dorado (gottlieb 1975)": "yBxnevfM",
    "el dorado (zen studios 2013)": "Hy9ZkBRX",
    "el dorado city of gold (gottlieb 1984)": "qy0LZKZa",
    "elder scrolls v skyrim pinball, the (zen studios 2016)": "9FDT5aNv",
    "electra-pool (gottlieb 1965)": "TnWtSnCV",
    "electric mayhem (original 2016)": "40-_M06J",
    "electric state og, the (original 2025)": "aK5weUZTcT",
    "elektra (bally 1981)": "XZ0464N8",
    "elf pinball xl (original 2018)": "LrPb5Px9",
    "elijah's batman pinball (original 2025)": "oIdGQg6mpS",
    "elite guard (gottlieb 1968)": "b7Dqg5P2",
    "elton john (original 2025)": "LypETTrZKA",
    "elvira and the party monsters (bally 1989)": "zG9bcULH",
    "elvira and the party monsters - nude edition (bally 1989)": "zp_2duHs",
    "elvira's house of horrors remix (original 2021)": "1Qzqsg9R",
    "elvira's house of horrors remix - blood red kiss edition (original 2021)": "7Egh1sJAck",
    "elvira's house of horrors remix - blood red kiss pup-pack edition (original 2021)": "Po5iv_ghSu",
    "elvis (stern 2004)": "1JzYfL7f",
    "elvis gold (limited edition) (stern 2004)": "7gJBIJ_SQy",
    "embryon (bally 1981)": "o1EiUMdi",
    "eminem (original 2019)": "ir-ASQB0",
    "eminem - pup-pack edition (original 2019)": "hmxbT_En0S",
    "endless summer, the (original 2020)": "SjkOK78o",
    "epic quest (zen studios 2013)": "dUwiyQMX",
    "escape from monkey island (original 2021)": "wmgWPmI3",
    "escape from new york (original 2020)": "QLKNk25l",
    "escape from the lost world (bally 1988)": "1eBpyWTc",
    "estopa (original 2022)": "iNkDEt65",
    "europe (original 2025)": "kgua8pl825",
    "evanescence (original 2021)": "yGAqNrSp2m",
    "evel knievel (bally 1977)": "74bDv1DMiD",
    "everquest ii pinball tribute (original 2023)": "UYWJJ45WDd",
    "everquest pinball tribute (original 2023)": "S97NXT1x7X",
    "evil dead (original 2018)": "DrEa5ApS9a",
    "evil dead 2 (original 2019)": "tGWj8-z9",
    "evil dead 2 (original 2022)": "jAZpN8ybf2",
    "evil dead 3 army of darkness (original 2020)": "Cul9IFTa",
    "evil fight (playmatic 1980)": "XAqw58HgYV",
    "excalibur (gottlieb 1988)": "p_s1VK4H",
    "excalibur (zen studios 2013)": "_cZVfWoF",
    "exorcist, the (original 2023)": "K0gfOLgp3X",
    "experiments of alchemical chaos (original 2024)": "wshgN88wIy",
    "extremoduro pinball (original 2021)": "652e4XLI",
    "eye of the beholder pinball (original 2023)": "87vf86Xz8k",
    "eye of the tiger (gottlieb 1978)": "Bg-ftVZATv",
    "f-14 tomcat (williams 1987)": "3mc1YJJO",
    "f-14 tomcat - afterburner edition (williams 1987)": "CyC-yYX28c",
    "f-14 tomcat - ultimate pro edition (williams 1987)": "VVFlr3Ej5y",
    "faces (sonic 1976)": "bqlUfNqf",
    "faeton (juegos populares 1985)": "oJw1kilZ",
    "fair fight (recel 1978)": "9k38chYycL",
    "fairy favors (original 2024)": "9Si1Zv8KQm",
    "falling in reverse (original 2025)": "6YYOcLfoLO",
    "fallout - season one (original 2024)": "RzYEuMHUTR",
    "fallout - season one - vault edition (original 2024)": "mUYcb63dvR",
    "fallout pinball (zen studios 2016)": "UFFpuobs",
    "family guy (stern 2007)": "2XNBa0XX",
    "family guy christmas (original 2019)": "tYbnqYK_OZ",
    "family guy pinball (zen studios 2015)": "lTHBYMUW",
    "fan-tas-tic (williams 1972)": "cWmX7zNm2c",
    "fantastic four (zen studios 2011)": "WYLSAx-T",
    "far cry 3 - blood dragon (original 2018)": "8ZKqX3eD",
    "far out (gottlieb 1974)": "LL-PlTwB",
    "farfalla (zaccaria 1983)": "aox9uh_t",
    "farwest (fliperbol 1980)": "33x_ceKQ8g",
    "fashion show (gottlieb 1962)": "PQyq7pmZxj",
    "fast and furious (original 2022)": "SG8ej0txB_",
    "fast draw (gottlieb 1975)": "qGEWcWNx",
    "father ted (original 2024)": "BIzkxfeg7P",
    "fathom (bally 1981)": "E551pHQO",
    "fathom - led edition (bally 1981)": "u2mfnGOd",
    "fear itself (zen studios 2012)": "Xgz6W5te",
    "feiseanna (original 2022)": "kWMQzKOeiH",
    "feiseanna ii - dream worlds (original 2022)": "okVb4ZnmKn",
    "ferris bueller's day off (original 2022)": "C57khfCome",
    "fifteen (inder 1974)": "jN3V13AYtu",
    "fifth element, the (original 2022)": "0_nir8w6ie",
    "fight night (original 2021)": "Z90Jj7zr",
    "fire action (taito do brasil 1980)": "bL5MHbwA",
    "fire action de luxe (taito do brasil 1983)": "lu90hcDV",
    "fire queen (gottlieb 1977)": "iYBWYrqO",
    "fire! (williams 1987)": "i2rXjn5Y",
    "fireball (bally 1972)": "V1EMmCe9",
    "fireball classic (bally 1985)": "uzPhhqXVa7",
    "fireball ii (bally 1981)": "PYN3jDqp",
    "fireball xl5 (original 2024)": "9c7By99buA",
    "firecracker (bally 1971)": "PRcpitXm",
    "firepower (williams 1980)": "dU-vGqph",
    "firepower ii (williams 1983)": "MLyJLTb1",
    "firepower vs. a.i. (williams 1980)": "7wkuyFHT",
    "fish tales (williams 1992)": "2YdpwiGg",
    "fish town (original 2022)": "36t_tBT94y",
    "five finger death punch (original 2023)": "ub9TLw08Cu",
    "five nights at freddy's (original 2021)": "MezX2thG",
    "five nights at freddy's pizza party (original 2020)": "zWUdnhw4",
    "fj (hankin 1978)": "GjzkjINm",
    "flash (williams 1979)": "fWBYQ4Uf",
    "flash - comic verison, the (original 2024)": "YeAMnMK7tD",
    "flash dragon (playmatic 1986)": "rQ17lAstAq",
    "flash gordon (bally 1981)": "JRxbFudGzn",
    "flash, the (original 2018)": "pye1bWUm",
    "flashman (sport matic 1984)": "dPavnEpRpF",
    "fleet jr. (bally 1934)": "eTF6idY-Y8",
    "fleetwood mac (original 2025)": "eaN4GYizH6",
    "flicker (bally 1975)": "So_PDZkAOp",
    "flight 2000 (stern 1980)": "CD6xp14v",
    "flintstones, the (williams 1994)": "ig1I06fQ",
    "flintstones, the - cartoon edition (williams 1994)": "5BnRoEFt",
    "flintstones, the - the cartoon vr edition (williams 1994)": "Zs8rYEiMsE",
    "flintstones, the - vr cartoon edition (williams 1994)": "W5B234qCzN",
    "flintstones, the - yabba dabba re-doo edition (williams 1994)": "3TIHgVCKhQ",
    "flip a card (gottlieb 1970)": "er6W8OW7",
    "flip flop (bally 1976)": "bSffh7ktLa",
    "flipper fair (gottlieb 1961)": "9UBxnd9f",
    "flipper football (capcom 1996)": "CaPztNoj",
    "flipper pool (gottlieb 1965)": "DilK7G3c",
    "floopy bat (original 2022)": "ndWc1kBhEj",
    "flower man, the (original 2025)": "TuV7Yy5f9o",
    "fly, the (original 2023)": "lg_ctB2V3V",
    "flying carpet (gottlieb 1972)": "_gldmTPb",
    "flying chariots (gottlieb 1963)": "UH5zriP7",
    "flying turns (midway 1964)": "dD0OD8vO",
    "fog, the (original 2020)": "SjrvM_f1",
    "foo fighters (original 2021)": "ZmydZ_XJ",
    "football (taito do brasil 1979)": "yWHXZuV3",
    "force (ltd do brasil 1979)": "3WBxX3Zj",
    "force ii (gottlieb 1981)": "HYofGN40",
    "foreigner (original 2025)": "qKPmkFOJwR",
    "forge (original 2023)": "1mYC1bqZex",
    "forgotten planet - murray leinster, the (original 2024)": "azyIwM2J23",
    "forrest gump (original 2023)": "620RhMAmqM",
    "fortnite (original 2024)": "Q8DOi1_yat",
    "four million b.c. (bally 1971)": "oGQExHwR",
    "four seasons (gottlieb 1968)": "XoUDyw3_",
    "frank thomas' big hurt (gottlieb 1995)": "ySzKsg45sb",
    "freddy - a nightmare on elm street (gottlieb 1994)": "us5egxCa",
    "freddy's nightmares (original 2025)": "SY9OhbCQXm",
    "free fall (gottlieb 1974)": "D0YS5npn",
    "freedom (em) (bally 1976)": "TJKUqd_w",
    "freedom (ss) (bally 1976)": "j5_AEurjyN",
    "freefall (stern 1981)": "GZ-_ILcT",
    "friday the 13th (original 2017)": "fhtRZIlJ",
    "friday the 13th (original 2022)": "5qJl2zCsX1",
    "friday the 13th part ii (original 2019)": "RlF2Gq-q",
    "from dusk till dawn (original 2022)": "smryB2FF",
    "frontier (bally 1980)": "RQcHicK8UO",
    "full (recreativos franco 1977)": "fjQOoZz6",
    "full house (williams 1966)": "VeXMsbPECW",
    "full metal jacket (original 2022)": "LAmyc7E-1-",
    "full throttle (original 2023)": "Pl6L2obzhd",
    "fullmetal alchemist (original 2007)": "GTTIWT1kXu",
    "fun fair (gottlieb 1968)": "MFvYSojn",
    "fun land (gottlieb 1968)": "IPjKm2n4",
    "fun park (gottlieb 1968)": "S4vP75C7",
    "fun-fest (williams 1972)": "utAAPUQU7P",
    "funhouse (williams 1990)": "6VQ2VkcY",
    "futurama (original 2024)": "GzUJtTjUKM",
    "future spa (bally 1979)": "o0g0o1VmA7",
    "galaga pinball (original 2021)": "7NhUNvrWn3",
    "galaxia (ltd do brasil 1975)": "ntmEJgITsu",
    "galaxia (original 2025)": "xR7KT-FjR1",
    "galaxie (gottlieb 1971)": "2DvVeThZ",
    "galaxy (sega 1973)": "izRX-ZRfHp",
    "galaxy (stern 1980)": "znNFli5nep",
    "galaxy play (cic play 1986)": "KLrV_gyb",
    "galaxy quest (original 2020)": "s3bFxFB8",
    "galaxy quest - pup-pack edition (original 2020)": "hya9GCE-",
    "gamatron (pinstar 1985)": "u13hTSjuAM",
    "gamatron (sonic 1986)": "_C6-IIJWXt",
    "gamblin daze (original 2023)": "10_HETYhQB",
    "game of thrones (limited edition) (stern 2015)": "Xv2JtB8_a1",
    "game of thrones (original 2021)": "iH5drECa",
    "games i, the (gottlieb 1983)": "YmyL3XhuGk",
    "games, the (gottlieb 1984)": "h2gszbGh",
    "garfield pinball (zen studios 2021)": "QqLAzOpojJ",
    "gargamel park (original 2016)": "SZNmTj_xSQ",
    "gaston pinball machine, the (original 2020)": "JzQA-vPD",
    "gaucho (gottlieb 1963)": "wvmY0vJssu",
    "gay 90's (williams 1970)": "90fzh8RlN9",
    "geega (original 2025)": "Ig0Yt0gSKg",
    "gemini (gottlieb 1978)": "-H4DMKd9",
    "gemini 2000 (taito do brasil 1982)": "yexCMrnO",
    "genesis (gottlieb 1986)": "-er8rIM00z",
    "genesis (original 2025)": "96rsGoZUTr",
    "genie (gottlieb 1979)": "ONx0NORQ",
    "genie - fuzzel physics edition (gottlieb 1979)": "COXI7LSgqO",
    "george michael - faith (original 2023)": "sSobZIMQ6W",
    "get smart (original 2021)": "XhvsKHRD",
    "getaway - high speed ii, the (williams 1992)": "UExbSJLf",
    "ghost (original 2023)": "Zd_pZAszOC",
    "ghost ramps and dmd test (original 2016)": "Jw2JwbU7Gh",
    "ghost rider (zen studios 2011)": "TcQjFFMC",
    "ghost toys vpx model pack (original 2016)": "mA5NYuJDtJ",
    "ghostbusters (limited edition) (stern 2016)": "T70qtkCCa1",
    "ghostbusters (limited edition) - daytime ultimate edition (stern 2016)": "heaEuxklld",
    "ghostbusters (limited edition) - nighttime ultimate edition (stern 2016)": "05wisipl7v",
    "ghosts 'n goblins (original 2018)": "cyEeoLfN",
    "gigi (gottlieb 1963)": "B1xTHUeX",
    "gilligan's island (bally 1991)": "opqgX5Su",
    "gladiators (gottlieb 1993)": "x9ANmZ3X",
    "gnome slayer yuki (original 2024)": "kQd_k4837v",
    "godfather, the (original 2024)": "Hfae8mMOK-",
    "godzilla (sega 1998)": "eNV3xuQI",
    "godzilla (stern 2021)": "MXlJiiadNN",
    "godzilla pinball (zen studios 2023)": "36OFEZJDQf",
    "godzilla remix (limited edition)  (original 2021)": "rjaOeIhtuq",
    "godzilla remix (limited edition)  - 70th anniversary premium edition (original 2021)": "PBBcAzNnwr",
    "godzilla vs. kong (original 2023)": "O9gS0uNl2P",
    "godzilla vs. kong pinball (zen studios 2023)": "P37sYdYPpD",
    "goin' nuts (gottlieb 1983)": "f_C-13K1",
    "gold ball (bally 1983)": "N44p_zA8",
    "gold crown (pierce 1932)": "WUkSApIGgG",
    "gold mine (williams 1988)": "nDcrUuaK",
    "gold rush (williams 1971)": "DT15YkI7",
    "gold star (gottlieb 1954)": "Noty778pZC",
    "gold strike (gottlieb 1975)": "B-O2uiHF",
    "gold wings (gottlieb 1986)": "pmncg9cT",
    "golden arrow (gottlieb 1977)": "aEPF2r1g",
    "golden axe (original 2018)": "SR-tIid3",
    "golden birds (original 2015)": "zxjJA_2y",
    "golden cue (sega 1998)": "8hOnTBtR_w",
    "goldeneye (sega 1996)": "Ph8_kB5U",
    "goldorak (original 2017)": "LFA_TDxV",
    "goldorak - ufo robot goldrake (original 2017)": "Fo_a1BlO5B",
    "goldorak - ufo robot grendizer (original 2017)": "z2ScnVs-R6",
    "goldwing (original 2018)": "qUko3qC8",
    "gollum - the rings of power edition (original 2023)": "V5aSr8_tIH",
    "goonies never say die pinball, the (original 2021)": "RJ5FwXlX",
    "goonies never say die pinball, the - french edition (original 2021)": "IUTaS3yojf",
    "goonies pinball adventure, the (original 2019)": "Df3SZTrOum",
    "gorgar (williams 1979)": "5iT8B6SClL",
    "gorillaz (original 2024)": "J5yOLvXzAH",
    "gork (taito do brasil 1982)": "TVVtk5v4",
    "gradius (original 2017)": "QGgpcu9w",
    "grand casino (j.p. seeburg 1934)": "4GZhO2TWT5",
    "grand lizard (williams 1986)": "fTJtnlSb",
    "grand prix (ltd do brasil 1977)": "SYzPJpLokj",
    "grand prix (stern 2005)": "WKXoEhuk87",
    "grand prix (williams 1976)": "BvpGzkmM",
    "grand slam (bally 1983)": "whyKjE2h",
    "grand slam (gottlieb 1953)": "uiksnzaV1I",
    "grand slam (gottlieb 1972)": "PXHIlvf-hH",
    "grand tour (bally 1964)": "U-ENxma_",
    "grande domino (gottlieb 1968)": "kGA5gGwz",
    "granny and the gators (bally 1984)": "HYJXHFww",
    "grateful dead (original 2020)": "hc8UUeFo",
    "grease (original 2020)": "Ca_cXoyx",
    "great giana sisters, the (original 2018)": "FgSHk5Uh",
    "great houdini (original 2022)": "GNkoSt8VsB",
    "greedo's cantina pinball (original 2019)": "CLyYiHZP",
    "green day - american idiot (original 2025)": "PMxMwdbbAl",
    "green day - dookie (original 2025)": "xU-zzLC_v3",
    "green lantern (original 2024)": "pk_2-lbS0z",
    "green pastures (gottlieb 1954)": "fyrdbT2H-Q",
    "gremlins (original 2022)": "x2-lo9dOv2",
    "gremlins pinball (original 2019)": "Fa_80Ld0",
    "gridiron (gottlieb 1977)": "_mPZCB19",
    "grillshow the pinball adventure (original 2019)": "lAbuzW13",
    "grimm tales (zen studios 2023)": "LGo6yktchH",
    "grinch pinball, the (original 2020)": "UO6KgOnw",
    "grinch's how to steal christmas, the (original 2025)": "Ea9sHIUZOd",
    "grinch, the (original 2022)": "iT_n53MJgF",
    "groovy (gottlieb 1970)": "p12-u0rh",
    "guardians of the galaxy (pro) (stern 2017)": "pq6RYRws",
    "guardians of the galaxy trilogy (original 2023)": "_3ZHbzlbuv",
    "gulfstream (williams 1973)": "l7h7YUAH",
    "gun men (staal 1979)": "7NwE42o-fg",
    "gundam wing (original 2022)": "SLN0IjgG",
    "guns n' roses (data east 1994)": "sU-9RCyd",
    "guns n' roses remix (original 2021)": "F-fNFHdX",
    "gunship (original 2023)": "OW53xAVz9d",
    "hairy-singers (rally 1966)": "U-fs0GRRnR",
    "half-life (original 2019)": "4cLZAfQz",
    "hall & oates (original 2025)": "cu4E3Il0Gs",
    "halley comet (juegos populares 1986)": "yK7NaGlFzv",
    "halley comet - alternate plastics edition (juegos populares 1986)": "y3cuVwIf2s",
    "halloween (original 2019)": "68mNMvWU",
    "halloween (original 2023)": "CK9P8JB4AY",
    "halloween - big bloody mike (original 2022)": "6eh39WdnU5",
    "halloween - ultimate pro (original 2022)": "vgPKwijwaT",
    "halloween 1978-1981 (original 2022)": "PbXCoo8mKk",
    "halloween michael myers pinball adventures (original 2018)": "bMpwluGU",
    "halo (original 2021)": "LCac647P",
    "hamilton (original 2025)": "_yakbTFqlU",
    "hanafuda garden (original 2022)": "gVdBT_-Aac",
    "hang glider (bally 1976)": "K3mZhWVo",
    "hank williams pinball (original 2022)": "y0q1XDeOJf",
    "hannibal lecter (original 2022)": "mNXhk6gu8D",
    "hans zimmer (original 2025)": "U8y_NnKm4W",
    "happy clown (gottlieb 1964)": "eFO4fwfDiN",
    "happy tree friends x-mas pinball (original 2025)": "JNiuAtrmdo",
    "hardbody (bally 1987)": "udhnb_gnEN",
    "harlem globetrotters on tour (bally 1979)": "Q0LATrbd",
    "harley quinn (original 2017)": "iXVpMw9p",
    "harley quinn - b&w edition (original 2017)": "gSSpMX8x71",
    "harley-davidson (bally 1991)": "x1rx7tHdf1",
    "harley-davidson (sega 1999)": "j_uSP2yZ",
    "harmony (gottlieb 1967)": "ySJQXwXq",
    "harry potter and the goblet of fire (original 2020)": "_JEoeUt5Og",
    "harry potter and the prisoner of azkaban (original 2021)": "SviANMkz9e",
    "harvest frenzy (original 2025)": "MnNZP5emP-",
    "hatch rally (original 2006)": "p5MomsI0aS",
    "hateful eight, the (original 2021)": "bMOOIm0V",
    "haunted hotel (ltd do brasil 1983)": "sfat7Ejm",
    "haunted house (gottlieb 1982)": "LTp7lFr2",
    "hawaiian beauty (gottlieb 1954)": "QUy9NyfRgy",
    "hawkman (taito do brasil 1983)": "jD4GDxo0",
    "hayburners (williams 1951)": "9aPGECJm",
    "hearts and spades (gottlieb 1969)": "cnQT9hR_",
    "hearts gain (inder 1971)": "xSTJ7oigpO",
    "heat ray heist (original 2025)": "Lg0QQz6UPB",
    "heat wave (williams 1964)": "0R5lEnHP",
    "heavy fire (original 2020)": "htD8asR1",
    "heavy metal (rowamet 1981)": "or_OYzZF",
    "heavy metal meltdown (bally 1987)": "jMLeexJG",
    "heineken (original 2020)": "zEP3GaXD",
    "hell hound (original 2026)": "8Xs-RJoiMb",
    "hellboy pinball (original 2024)": "NpJDdu882N",
    "hellfire (original 2021)": "rUg-LKV0QD",
    "hellraiser (original 2022)": "1Dbo7GYl4P",
    "hercules (atari 1979)": "ZY9KIY01JL",
    "hextech (original 2016)": "GA9tYl5q",
    "hi-deal (bally 1975)": "ifwykSGo",
    "hi-diver (gottlieb 1959)": "ZOX21hkD",
    "hi-lo (gottlieb 1969)": "3k8KOw17",
    "hi-lo ace (bally 1973)": "bVXx23lQ",
    "hi-score (gottlieb 1967)": "soQGNz9jHc",
    "hi-score pool (chicago coin 1971)": "xSYxy1uv",
    "hi-skor (hi-skor 1932)": "7aKmXS0iC1",
    "high hand (gottlieb 1973)": "aSM20ope",
    "high roller casino (stern 2001)": "sOWxJaXb",
    "high seas (gottlieb 1976)": "IpvmwyFU",
    "high speed (williams 1986)": "p1Ur8qLo",
    "highlander (original 2020)": "YIwHHA9l",
    "hiphop (original 2024)": "uMXC-WMr_y",
    "hit the deck (gottlieb 1978)": "OaYgN7rQ",
    "hokus pokus (bally 1976)": "Uya2aiZ5",
    "holiday (chicago coin 1948)": "QzRHJp4Hjo",
    "holloween - trick or treat (original 2025)": "EoizqALTJt",
    "hollywood heat (gottlieb 1986)": "vQ2UaEql",
    "home alone (original 2019)": "YfLGLtOg",
    "home alone (original 2021)": "jPE9xmaE",
    "home alone 2 (original 2020)": "M6w29H3k",
    "home run (gottlieb 1971)": "DJAuD5ky",
    "homeworld - journey to hiigara pinball (zen studios 2023)": "hpPzxC1ZTN",
    "honey (williams 1971)": "ra0yxRHzfQ",
    "hong kong phooey (original 2025)": "S-FVGvn6PC",
    "hook (data east 1992)": "7S8T4SuK",
    "hoops (gottlieb 1991)": "9KsJVtqR",
    "hootenanny (bally 1963)": "OKnjQ4d0",
    "horrorburg (original 2023)": "SV8KX1l6e1",
    "horseshoe (a.b.t. 1931)": "VKmkViXCMx",
    "hot ball (taito do brasil 1979)": "NW93dZTu",
    "hot hand (stern 1979)": "fBFF5gt_",
    "hot line (williams 1966)": "JKvcdK_4",
    "hot shot (gottlieb 1973)": "fikoiavU",
    "hot shots (gottlieb 1989)": "uD3k1i0f",
    "hot tip (williams 1977)": "ShUlis-y",
    "hot tip - less reflections edition (williams 1977)": "Tf2tUSCH",
    "hot wheels (original 2021)": "HjNguMJz",
    "hotdoggin' (bally 1980)": "mV9Nxa_4",
    "houdini (original 2019)": "minunTjMTB",
    "house of diamonds (zaccaria 1978)": "LpPc4C4M",
    "howl against the chains - lunar howl 2 (original 2025)": "UB8GI8YOFu",
    "humpty dumpty (gottlieb 1947)": "s393znjkK1",
    "hungry dead, the (original 2005)": "WdlIC0iLdT",
    "hunter (jennings 1935)": "vE4h59SP",
    "hurricane (williams 1991)": "7BwZ2kB3",
    "hustler (ltd do brasil 1980)": "BUrtz6Uk",
    "hyperball (williams 1981)": "Z_Md2XIW",
    "hyperball - analog joystick edition (williams 1981)": "o-2Xgts1n_",
    "hyperball - analog mouse edition (williams 1981)": "DIahnJnu",
    "i dream of jeannie (original 2019)": "_ovvVJVX",
    "i.g.f. interstellar ground force (original 2025)": "cPyqwHSfYu",
    "ice age - a mammoth xmas pinball (original 2020)": "hhuzWT64",
    "ice age christmas (original 2021)": "OaMJaHHq",
    "ice cold beer (taito 1983)": "f5-tW6tS",
    "ice fever (gottlieb 1985)": "6PLlVnyy",
    "ignition (digital illusions 1992)": "-widEnBNEx",
    "impacto (recreativos franco 1975)": "h5VAZ4I6",
    "impractical jokers (original 2015)": "N6Fw1kPI",
    "incredible hulk, the (gottlieb 1979)": "QMIFlbdGy7",
    "independence day (sega 1996)": "knlloaW2",
    "indestructible pack - lunar howl 4 (original 2026)": "tjpqYeFzSv",
    "indiana jones (stern 2008)": "a0u7vvLT5b",
    "indiana jones - fortune and glory (original 2020)": "BVxaZVq5xA",
    "indiana jones - the last movie (original 2023)": "I0ysaAqWSq",
    "indiana jones - the pinball adventure (williams 1993)": "jnu1B1pP",
    "indiana jones - ultimate pro (original 2020)": "08C9YHoZJ-",
    "indianapolis 500 (bally 1995)": "K4f5HSsX",
    "indochine (original 2020)": "pgc8LAS1_n",
    "indochine central tour (original 2023)": "lHWEFnroih",
    "infected mushroom pinball - limited edition (rayworks 2025)": "gK1e9MmdPF",
    "infectious grooves (original 2021)": "gnU36ySC",
    "infinity gauntlet, the (zen studios 2014)": "65_UJ3Ll",
    "information society (original 2025)": "qSLFDxyr9c",
    "inhabiting mars (original 2023)": "J0uGLweyve",
    "inspector gadget (original 2021)": "6xrKCNn0s2",
    "insus, the (original 2020)": "KlP9tXKo",
    "inuyasha (original 2022)": "3U_glqsN",
    "inuyasha - special edition (original 2022)": "0EBgxXqnU7",
    "invader (original 2020)": "k9lUk8XI",
    "ipanema (ltd do brasil 1976)": "n2cj9UW09B",
    "iron balls (unidesa 1987)": "HmA-OceA",
    "iron eagle (original 2025)": "lL-INK2dfG",
    "iron maiden (original 2017)": "DzvH1Ybd1l",
    "iron maiden (original 2019)": "GORUq_qA",
    "iron maiden (original 2025)": "zbhZZEMfl-",
    "iron maiden (original 2026)": "SgmkCsiOL4",
    "iron maiden (stern 1982)": "Tl1WRb12ny",
    "iron maiden legacy of the beast - limited edition (stern 2018)": "_UMEFSmYor",
    "iron maiden legacy of the beast - pro (stern 2018)": "xJ9vBfm2Ib",
    "iron maiden senjutsu (original 2021)": "AscPKtsv",
    "iron maiden virtual time (original 2020)": "CXCYpKzH",
    "iron maiden virtual time - pup-pack edition (original 2020)": "PATkNto6cw",
    "iron man (pro vault edition) (stern 2014)": "suBQeZPkju",
    "iron man (stern 2010)": "rwVS2U8w",
    "iron man (zen studios 2010)": "deYR0ryi",
    "iron mike tyson (original 2024)": "2_Td656JK1",
    "it pinball madness (original 2022)": "fvb6yyiKqi",
    "j6 insurrection (original 2022)": "paVtQwiefl",
    "jabberjaw (original 2021)": "ocBvjBzgmO",
    "jack daniel's (original 2020)": "KGpYvPJQ",
    "jack daniel's 2 (original 2021)": "O5EwrF50",
    "jack in the box (gottlieb 1973)": "mVOx3EeZ",
    "jack sparrow (original 2023)": "XiVQmvVnMp",
    "jack-bot (williams 1995)": "gRRS4ld1",
    "jackpot (williams 1971)": "MpDVpsPo",
    "jacks open (gottlieb 1977)": "mghQM3se",
    "jacks to open (gottlieb 1984)": "nISIfh3j",
    "jake mate (recel 1974)": "bZX1mrX4dN",
    "jalisco (recreativos franco 1976)": "DMJDujZ973",
    "jalopy (williams 1951)": "sDs1azok",
    "james bond (original 2021)": "GrKDNMAP",
    "james bond 007 (gottlieb 1980)": "A1wxTjE3",
    "james cameron's avatar (stern 2010)": "CtUngRyI",
    "james cameron's avatar - neytiri's revenge (stern 2010)": "KZrnRk9ZVe",
    "james cameron's avatar - ultimate (stern 2010)": "qCkpP_CrIC",
    "jaws (original 2013)": "ULqUHOvG",
    "jaws - 50th anniversary (original 2025)": "DJwGB6g1ra",
    "jaws - bigger boat edition (original 2013)": "9cDtSQAyqF",
    "jaws - ultimate pro (original 2013)": "f48eiu1kom",
    "jaws pinball (zen studios 2017)": "3EzxXw-D",
    "jayce and the wheeled warriors (original 2024)": "WryYTv5nsN",
    "jeepers creepers (original 2024)": "0kem81TKml",
    "jeff wayne's musical version of war of the worlds (original 2025)": "D-WyID5S29",
    "jet set radio pinball (original 2020)": "90g_yVUr",
    "jet spin (gottlieb 1977)": "8zraF4R7",
    "jets (original 2023)": "pl0Sunc8Xo",
    "jimi hendrix (original 2021)": "jfHL4B4v",
    "jive time (williams 1970)": "LENyN6mF",
    "joe bar team (original 2019)": "jUb1hDgl",
    "joe bonamassa (original 2025)": "rB_9k_jQwT",
    "joe cocker (original 2025)": "MRZ7chdV0Y",
    "joe satriani (original 2025)": "8qgUtHaeOp",
    "john carpenter's christine (original 2019)": "9ciUIvCG",
    "john carpenter's the thing (original 2019)": "g6uSpszg",
    "john rambo (original 2024)": "flk9V8M6k0",
    "john wick - baba yaga pinball edition (original 2023)": "VG0a5Acwiy",
    "johnny cash pinball (original 2022)": "rXqcaosdNG",
    "johnny hallyday (original 2020)": "sG9cOVGW",
    "johnny mnemonic (williams 1995)": "qatHf_in",
    "joker (gottlieb 1950)": "uVj31Zg4",
    "joker poker (em) (gottlieb 1978)": "EeFoKM8qHo",
    "joker poker (ss) (gottlieb 1978)": "_08rndJ3S3",
    "joker wild (bally 1970)": "dO0lEYS5",
    "jokerz! (williams 1988)": "ZRBFZJ3xDT",
    "jolly park (spinball s.a.l. 1996)": "M9CgSziW",
    "jolly park oktoberfest (original 2024)": "ULjArOtFrP",
    "jolly roger (williams 1967)": "ROrXk5M6L0",
    "joust (bally 1969)": "n5J8OcKT",
    "joust (williams 1983)": "lPkKDpWP",
    "jp's addams family (bally 1992)": "vQjLGEld0D",
    "jp's captain fantastic (bally 1976)": "m13RHwNxRN",
    "jp's cyclone (original 2022)": "gGCkE0N1gK",
    "jp's dale jr. nascar (original 2020)": "JSd2NV7M",
    "jp's deadpool (original 2021)": "2MNxXWm5A5",
    "jp's deadpool - gold edition (original 2021)": "HIWfmJWNNM",
    "jp's foo fighters (original 2025)": "2w5fD4mMTU",
    "jp's friday the 13th (original 2021)": "XXCkW1j0QC",
    "jp's ghostbusters slimer (original 2017)": "HiSlXbfb",
    "jp's grand prix (stern 2005)": "hTpE8uT3",
    "jp's indiana jones (stern 2008)": "gIQ_cheyLG",
    "jp's iron man 2 - armored adventures (original 2018)": "hbPwe7B5zm",
    "jp's mephisto (cirsa 1987)": "q4bJG2UE_B",
    "jp's metallica pro (stern 2013)": "P-R9a8GPd1",
    "jp's motor show (original 2017)": "RS8rIAuG",
    "jp's nascar race (original 2015)": "mqN6b0Ls",
    "jp's papa smurf (original 2015)": "Kys-AtQLhZ",
    "jp's pokemon pinball (original 2016)": "dyoYyK7l93",
    "jp's seawitch (stern 1980)": "hMM0J00w",
    "jp's smurfette (original 2015)": "WmTckSZnYn",
    "jp's space cadet (original 2021)": "8zJDEwlpyu",
    "jp's space cadet - family edition (original 2021)": "e-dLHYkCah",
    "jp's space cadet - galaxy edition (original 2021)": "aHb-SNzjDs",
    "jp's spider-man (original 2018)": "FaPiG9T5e3",
    "jp's star trek (enterprise limited edition) (original 2020)": "5nBoxs6g",
    "jp's street fighter ii (original 2016)": "IyJL_Rh66T",
    "jp's terminator 2 (original 2020)": "GAqfmxLp",
    "jp's terminator 3 (stern 2003)": "qX8zBws_Jw",
    "jp's the avengers (original 2019)": "H-95t5dF",
    "jp's the lord of the rings (stern 2003)": "q8ac-RuR",
    "jp's the lost world jurassic park (original 2020)": "q7q5ZB1GXk",
    "jp's the walking dead (original 2021)": "V6g122anes",
    "jp's transformers (original 2018)": "y-olBUcR",
    "jp's vpx arcade physics (original 2022)": "ioROfNkcRD",
    "jp's whoa nellie! big juicy melons (original 2022)": "HIykvJBUPh",
    "jp's world joker tour (original 2024)": "nBHiWkJZqw",
    "jp's world joker tour - nfozzy mod (original 2024)": "flVincfT8n",
    "jp's wow monopoly (original 2015)": "RM3ShjGJ9A",
    "jp's wrath of olympus (original 2022)": "yGQ2e_hBMQ",
    "jubilee (williams 1973)": "znYipJdx",
    "judas priest (original 2019)": "vZkGb3CKZi",
    "judas priest (original 2024)": "Nizif9k111",
    "judge dredd (bally 1993)": "VLUr5w6E",
    "jukebox (seeburg 1965)": "8UBPMzwPgr",
    "jumanji (original 2023)": "pCxBuhBwtH",
    "jumping jack (gottlieb 1973)": "z-A9Dv8N",
    "jungle (gottlieb 1972)": "FV80qbW7",
    "jungle girl (original 2021)": "2v9AwLjTF_",
    "jungle king (gottlieb 1973)": "edfE4OXf",
    "jungle life (gottlieb 1972)": "MQ1fkeFU",
    "jungle lord (williams 1981)": "jqgiE2Np",
    "jungle princess (gottlieb 1977)": "l7q_8SnW",
    "jungle queen (gottlieb 1977)": "VMy2OHlC",
    "jungle quest (original 2022)": "5AJ3NGDPkP",
    "junk yard (williams 1996)": "7tR5UMpq",
    "junkyard cats (original 2012)": "T3jUV2lk25",
    "junkyard cats - bam edition (original 2012)": "yL4rRRj1_a",
    "jupiter (original 2023)": "Ijs8mEINqC",
    "jupiter ascending (original 2023)": "QZjXiewJO9",
    "jurassic park (data east 1993)": "2aJU8y9P",
    "jurassic park (original 2022)": "suKwLaMi",
    "jurassic park 30th anniversary (original 2023)": "hXWmfcKgAt",
    "jurassic park pinball (zen studios 2018)": "qDfmI9Qm",
    "jurassic park pinball mayhem (zen studios 2018)": "giOTxEfa",
    "jurassic world pinball (zen studios 2018)": "FQlI5tp1",
    "justin timberlake (original 2021)": "ukmgDZpw",
    "kat & roman kostrzewski (original 2023)": "P_My_abR_y",
    "kat & roman kostrzewski - pup-pack edition (original 2023)": "m9FNG2yZ30",
    "kessel run (original 2025)": "nlid4un_QR",
    "kick off (bally 1977)": "5RDLdkETk6",
    "kickoff (williams 1967)": "4N08ydR3",
    "kidnap (cic play 1986)": "0C74w0ay",
    "kill bill (original 2022)": "FC2Lf58DrB",
    "killer instinct (original 2024)": "yXsqhMH3VR",
    "killer klowns (original 2023)": "mi3NyppPHr",
    "killers hall of fame (original 2023)": "wBakclyqTE",
    "killswitch engine (original 2025)": "1XlnRn6_f4",
    "killzone (original 2019)": "A19yqLZj",
    "kilroy (chicago coin 1947)": "gE4NX1xchi",
    "kim wilde (original 2020)": "YTNvsrdb",
    "kim wilde (original 2025)": "VC_Vcko8WU",
    "king donkey kong (original 2023)": "S68HSxO8l_",
    "king kong (data east 1990)": "Sd2vZtaR",
    "king kong (ltd do brasil 1978)": "Kcr__s4a",
    "king kool (gottlieb 1972)": "4kkQhtjo",
    "king of diamonds (gottlieb 1967)": "PhwalUEo",
    "king of rock and roll (original 2022)": "6C2L6mOx",
    "king of the hill (original 2025)": "iQC3YbzBzM",
    "king pin (gottlieb 1973)": "Otk9YKG2",
    "king pin (williams 1962)": "1lw2kK0r",
    "king rock (gottlieb 1972)": "gXyU8fic",
    "king tut (bally 1969)": "asLVR1ZoI3",
    "king tut (williams 1979)": "AmBYA8j0",
    "kingdom (j. esteban 1980)": "01d06EShX7",
    "kingdom planets (original 2025)": "lfd3j7eqlS",
    "kingpin (capcom 1996)": "85M0M7pd",
    "kings & queens (gottlieb 1965)": "mHkuYC4J",
    "kings of steel (bally 1984)": "czXi3q1f",
    "kiss (bally 1979)": "Y-ovwFD6",
    "kiss (pro) (stern 2015)": "E-RHgwloOn",
    "kiss (pro) - pup-pack edition (stern 2015)": "y9jtZk_ZyM",
    "kiss - pup-pack edition (bally 1979)": "82hWxurqBC",
    "klondike (williams 1971)": "yclmpzRv",
    "knight rider (original 2021)": "C6Zb4Vlj",
    "knight rider - doflinx cabinet edition (original 2021)": "kkYwWZvFyv",
    "knight rider pinball - table_177 (zen studios 2024)": "fiAwdKyX8n",
    "knock out (gottlieb 1950)": "N5rzjyE_",
    "kong pinball (zen studios 2023)": "ZRB4lMcfMS",
    "kong vs. godzilla (original 2023)": "o9JlGXC1YL",
    "kratos - god of war (original 2018)": "sZ_3b4CL",
    "krull (gottlieb 1983)": "us6X9cua",
    "kung fu (ltd do brasil 1975)": "rGntrHV3bg",
    "kung fu hustle (original 2024)": "Gyq3bzPSLQ",
    "kusogrande (original 2025)": "FFHH_j2RCR",
    "kyrie (original 2025)": "4pCKnuekuu",
    "lab, the (original 2024)": "B5_AqAP9Qd",
    "labyrinth (original 2021)": "CT8CQ1qmcb",
    "labyrinth (original 2023)": "kiBIoviC9t",
    "lady death (geiger 1983)": "jCB3MUYL",
    "lady luck (bally 1986)": "OYHthvEu",
    "lady luck (recel 1976)": "rF_jhweD",
    "lady luck (taito do brasil 1980)": "Msbi1r7g",
    "lagerstein (original 2020)": "zphoPOoZ",
    "lap by lap (inder 1986)": "JtMvaMQxxM",
    "lariat (gottlieb 1969)": "y1bF2Yia",
    "laser ball (williams 1979)": "J0H5WwfJ",
    "laser cue (williams 1984)": "afSisLjS",
    "laser war (data east 1987)": "aevnnq35",
    "last action hero (data east 1993)": "Ze8skJeS",
    "last dragon, the (original 2020)": "i3YGfqa7",
    "last dragon, the (original 2025)": "HkS66qUUUa",
    "last lap (playmatic 1978)": "A7fPbfKq",
    "last ninja, the (original 2018)": "CAjmCnVY",
    "last of us, the (original 2018)": "BBqYhI7N",
    "last spaceship - murray leinster, the (original 2024)": "iZklndJhq_",
    "last starfighter, the (original 2020)": "RJAblUYK",
    "last starfighter, the (original 2023)": "D4APGqIYk8",
    "last unicorn, the (original 2020)": "S2sg-TqU",
    "lawman (gottlieb 1971)": "2l92MudD",
    "lazer lord (stern 1982)": "Tll4mMYJHO",
    "league champ (williams 1996)": "GQOPKRRw",
    "lectronamo (stern 1978)": "S3AgyJizja",
    "led zeppelin (original 2017)": "kzfpeK0F",
    "led zeppelin (original 2020)": "_zdNC4YT",
    "legend - a pinball adventure (original 2023)": "MpXNDD58qI",
    "legend of zelda twilight princess, the (original 2025)": "-ApRuWYKou",
    "legend of zelda, the (original 2015)": "I36NlujvZ7",
    "legends of valhalla (original 2021)": "29CElilm",
    "legends of wrestlemania (limited edition) (original 2023)": "99bgIPCfSC",
    "lego pinball (original 2022)": "c2hl1xE1Fo",
    "lenny kravitz (original 2025)": "RxrqvCo_vQ",
    "leprechaun king, the (original 2019)": "65U2ADbg",
    "les mystérieuses cités d'or (original 2022)": "Egd3DG_s",
    "lethal weapon 3 (data east 1992)": "BR4FaL60",
    "liberty bell (williams 1977)": "eldV7POC",
    "life is but a dream - avenged sevenfold (original 2024)": "DvbM30wrS2",
    "lightning (stern 1981)": "Eb6Jm9h6Gx",
    "lightning ball (gottlieb 1959)": "QLw4Fc_-",
    "lights...camera...action! (gottlieb 1989)": "ixeTCjG4Do",
    "lilo & stitch (original 2025)": "Kal3WbgT4z",
    "line drive (williams 1972)": "-LG9kCXH",
    "linkin park (original 2020)": "Bjmutf-T",
    "linkin park (original 2024)": "HFgLi3bgu3",
    "little chief (williams 1975)": "x4Mn6EU-AX",
    "little joe (bally 1972)": "gC-rrW9m",
    "loch ness monster (game plan 1985)": "STogIAnY",
    "locomotion (zaccaria 1981)": "6X98ROFL",
    "logan's run (original 2021)": "7FRpOBRqpO",
    "lone wolf mcquade (original 2020)": "I8B9R-tj",
    "looney tunes (original 2022)": "ykOBY5XvGC",
    "loony labyrinth (original 2024)": "YcK84lkGRz",
    "lord of the rings - the rings of power, the (original 2022)": "k3MXWkWoC6",
    "lord of the rings, the (stern 2003)": "iii4q4WpsG",
    "lord of the rings, the - valinor edition (stern 2003)": "ulolpyXq",
    "lortium (juegos populares 1987)": "5PJhpE3y",
    "lost boys, the (original 2025)": "3e5wQLWkOT",
    "lost in space (sega 1998)": "7vstFnBOZj",
    "lost world (bally 1978)": "R1H339sKVg",
    "lost world jurassic park, the (sega 1997)": "Btk9uVOUDd",
    "louis de funes - fantomas (original 2022)": "IIe5es7NrW",
    "love bug (williams 1971)": "9qP4N3Y7",
    "luck smile (inder 1976)": "nRbXUZxKPg",
    "luck smile - 4 player edition (inder 1976)": "UYzfszCUyn",
    "lucky ace (williams 1974)": "NNEYayg0",
    "lucky hand (gottlieb 1977)": "-aK4AJO7",
    "lucky luke (original 2020)": "fkvhWxm0",
    "lucky seven (williams 1978)": "sXhucU-J",
    "lucky strike (gottlieb 1975)": "EA2Q1mRL",
    "lucky strike (taito do brasil 1978)": "asi2XTcY",
    "lunar howl (original 2025)": "j7_wLt56NS",
    "lunelle (taito do brasil 1981)": "_LS_-hP_",
    "lupine and howling - lunar howl 3 (original 2026)": "nQQc7y4FH4",
    "mac jungle (mac 1987)": "5h8iG1e1",
    "mac's galaxy (mac 1986)": "fgrg8hd1",
    "mach 2.0 two (spinball s.a.l. 1995)": "M2USRO02b9",
    "machine - bride of pin-bot, the (williams 1991)": "-6XoDkj1",
    "mad max - fury road (original 2021)": "kvE46l3j",
    "mad max 2 - the road warrior (original 2019)": "H1k3cTKe",
    "mad race (playmatic 1985)": "3SZaM-7W2Z",
    "mad scientist (maxis 1996)": "yAIIlgFk",
    "magic (stern 1979)": "pRoH8Cc-",
    "magic - the gathering (original 2020)": "5YAbfD_Q",
    "magic castle (zaccaria 1984)": "mcxbEiKG",
    "magic circle (bally 1965)": "nDMCZgNNAr",
    "magic city (williams 1967)": "zIeopOUx",
    "magic clock (williams 1960)": "TuDJsu_q",
    "magic pinball (original 2025)": "ESBg49heU1",
    "magic town (williams 1967)": "3xzEux1s",
    "magnificent seven, the (original 2020)": "M9BftK7J",
    "magnotron (gottlieb 1974)": "Cn5OfNTu",
    "magnum p.i.nball (original 2020)": "T65EXODp",
    "mago de oz (original 2021)": "edenqx7z",
    "maisie (gottlieb 1947)": "0r3uEggzC_",
    "major league (pamco 1934)": "B577j2bu",
    "major payne (original 2021)": "2sOpd5WESu",
    "mandalorian, the (original 2020)": "1b-C4Uc8",
    "mandalorian, the (original 2023)": "OvYv_ivhgn",
    "mandalorian, the - razor crest (original 2023)": "IZDRaDmE5I",
    "manowar (original 2019)": "2YHZ8se0",
    "manowar (original 2021)": "QechES9R",
    "maple leaf, the (automatic 1932)": "yHACqkIv4R",
    "marble queen (gottlieb 1953)": "GTPU7HQNmK",
    "marilyn manson (original 2021)": "6Dk-QSeI",
    "marilyn monroe tribute (original 2022)": "RIXnED5Nod",
    "mariner (bally 1971)": "nfZF5lk-",
    "mario andretti (gottlieb 1995)": "On1oUzWw",
    "mario kart pinball (original 2022)": "nCyHfrN2fA",
    "marjorie (gottlieb 1947)": "qyKDKLI1Vm",
    "maroon 5 (original 2021)": "k0t4a_Ya",
    "married with children (original 2021)": "_Q0mEZ5qBW",
    "mars (zen studios 2013)": "6g8ojW7r",
    "mars attacks! pinball (original 2022)": "fvY_MOnW9O",
    "mars god of war (gottlieb 1981)": "zIBLifSAIr",
    "mars trek (sonic 1977)": "LTCTjTai0i",
    "marsupilami (original 2022)": "qKuo5_DwLO",
    "martian queen (ltd do brasil 1981)": "wtgZIwFm",
    "marvel's ant-man (zen studios 2015)": "wTckbG88",
    "marvel's avengers age of ultron (zen studios 2015)": "iArCcDWO",
    "marvel's guardians of the galaxy (zen studios 2014)": "RW88mv4s",
    "marvel's women of power - a-force (zen studios 2016)": "acHzfMzl",
    "marvel's women of power - champions (zen studios 2016)": "PquC9KP2",
    "marvel’s the avengers (zen studios 2012)": "n7dUb2J9",
    "mary shelley's frankenstein (sega 1995)": "0Ygqh7NP",
    "mary shelley's frankenstein - b&w edition (sega 1995)": "NWVtG6Sq",
    "mask (original 2023)": "fV0hg-c4H8",
    "mask, the (original 2019)": "d_0iIM0Q",
    "masquerade (gottlieb 1966)": "r1OKjx3U6o",
    "masters of the universe (original 2018)": "g9ZMfhVFhz",
    "masters of the universe (original 2021)": "gcOLfu0bjy",
    "masters of the universe - collectors edition (original 2018)": "mF6pqDl_SE",
    "masters of the universe - mastered edition (original 2018)": "4rOPu3T5GZ",
    "masters of the universe - unlimited edition (original 2018)": "z0l3GFPVgM",
    "mata hari (bally 1978)": "d_OiCWZD",
    "matrix, the (original 2023)": "Z6TQHOOYU-",
    "maverick (data east 1994)": "FQIed3Gh",
    "meat loaf (original 2025)": "ou6-xV-LjN",
    "medieval castle (original 2006)": "dhOcB_XGZs",
    "medieval madness (williams 1997)": "tukTr13P",
    "medieval madness - b&w edition (williams 1997)": "VJI7krHx",
    "medieval madness - redux edition (williams 1997)": "-uVoBnOY8U",
    "medieval madness - remake edition (williams 1997)": "DSxP_0x6Oa",
    "meducks (original 2024)": "mfPZDrpf-X",
    "medusa (bally 1981)": "QwDn4KfxSu",
    "mega man (original 2023)": "vPUJOUHVwi",
    "megadeth (original 2023)": "t9WZcMFwyU",
    "megadeth - thermo-nuclear protection (original 2025)": "hVULfYj07n",
    "melody (gottlieb 1967)": "_cFBLUGj",
    "memory lane (stern 1978)": "jaFHt_co",
    "men in black trilogy (original 2024)": "hA7QRdZvv6",
    "mermaid (gottlieb 1951)": "oEn1QUzus_",
    "merry-go-round (gottlieb 1960)": "RKVwh3es",
    "metal man (inder 1992)": "ZXXS00ZagM",
    "metal slug (original 2017)": "ZWY-HOwq",
    "metallica (premium monsters) (stern 2013)": "481v8uW4",
    "metallica (premium monsters) - christmas edition (stern 2013)": "T8T7yQbv",
    "metallica - master of puppets (original 2020)": "vZiwCBZ8",
    "meteor (stern 1979)": "1VUwLLR5",
    "meteor (taito do brasil 1979)": "ID0UMvvZ",
    "metropolis (maresa 1982)": "jeTw-6szrE",
    "metropolis reborn (original 2022)": "EQITnc1dTG",
    "mets (original 2023)": "aCAEBB98UW",
    "mf doom (original 2024)": "Ug53LOj8gf",
    "miami vice (original 2020)": "NInc9X4y",
    "mibs (gottlieb 1969)": "ifV0Vq-K",
    "michael jackson (original 2020)": "0WTIv8I3",
    "michael jordan (data east 1992)": "K5fS5a_e",
    "michael jordan - black cat edition (data east 1992)": "c3myb7ic",
    "mickey mouse happy christmas (original 2022)": "aGXHlKGcEC",
    "mickey mouse happy halloween (original 2022)": "Fp7E8Wa0XN",
    "mickey mouse in steamboat willie (original 2022)": "pkDACTJnym",
    "middle earth (atari 1978)": "MekNMAi9",
    "midget hi-ball (peo 1932)": "CXB1J30SNq",
    "midnight magic (atari 1986)": "v9Ohxq7f",
    "midnight resistance (original 2020)": "ZZywjo9L",
    "mighty morphin power rangers (original 2024)": "mgUCsU9tAl",
    "mike vegas (original 2023)": "Vh1f6o_OHJ",
    "mike's pinball - 10th anniversary edition (original 2024)": "m8Wi2-aZs6",
    "millionaire (williams 1987)": "6dItcjyZ",
    "minecraft (original 2020)": "2v1iujRA",
    "mini cycle (gottlieb 1970)": "U_q1bick",
    "mini golf (williams 1964)": "jpdTafAv6D",
    "mini pool (gottlieb 1969)": "9x3E1-U4",
    "mini-baseball (chicago coin 1972)": "9S0mThgd0x",
    "minions (original 2017)": "ALYKU0i7bf",
    "miraculous (original 2019)": "3gqaChYz",
    "misfits (original 2019)": "R3mcagT3",
    "miss world (geiger 1982)": "qOrxQR6R",
    "miss-o (williams 1969)": "93nO9b2bNu",
    "missing in action (original 2018)": "FBS7GRT_",
    "mission impossible (original 2022)": "IzNfqj-xZn",
    "mississippi (recreativos franco 1973)": "z1V_wBkgLL",
    "mobile suit gundam (original 2024)": "pZASiolF3K",
    "moebius - a tribute (original 2024)": "UESxbRr1lo",
    "monaco (segasa 1977)": "kLhyurZ6-J",
    "monday night football (data east 1989)": "kn100tWk",
    "monopoly (stern 2001)": "qWNEf5Mn",
    "monster bash (williams 1998)": "IoWHnBvo",
    "monster rancher (original 2019)": "BU3zQ6Az",
    "monsters (original 2016)": "3iA51Jbm",
    "monsters of rock (original 2021)": "7VrGGt0zt0",
    "monte carlo (bally 1973)": "WBXgsvdj",
    "monte carlo (gottlieb 1987)": "VfZE5fvS",
    "monty python (original 2022)": "yrKATchtFw",
    "moon knight (zen studios 2013)": "_8_jlukU",
    "moon light (inder 1987)": "JI34fjH4",
    "moon shot (chicago coin 1969)": "rNdMbMhUHd",
    "moon station (original 2021)": "R-oXZ4uw",
    "moon walking dead, the (original 2017)": "ToQ_Vlt8",
    "mortal kombat (original 2016)": "mrr3ry_M",
    "mortal kombat ii (original 2016)": "l595YApN",
    "motley crue (original 2017)": "-TxOjFbE",
    "motley crue - carnival of sin (original 2024)": "334s_AguDZ",
    "motordome (bally 1986)": "jv9OBGbMtf",
    "motörhead (original 2018)": "pCvuGNaK",
    "moulin rouge (williams 1965)": "mgVKY_Ri0q",
    "mousin' around! (bally 1989)": "zfBJdPcA",
    "mr. & mrs. pac-man pinball (bally 1982)": "V75hTHHW",
    "mr. & mrs. pec-men (ltd do brasil 1983)": "ZfHinkmsv1",
    "mr. big (original 2025)": "VxihcrGLkh",
    "mr. black (taito do brasil 1984)": "6ZpMRfLa",
    "mr. bubble (original 2018)": "f1JPDO1k",
    "mr. doom (recel 1979)": "fi0d8R86",
    "mr. evil (recel 1978)": "Cx6wTSCM",
    "ms. splosion man (zen studios 2013)": "IMrrNLLx",
    "mundial 90 (inder 1990)": "3X_Kp8pq",
    "munsters, the (original 2020)": "FhAokXrn",
    "munsters, the (original 2021)": "gHwra6DQ",
    "muppets (original 2022)": "qigT5wqw8g",
    "mushroom madness (original 2026)": "BVbeM3Kmbx",
    "mustang (gottlieb 1977)": "lxV9aiLx",
    "mustang (limited edition) (stern 2014)": "djaYi2Lb",
    "my little pony pinball (zen studios 2021)": "YXtrTxzp_k",
    "mystery castle (alvin g. 1993)": "GOA265Se",
    "mystery science theater 3000 - pinball peril (original 2021)": "ver5n_Ou",
    "mystic (bally 1980)": "GZXpYhSb",
    "mystical ninja goemon (original 2025)": "eo6lncr3Y-",
    "nagatoro (original 2023)": "wOuRELVX2_",
    "nags (williams 1960)": "7Td-pzgz1D",
    "nairobi (maresa 1966)": "6lp0OIj9",
    "namkwah (original 2025)": "VlXgYBExo7",
    "naruto pinball (original 2024)": "mF-gcvdF-7",
    "nascar (stern 2005)": "LX-bgTj1",
    "nascar - dale jr. (stern 2005)": "FlgGNdnK",
    "nascar - grand prix (stern 2005)": "0A7eTpIm",
    "national lampoon's christmas vacation (original 2019)": "v4DVUQGS",
    "nautilus (playmatic 1984)": "BhzWD-hq",
    "nba (stern 2009)": "gUCjGnlg",
    "nba chicago bulls (original 2022)": "UUcKGIHpZ_",
    "nba fastbreak (bally 1997)": "qmN4lKAT",
    "nba mac (mac 1986)": "Fqw4zW_s",
    "near dark (original 2025)": "wH0goglp-5",
    "nebulon (original 2025)": "JxxYGD1N6R",
    "nebulon 2 - humanity's stand (original 2025)": "P0ugIULCJb",
    "nebulon 3 - the final boss (original 2025)": "VjlEd6Zv0M",
    "need for speed (original 2018)": "pUuCHhyQ",
    "nemesis (peyper 1986)": "M1QkWrCX",
    "neptune (gottlieb 1978)": "_K0BPTR6",
    "neverending story, the (original 2021)": "HQE5NbSS",
    "nevermind the bollocks (original 2024)": "lJ1yaizNtr",
    "new wave (bell games 1985)": "_oNE9WCh",
    "new world (playmatic 1976)": "MtNXtRHz",
    "new york (gottlieb 1976)": "8TyRhWUJ",
    "nfl (stern 2001)": "9VRfEyjf50",
    "nfl - 49ers edition (stern 2001)": "XuexXwT0",
    "nfl - bears edition (stern 2001)": "yiPbSTsJ",
    "nfl - bengals edition (stern 2001)": "t63tu_Gd",
    "nfl - bills edition (stern 2001)": "W7eAT01c",
    "nfl - broncos edition (stern 2001)": "wSTdGqG8",
    "nfl - browns edition (stern 2001)": "Gn1vz-wb",
    "nfl - buccaneers edition (stern 2001)": "W8wZ-XAf",
    "nfl - cardinals edition (stern 2001)": "Yn329C7z",
    "nfl - chargers edition (stern 2001)": "iy52uxtW",
    "nfl - chiefs edition (stern 2001)": "RkRVi_f9",
    "nfl - colts edition (stern 2001)": "i1KPZQls",
    "nfl - commanders edition (stern 2001)": "hz8R3wdSyF",
    "nfl - cowboys edition (stern 2001)": "rvra9Yjn",
    "nfl - dolphins edition (stern 2001)": "Sadlupxn",
    "nfl - eagles edition (stern 2001)": "A_kR0yIu",
    "nfl - falcons edition (stern 2001)": "QFF0HDII",
    "nfl - giants edition (stern 2001)": "v2jwTq6S",
    "nfl - jaguars edition (stern 2001)": "v_WOy2D7",
    "nfl - jets edition (stern 2001)": "eE3DdN14",
    "nfl - lions edition (stern 2001)": "iME5AbDm",
    "nfl - packers edition (stern 2001)": "_Qj9skkQ",
    "nfl - panthers edition (stern 2001)": "mHJWEd6l",
    "nfl - patriots edition (stern 2001)": "dq7E9Qb5",
    "nfl - raiders edition (stern 2001)": "qSZ8aclq",
    "nfl - rams edition (stern 2001)": "svxY2RXb",
    "nfl - ravens edition (stern 2001)": "ay5QHr_4",
    "nfl - redskins edition (stern 2001)": "-eAAqSuf",
    "nfl - saints edition (stern 2001)": "AWJpEMtW",
    "nfl - seahawks edition (stern 2001)": "nb3WEHkR",
    "nfl - steelers edition (stern 2001)": "-7DWqzBF",
    "nfl - texans edition (stern 2001)": "LoI2qDj_",
    "nfl - titans edition (stern 2001)": "9T-DIlWO",
    "nfl - vikings edition (stern 2001)": "FNj23Xxq",
    "nickelback (original 2025)": "ak2_Rs9AL4",
    "night moves (international concepts 1989)": "0gGZC-Fr",
    "night of the living dead '68 (original 2018)": "daptIsOp",
    "night of the living dead (pinventions 2014)": "8CaLewwT",
    "night rider (bally 1977)": "eyojtQ_n",
    "nightmare (digital illusions 1992)": "sf3MmY-01C",
    "nightmare before christmas (original 2024)": "LI9FmU9PDM",
    "nightmare before christmas, the (original 2019)": "oA-XBGBy",
    "nightmare on elm street - ultimate (original 2013)": "BRqaTqjTvF",
    "nightmare on elm street - ultimate pro (original 2013)": "qAH-Qv7Ovs",
    "nine ball (stern 1980)": "NTissEZP",
    "nine inch nails (original 2023)": "8ASbYne-",
    "ninja gaiden (original 2023)": "Wdz9GsMCxI",
    "nip-it (bally 1973)": "QnNv85BUyM",
    "nirvana (original 2021)": "JWfcMj4w",
    "nitro ground shaker (bally 1980)": "1UT-jSAG",
    "no fear - dangerous sports (williams 1995)": "NkU9XqCn",
    "no good gofers (williams 1997)": "aUBpapLk",
    "nobs (original 2016)": "Q0FmmEmE",
    "north pole (playmatic 1967)": "18aek0ft",
    "north star (gottlieb 1964)": "O3LEgbZtfQ",
    "nosferatu 1922 (original 2023)": "sIghlRPN0S",
    "nova pinball (original 2024)": "D-RTgX6SE9",
    "now (gottlieb 1971)": "7vFY61-XyL",
    "nudge test and calibration (original 2017)": "BTHuQZHp",
    "nudge-it (gottlieb 1990)": "k57OC5yZ",
    "nudgy (bally 1947)": "FVQ9lsfWa3",
    "nugent (stern 1978)": "tasKxPmz",
    "nuka cola - pop-a-top pinball (original 2024)": "SZ2qyKRj97",
    "nuke em high (original 2024)": "PGx1pvWYG1",
    "o brother, where art thou (original 2021)": "NpPs9rJG",
    "o gaucho (ltd do brasil 1975)": "Ya6Cz71q5s",
    "oasis knebworth (original 2023)": "sN9Y1IotLj",
    "oba-oba (taito do brasil 1979)": "9T89IUJa6t",
    "oblivion (original 2023)": "VrcMS0BmZf",
    "octopus (nintendo 1981)": "yXu2BsG1",
    "odds & evens - bud spencer & terence hill (original 2021)": "CW-TalZLlL",
    "oddzilla (original 2023)": "9ymXd1nDSR",
    "odin deluxe (sonic 1985)": "3MEp7SBq",
    "odisea paris-dakar (peyper 1987)": "K_sBk4Cj",
    "off road racers (original 2025)": "UkGIhkyu52",
    "office, the (original 2021)": "pfJlsBcv",
    "oktoberfest - pinball on tap (original 2024)": "SN55hCv4X0",
    "ol' ireland (original 2018)": "JwAD5Asv",
    "old chicago (bally 1976)": "WsUuvD6i",
    "old coney island! (game plan 1979)": "z4uQwFVcHu",
    "old tunes - volume 1 (original 2025)": "LwJsIF1R_d",
    "old tunes - volume 2 (original 2025)": "6X2CzOB4is",
    "old tunes - volume 3 (original 2025)": "WwIpEPA2DP",
    "olympics (chicago coin 1975)": "uJilzS_TiE",
    "olympics (gottlieb 1962)": "P2rQwabQ",
    "olympus (juegos populares 1986)": "AGBZDuIK",
    "on beam (bally 1969)": "S2ms04jxZn",
    "once upon a time in the west (original 2019)": "Z7Dq1bkG",
    "one piece (original 2023)": "yLYQGWU-_T",
    "one punch man pinball (original 2024)": "Z8Q7aLnzTW",
    "op-pop-pop (bally 1969)": "tcG8gJ7nEi",
    "operation highjump (original 2021)": "8Q1HmOY6",
    "operation thunder (gottlieb 1992)": "guuH3VOZ",
    "orbit (gottlieb 1971)": "kgJIXqWv",
    "orbitor 1 (stern 1982)": "GfyAGEv_",
    "ouija (original 2020)": "lFVvEjRb",
    "out of sight (gottlieb 1974)": "oarAmz_b",
    "outer space (gottlieb 1972)": "0l3GAEpk",
    "oxo (williams 1973)": "R0_39L5ec1",
    "ozzy osbourne (original 2025)": "KwF0L8v-Az",
    "pabst can crusher, the (stern 2016)": "wCOhBsJr",
    "pacific rim pinball - table_186 (zen studios 2024)": "janm18KqSc",
    "pacman (original 2021)": "YUZkHTWY",
    "paddock (williams 1969)": "CPCbI05D",
    "pain (original 2024)": "IVy-3Au3I-",
    "pain (original 2025)": "QuGwR9in_v",
    "palace guard (gottlieb 1968)": "d4BrRAAo69",
    "pantera (original 2020)": "ASaZIEvz",
    "panthera (gottlieb 1980)": "-p4ju8Sw",
    "paolo nutini (original 2025)": "HPzFoQvzTJ",
    "paradise (gottlieb 1965)": "oo1p3tMyQw",
    "paragon (bally 1979)": "O4JxplbP",
    "paranormal (zen studios 2013)": "WhTQMTwv",
    "party animal (bally 1987)": "mO_nz3db",
    "party zone, the (bally 1991)": "Gp1e044P",
    "partyland (digital illusions 1992)": "Rf7aNTzLga",
    "pasha (zen studios 2010)": "ps9XF7p9",
    "pat hand (williams 1975)": "ZO7h-OlMcP",
    "paul bunyan (gottlieb 1968)": "Rx7vhUe8",
    "paw patrol, the (original 2020)": "_RIB1Vj4",
    "pdc darts 2023 (original 2023)": "JeAgBsg3GZ",
    "pdc world darts (original 2020)": "OqDGyUpw",
    "peaky blinders (original 2021)": "kVBquxFT",
    "peanuts' snoopy pinball (zen studios 2021)": "HfsyZoQHEX",
    "pennant fever (williams 1984)": "R1GOpnk4",
    "penthouse (pinball dreams 2008)": "jxOvDJqUOh",
    "peppa pig pinball (original 2021)": "bX1bDQbL",
    "pepsi man (original 2019)": "Dd1o_djY",
    "persona 5 demo (original 2023)": "yfiMJ9T2G0",
    "pet shop boys show (original 2025)": "2l2l0pAIlJ",
    "petaco (juegos populares 1984)": "JB_wofcjRH",
    "petaco 2 (juegos populares 1985)": "S4uzNuo80t",
    "phantasm (original 2023)": "YcjItL3EWG",
    "phantogram  (original 2018)": "MwHlQagkf0",
    "phantom haus (williams 1996)": "IOsZXoMuf7",
    "phantom of the opera (data east 1990)": "ftEAiufw",
    "phantom of the paradise (original 2021)": "AOOxT0BxCE",
    "pharaoh (williams 1981)": "iAo3mT2g",
    "pharaoh - dead rise (original 2019)": "oXfqCduB",
    "phase ii (j. esteban 1975)": "iyIWDkZX",
    "phil collins (original 2023)": "m1BSlAyBqI",
    "phish (original 2024)": "H9_s-kv83_",
    "phoenix (williams 1978)": "vzgC4b9eqr",
    "pi rats (original 2024)": "1sMiSSrIXE",
    "pierce the veil (original 2025)": "Do0UN8d9fs",
    "piggy bank blitz (original 2023)": "ws_hvA6-iT",
    "pin city (original 2018)": "Ej8cxtA4",
    "pin-bot (williams 1986)": "A_QiSnbC",
    "pin-up (gottlieb 1975)": "YUGsLrAd",
    "pinball (em) (stern 1977)": "VKU15E4G",
    "pinball (ss) (stern 1977)": "D-zHIJ7GNA",
    "pinball action (tekhan 1985)": "vod4rU2W4A",
    "pinball champ '82 (zaccaria 1982)": "kJkGS991",
    "pinball domes (original 2020)": "A85htGkt",
    "pinball food fight, the (original 2016)": "P0xzZ8lDSV",
    "pinball lizard (game plan 1980)": "4Wef9ZDVGs",
    "pinball magic (capcom 1995)": "C0biqvxH",
    "pinball noir (zen studios 2022)": "zGkmB4Qarg",
    "pinball pool (gottlieb 1979)": "7nbAFTL9Sp",
    "pinball solitaire (original 2025)": "PY8dy8vkkA",
    "pinball squared (gottlieb 1984)": "33PE_NAiWd",
    "pinblob (original 2024)": "JWB3WseUaS",
    "pindar - the lizard king (original 2021)": "xCqtHSTd",
    "pink bubble monsters (original 2025)": "zNGcpsOX1N",
    "pink floyd (original 2022)": "qV3Z3oQ8md",
    "pink floyd - the wall (original 2020)": "JbdHMAYa",
    "pink floyd pinball (original 2020)": "FR-yIPfq",
    "pink panther (gottlieb 1981)": "QvOrGkPi",
    "pink wind turbine (original 2025)": "9lgqYwZQyC",
    "pinky and the brain - gollyzilla (original 2017)": "ukiluTFfOC",
    "pinocchio (original 2025)": "cqvF2s1Tmr",
    "pinup jukebox - the 80s (original 2019)": "JfX7kY3W",
    "pioneer (gottlieb 1976)": "25ZDqJH_",
    "pipeline (gottlieb 1981)": "c8jOgkkHnZ",
    "pirate gold (chicago coin 1969)": "PPREf8_K",
    "pirates life - the revenge of cecil hoggleston (original 2024)": "GeAnEjXczS",
    "pirates of the caribbean (stern 2006)": "cjp2rxwJuT",
    "pistol poker (alvin g. 1993)": "Qg6G4hlP9u",
    "pit stop (williams 1968)": "B3wwb91-",
    "pizza time (original 2020)": "Vzt5icUh",
    "pj masks (original 2020)": "ixRfHhP7",
    "planet hemp (original 2025)": "eKnJYgemXq",
    "planet hemp - pup-pack edition (original 2025)": "AUqgBtql_v",
    "planet of the apes (original 2021)": "29fQECSW",
    "planets (williams 1971)": "IE6m6XCmBN",
    "plants vs. zombies (zen studios 2014)": "ezG8sawq",
    "play ball (gremlin 1972)": "E8RrMSqspO",
    "play pool (gottlieb 1972)": "bzxu8kkuse",
    "playball (gottlieb 1971)": "HISweI4X",
    "playboy (bally 1978)": "IFPGFvgl",
    "playboy (stern 2002)": "cqC1LMDt",
    "playboy - definitive edition (bally 1978)": "QTmGXiYi",
    "playboy 35th anniversary (data east 1989)": "1QxDPaWb33",
    "playmate (original 2020)": "A6Wr4CWT",
    "playmates (gottlieb 1968)": "Dpk6C2UW",
    "poison (original 2025)": "Qxbi6HM3lU",
    "pokemon mystery dungeon (original 2025)": "4nRsY8auSq",
    "pokemon pinball (original 2021)": "Z4v1vgR5",
    "pokemon slots (original 2024)": "Rn94lGsgqG",
    "pokerino (williams 1978)": "PqX1EomCOD",
    "polar explorer (taito do brasil 1983)": "68amNrAE",
    "polar express, the (original 2018)": "E-C4dlxH",
    "pole position (sonic 1987)": "MT3os3Yx",
    "police academy (original 2019)": "IDjVU-HZ",
    "police force (williams 1989)": "iEmHu-2K",
    "police, the (original 2024)": "tYmTfQEf_f",
    "polo (gottlieb 1970)": "00ubLbvS",
    "polo skill (a. pirmischer 1931)": "tv6Y6G8fNi",
    "poltergeist (original 2022)": "eyqGGwPW0C",
    "pompeii (williams 1978)": "hSuRslNi",
    "pool sharks (bally 1990)": "vHd8sNtG",
    "pop-a-card (gottlieb 1972)": "BhcZJ-hu",
    "popeye saves the earth (bally 1994)": "mbCdWbvp",
    "portal (zen studios 2015)": "xK6gQ6YD",
    "poseidon (gottlieb 1978)": "JVzroH1svs",
    "positronic (original 2016)": "n7_bmGAe",
    "post time (williams 1969)": "IP7gMKxR",
    "predator (original 2019)": "-LxhHcra",
    "predator (original 2023)": "GRqg-2y7_G",
    "predator (original 2026)": "Xludx-jcms",
    "predator 2 (original 2019)": "yl250tL5",
    "price is right - 2 for the price of 1, the (original 2023)": "CntYZ64cvl",
    "price is right - 50 year, the (original 2022)": "s411w4WMFA",
    "price is right - five price tags, the (original 2023)": "YaaKQ5JPal",
    "price is right - grand game 2.0, the (original 2023)": "GJWlEc6FXR",
    "price is right - original, the (original 2025)": "fRwAN2bAO6",
    "price is right - plinko, the (original 2022)": "zdDLQR6ysL",
    "primordial quarry (original 2024)": "qOXe9Za7c1",
    "primus (stern 2018)": "OjCGVPqs",
    "princess bride, the (original 2020)": "OjrAJ7J9Ew",
    "prison break (original 2018)": "i4YwDyTr",
    "pro pinball the web (cunning developments 1995)": "oxO-FJst",
    "pro pool (gottlieb 1973)": "jPe5WYf9",
    "pro-football (gottlieb 1973)": "fxorHvOw",
    "prodigy, the (original 2025)": "maelT047Zp",
    "professional pinball - challenger i (professional pinball 1981)": "DZTJZBq8",
    "professional pinball - challenger v (professional pinball 1981)": "YQBf6kAQ",
    "prospector (sonic 1977)": "bwJ-2uaN",
    "pseudo echo (original 2025)": "n53FmUV3Fe",
    "psychedelic (gottlieb 1970)": "rNgZIdV3",
    "pt01 (original 2023)": "LR6ZnYHhWY",
    "pulp fiction (original 2020)": "n4dRBXo3",
    "pulp fiction (original 2023)": "HImsGBv3v1",
    "punch-out (original 2025)": "bpBAQLoWhQ",
    "punchy the clown (alvin g. 1993)": "xERB_g2Df6",
    "punchy the cow (original 2025)": "OIata_9eSO",
    "punk park (original 2025)": "KgmavXm7O7",
    "punk! (gottlieb 1982)": "bAu-4FIe",
    "purge, the (original 2022)": "IIPJeHs83c",
    "puscifer pinball (original 2022)": "e7_0-CogeQ",
    "putin vodka mania (original 2022)": "lAnZOQKhyx",
    "pyramid (gottlieb 1978)": "af6TFO8c",
    "q-bert's quest (gottlieb 1983)": "CfGaTNWc",
    "queen (original 2021)": "CfPb7XL7",
    "queen - the game - hits 1 (original 2021)": "anGjFKsd",
    "queen - the game - hits 2 (original 2021)": "zf2_j2Rg62",
    "queen - the show must go on (original 2022)": "gblsaBcNWU",
    "queen of hearts (gottlieb 1952)": "h8j9OEOe",
    "queens of the stone age (original 2021)": "lH_3BVH97M",
    "quick draw (gottlieb 1975)": "iE2ASzDk",
    "quick! silver! - a rush for riches (original 2025)": "DsuS1orGmX",
    "quicksilver (stern 1980)": "beHzN91Z",
    "quijote (juegos populares 1987)": "yYgpJ6Oo",
    "r.e.m (original 2025)": "4jFtweNwf1",
    "r2d2 (original 2019)": "frxudUx297",
    "rack 'em up! (gottlieb 1983)": "RucJdJIu",
    "rack-a-ball (gottlieb 1962)": "NCAZJBSU",
    "radical! (bally 1990)": "mwJTQUhXzS",
    "radical! (prototype) (bally 1990)": "YE4sbK8gxP",
    "radiohead (original 2025)": "Z3HBNWABpF",
    "rage against the machine (original 2025)": "9uvEURqaHp",
    "raid, the (playmatic 1984)": "pnOysL1v",
    "rails (original 2025)": "5PBygI9b3e",
    "rain (original 2019)": "SOwPOXBNCO",
    "rainbow (gottlieb 1956)": "6CPdKAN0",
    "rainbow (original 2025)": "2x2qlw8NaA",
    "raiponce (original 2021)": "fhEMcE2A",
    "rally (taito do brasil 1980)": "86-K4SpS",
    "rambo (original 2019)": "QOd5ivcVbU",
    "rambo first blood part ii (original 2020)": "cvQVNDFB",
    "rammstein - fire & power (original 2023)": "hbIv1SC0_1",
    "ramones (original 2021)": "TC8_qMKn",
    "rancho (gottlieb 1966)": "7Hc_RTIB",
    "rancho (williams 1976)": "NbhyViUJjE",
    "rapid fire (bally 1982)": "-5tVwxd5",
    "rat fink (original 2016)": "0aKEy6kg",
    "rat fink (original 2025)": "nya-dnobhA",
    "rat race (williams 1983)": "Kz76AyCtlx",
    "rattlecan (original 2025)": "baoHL_uGaL",
    "raven (gottlieb 1986)": "kOKeRXRV",
    "rawhide (stern 1977)": "gMKgsuFkNZ",
    "raygun runner (original 2024)": "ThUwLJj7KJ",
    "re-animator (original 2022)": "VOvPOpOyI7",
    "re-animator - trilogy edition (original 2022)": "72c4654zJO",
    "ready jet go (original 2022)": "fIOn86PHUj",
    "ready player one (original 2024)": "JGn39ZBytl",
    "ready...aim...fire! (gottlieb 1983)": "jmeryXP9Wh",
    "red & ted's road show (williams 1994)": "SzGJ9G2v",
    "red baron (chicago coin 1975)": "VYvZsSYwic",
    "red electric rhapsody (original 2025)": "B6AxG18lHX",
    "red hot chili peppers (original 2021)": "WFhFVzmob7",
    "red hot pinball (original 2021)": "wo5G3F3r",
    "red sonja (original 2019)": "pYIIvdg_",
    "ren & stimpy space madness (original 2024)": "FCx6-tAH4c",
    "rescue 911 (gottlieb 1994)": "mZT99t-q",
    "reserve (williams 1961)": "GU-KD_mkWW",
    "resident alien (original 2024)": "6UnDGf3Axz",
    "resident evil (original 2022)": "BCQf5qj_e2",
    "resident evil vii (original 2019)": "q5OB_eYM",
    "retro king (original 2004)": "Ll3n1dG0va",
    "retro zombie adventure land (original 2016)": "0pVhzZWa",
    "retroflair (original 2012)": "NquQKxYfqP",
    "retroflair - bam edition (original 2012)": "LPlspaI_aS",
    "return of the living dead (original 2021)": "v0wdgqZh",
    "return of the living dead, the (original 2020)": "sByXH45WeO",
    "return of the living dead, the (original 2024)": "0vUhQnzUpg",
    "rey de diamantes (petaco 1967)": "1Sawx7aL",
    "riccione (original 2024)": "uE3Jxn_-tp",
    "rick and morty (original 2019)": "VH9Zs49K",
    "rick and morty (original 2023)": "WSE0lE1FdO",
    "rider's surf (jocmatic 1986)": "Ca2kxueo",
    "rigel 7 (original 2023)": "oCYe4QYYzc",
    "rio travel (original 2025)": "pCjG4Z_Mbw",
    "ripley's believe it or not! (stern 2004)": "UOa7DIIA",
    "rise against (original 2025)": "idST46Zk60",
    "riverboat gambler (williams 1990)": "5IuXcZ-p",
    "ro go (bally 1974)": "3yX6x-fc",
    "road blues (original 2020)": "tuFlR8GX",
    "road kings (williams 1986)": "KqYFefRN",
    "road race (gottlieb 1969)": "6cgLKVFa",
    "road runner (atari 1979)": "k2rhZAx-",
    "road runner (original 2023)": "eeFWOFAlDo",
    "road train (original 2024)": "WrrurDqHVe",
    "rob zombie's spookshow international (original 2017)": "DqHtDnz7",
    "robo-war (gottlieb 1988)": "an0Nk7Tt",
    "robocop (data east 1989)": "cPI6Ww-1",
    "robocop (original 2013)": "0LQNpWah1c",
    "robocop - dead or alive (original 2013)": "0p-f5gJMVb",
    "robocop - ultimate (original 2013)": "LsP753HULI",
    "robocop - ultimate pro (original 2013)": "iwzoHeLUJr",
    "robocop - ultra (original 2013)": "WVCEpsPArl",
    "robocop 3 (original 2018)": "NU_gWBx4",
    "robot (zaccaria 1985)": "iDx4vLUL",
    "robotech: the macross saga (original 2025)": "upzAgpGn1l",
    "robots invasion (original 2024)": "pCWcArFh3-",
    "rock (gottlieb 1985)": "RJitvevs",
    "rock 2500 (playmatic 1985)": "Y5ltBuUCm1",
    "rock and roll (original 2020)": "TXFRw-EW",
    "rock encore (gottlieb 1986)": "-ZAd39t6",
    "rock in rio (original 2025)": "zl5cLK_Hh2",
    "rock music (original 2025)": "VkD2LCYYm8",
    "rock n roll diner (original 2020)": "xaS9lfl4",
    "rock star (gottlieb 1978)": "iJ_MSUEl",
    "rock sugar (original 2021)": "MsYlnwXXQZ",
    "rockabilly (original 2022)": "fOoTVqMs1F",
    "rocket iii (bally 1967)": "ZkyRkOse",
    "rocket ship (gottlieb 1958)": "-Clx8k5-ro",
    "rockmakers (bally 1968)": "4ZdLiUx8",
    "rocky (gottlieb 1982)": "gq5ooxZW",
    "rocky (original 2020)": "iRB6cfzU",
    "rocky balboa (original 2025)": "Yxvms1ashg",
    "rocky horror picture show, the (original 2022)": "wU3lxCGan5",
    "rocky tko (original 2021)": "gBI4H8FN",
    "rocky vs. balutito (original 2021)": "_ewOT_Rn",
    "rod stewart (original 2023)": "Hg5-xVT4c9",
    "roller coaster (gottlieb 1971)": "t6-exM_e",
    "roller derby (bally 1960)": "T0m35TYs",
    "roller disco (gottlieb 1980)": "vfihCIiN",
    "rollercoaster tycoon (stern 2002)": "1oC_SXeO",
    "rollergames (williams 1990)": "TLmSQkGS",
    "rollet (barok co 1931)": "il21IVzgbh",
    "rolling stones (bally 1980)": "CqL5ibkl",
    "rolling stones - b&w edition (bally 1980)": "tZr2jk-Sb0",
    "rolling stones, the (stern 2011)": "19x8IM6g",
    "roman victory (taito do brasil 1977)": "9EMjy3Uo",
    "rome (zen studios 2010)": "nyYS7gan",
    "route 66 (original 2024)": "HTnqgvTEso",
    "roy orbison (original 2020)": "mVHk_oSo",
    "royal blood (original 2021)": "hzkLheAz4z",
    "royal flush (gottlieb 1976)": "2aloo6Mw",
    "royal flush deluxe (gottlieb 1983)": "oSWxMXGG",
    "royal guard (gottlieb 1968)": "8fjJvL8-",
    "royal pair (gottlieb 1974)": "Ej_pHo7_",
    "royal pair - 2 pop bumper edition (gottlieb 1974)": "ixJAt2Q3",
    "running horse (inder 1976)": "cYua0PGDpT",
    "rush 2112 (original 2020)": "7kd-Lnuu",
    "rush le tribute (original 2025)": "WLDTmruQ5a",
    "ryoko (original 2003)": "_1UBIt6zLP",
    "safe australia (original 2024)": "qd6wWc1yEM",
    "safe cracker (bally 1996)": "_ELCbKmu",
    "saint seiya - i cavalieri dello zodiaco - cabinet edition (original 2022)": "Ad18zRvauU",
    "saint seiya - i cavalieri dello zodiaco - desktop edition (original 2022)": "nYN685W_fi",
    "saloon (taito do brasil 1978)": "uobLjBMgRF",
    "salsa (original 2021)": "yI6HNS4E",
    "samba (ltd do brasil 1976)": "H94bTMWLSC",
    "san francisco (williams 1964)": "7qDFGMv8",
    "san ku kai (original 2022)": "KK8QAbkQS1",
    "sand reapers: assasins of the desert, the - bam edition (original 2023)": "moMc3qJIXl",
    "sandra - the 80's pop star (original 2025)": "H2lMUmcAk7",
    "sands of the aton (original 2023)": "csAFDthAC1",
    "santana (original 2025)": "VKdQj9ertn",
    "satin doll (williams 1975)": "IHYtsDV-",
    "saturday night fever (original 2025)": "V2bpxglnt3",
    "saucer secrets (original 2026)": "TQaYQWORIG",
    "saucerer (original 2025)": "_cmOUmuPmV",
    "saving wallden (original 2024)": "JK7gTe3ZjY",
    "saw (original 2022)": "2fABdKt-cp",
    "saxon (original 2025)": "8gyopusyad",
    "scared stiff (bally 1996)": "Jhr0Ueap",
    "scarface - balls and power (original 2020)": "zUt0yeaM",
    "schuss (rally 1968)": "gcL8pb0D",
    "scooby-doo! (original 2022)": "7PO2uGwNvs",
    "scooby-doo! and kiss - rock 'n roll mystery (original 2015)": "bzq5tKcC",
    "scorpion (williams 1980)": "ZoD3I_Ak",
    "scorpions (original 2024)": "gHe-5Dyww6",
    "scott pilgrim vs. the world (original 2021)": "4tIs87Yp0A",
    "scram! (hutchison 1932)": "Ifcb-iU0mH",
    "scramble (tecnoplay 1987)": "mX7ujx4FAg",
    "scream (original 2025)": "3ipKG7yTdU",
    "scrooged (original 2019)": "ZZrbW56L",
    "scuba (gottlieb 1970)": "c-sHqaNX",
    "sea jockeys (williams 1951)": "H3jJOido",
    "sea ray (bally 1971)": "nLh3vkkJ",
    "seawitch (stern 1980)": "THm3ohiJ",
    "secret agent (original 2024)": "IFaNlY_dl5",
    "secret service (data east 1988)": "sgEzHEF2",
    "secrets of the deep (zen studios 2010)": "BUeaco8P",
    "seinfeld (original 2021)": "9nPAZ3oc",
    "senna - prototype edition (culik pinball 2020)": "ssOBaYceiU",
    "sepultura (original 2025)": "v8OltURoa2",
    "serious sam ii (original 2019)": "GUCFbJI0pf",
    "serious sam pinball (original 2017)": "ls-dMMhYLY",
    "sesame street (original 2021)": "I6Dwe16_",
    "seven winner (inder 1973)": "7hF0VNolwC",
    "sexy girl (arkon 1980)": "R80qhgsz",
    "sexy girl - nude edition (arkon 1980)": "meEhjXIJWp",
    "shadow, the (bally 1994)": "yfPwDiVATe",
    "shaman (zen studios 2013)": "u-P91z_4",
    "shamrock (inder 1977)": "1n_6a_RT1d",
    "shangri-la (williams 1967)": "WYxu8VZW",
    "shaq attaq (gottlieb 1995)": "3doTkFIY",
    "shark (taito do brasil 1982)": "aHfn8k3U",
    "sharkey's shootout (stern 2000)": "fLqFto79fb",
    "sharks (original 2023)": "TdjiUtaKME",
    "sharp shooter ii (game plan 1983)": "3pGH_l-p",
    "sharpshooter (bally 1961)": "eYtU9NK0",
    "sharpshooter (game plan 1979)": "Qi9Ce5ou",
    "sheriff (gottlieb 1971)": "QsDg_6Nb",
    "sherokee (rowamet 1978)": "mvO7iGKsB-",
    "shining, the (original 2022)": "BKf3ny5x",
    "shining, the (original 2025)": "VkNANt3br1",
    "ship ahoy (gottlieb 1976)": "2cEM-2Ai",
    "ship-mates (gottlieb 1964)": "dD3kFUpc",
    "shock (taito do brasil 1979)": "YJhFns1cxE",
    "shooting star (junior) (daval 1934)": "TJfEmlHSfU",
    "shooting the rapids (zaccaria 1979)": "WuXzpIuBF-",
    "short circuit (original 2024)": "qsiPZiXr6A",
    "shovel knight (original 2017)": "nydw3zn0Fu",
    "shrek (stern 2008)": "7TNC17gj",
    "shrek the halls (original 2019)": "l1uUNRkL",
    "shuffle inn (williams 1989)": "YqD-KrqK",
    "silent night deadly night (original 2016)": "HXzcvwZE",
    "silver bullet (original 2025)": "G-_HQ6TVyO",
    "silver cup (genco 1933)": "T9fMfEqxuD",
    "silver line (bill port 1970)": "nt_tzALK",
    "silver slugger (gottlieb 1990)": "mro2e1kN",
    "silverball mania (bally 1980)": "JMfE2-eO",
    "simple minds (original 2024)": "mgY-uvCd0a",
    "simpsons christmas, the (original 2019)": "jm-8frOP",
    "simpsons kooky carnival, the (stern 2006)": "enepoIisSo",
    "simpsons pinball party, the (stern 2003)": "giw7cSzk",
    "simpsons treehouse of horror, the (original 2020)": "upTwChms",
    "simpsons treehouse of horror, the - starlion edition (original 2020)": "iMTt4PXh6x",
    "simpsons, the (data east 1990)": "lpGzyetS",
    "sin city (original 2022)": "ovQSilyb7r",
    "sin city - pup-pack edition (original 2022)": "AjCXD21F__",
    "sinbad (gottlieb 1978)": "OMK09HUn",
    "sing along (gottlieb 1967)": "1Ib9PsvH",
    "sir lancelot (peyper 1994)": "y5_RGoq_",
    "sittin' pretty (gottlieb 1958)": "OqImqNXjYO",
    "six million dollar man, the (bally 1978)": "tBofel5G",
    "skate and destroy (original 2019)": "DTp_TBsK",
    "skateball (bally 1980)": "rH0oXSnv",
    "skateboard (inder 1980)": "PVEIN8Zo0R",
    "skipper (gottlieb 1969)": "3yMybVr7",
    "skittles (original 2019)": "cD6eCV46",
    "sky jump (gottlieb 1974)": "-OrSUeyL",
    "sky kings (bally 1974)": "7xMfVlTYZk",
    "sky pirates - treasures of the clouds (zen studios 2022)": "hk5A-USz_p",
    "sky ride (genco 1933)": "xc1biJcadC",
    "sky-line (gottlieb 1965)": "3qgVz8WEka",
    "skylab (williams 1974)": "hkwrlA_klR",
    "skyrocket (bally 1971)": "6L4NUXUF",
    "skyscraper (bally 1934)": "fzOMz7rlhz",
    "skyway (williams 1954)": "qo-m1I-F",
    "slash (original 2025)": "4RtHlQKWi0",
    "slash's snakepit it's five o'clock somewhere (original 2025)": "juayUwEg_b",
    "slayer (original 2022)": "0ZPsV_8g3z",
    "sleic pin-ball (sleic 1994)": "rdpCXsOSzc",
    "sleic pin-ball - cabinet edition (sleic 1994)": "qcCAGKwxo2",
    "sleic pin-ball - desktop edition (sleic 1994)": "oIJS-Evo3r",
    "slick chick (gottlieb 1963)": "dBl0gI0iuy",
    "slipknot (original 2021)": "OOXtK7R0",
    "smart set (williams 1969)": "cmsm8qnOu5",
    "smokey and the bandit (original 2021)": "qmK7H4d-",
    "smooth hot ride 3 - from natchez to mike vegas (original 2023)": "RYqKc5RyUs",
    "snake dmd (original 2021)": "_BIP9kOqax",
    "snake machine (taito do brasil 1982)": "DICfGmxH",
    "snooker (gottlieb 1985)": "ZXqz0hRPqr",
    "snorks (original 2024)": "otOCScBZom",
    "snow derby (gottlieb 1970)": "EZjLgYAe",
    "snow queen (gottlieb 1970)": "7RrRifxZ",
    "snowman, the (original 2019)": "eQi7mpqF",
    "soccer (gottlieb 1975)": "vOi-OYLx",
    "soccer (williams 1964)": "_IB_QPR_",
    "soccer kings (zaccaria 1982)": "GOlRXT3v",
    "solar city (gottlieb 1977)": "QgtWDZao",
    "solar fire (williams 1981)": "DuR0tlfn",
    "solar ride (electromatic 1982)": "uTx-mtgCZx",
    "solar ride (gottlieb 1979)": "7DJIwVvf",
    "solar ride (rowamet 1982)": "y-UtawbtXG",
    "solar sailor (original 2016)": "eHMX8iTr",
    "solar wars (sonic 1986)": "QO4CFBHKDR",
    "solids n stripes (williams 1971)": "I4ESJ9pD",
    "solitaire (gottlieb 1967)": "NCIZFoFK",
    "son of zeus (zen studios 2017)": "2A-nOl5G",
    "sonic pinball mania (original 2022)": "Cc-r8YrYBI",
    "sonic the hedgehog (original 2005)": "vxmVY4bPId",
    "sonic the hedgehog 2 (original 2019)": "17fCJAS8a2",
    "sonic the hedgehog spinball (original 2020)": "2RURHgre",
    "sons of anarchy (original 2019)": "lMA-psYP",
    "sopranos, the (stern 2005)": "NDgcI5da",
    "sorcerer (williams 1985)": "sv0BJWOy",
    "sorcerer's lair (zen studios 2011)": "QeZVKxt-",
    "soul reaver (original 2019)": "vVFmvuZ5",
    "sound stage (chicago coin 1976)": "D4hP8yYeWV",
    "south park (sega 1999)": "lEHkbgwl",
    "south park - butters' very own pinball game (zen studios 2014)": "83geIcSX",
    "south park - super sweet pinball (zen studios 2014)": "EnlCopjT",
    "south park pinball (original 2021)": "Zjjgfzpi",
    "south park xmas pinball (original 2020)": "MzOMfLNH",
    "southern belle (gottlieb 1955)": "xQoOwOal_3",
    "soylent green (original 2023)": "eo5Fv0P1la",
    "space 1999 (original 2025)": "sWGEESjWza",
    "space cadet (microsoft 1995)": "I5MBusrpb2",
    "space dragon princess (original 2023)": "AXNoViLw_y",
    "space gambler (playmatic 1978)": "YFv5J58XDZ",
    "space invaders (bally 1980)": "zmo54Fjv",
    "space jam (sega 1996)": "9pTQh92P",
    "space mission (williams 1976)": "J1N-CEpH",
    "space oddity (original 2022)": "_-1GvxdS1k",
    "space odyssey (williams 1976)": "4so9iQqQ",
    "space orbit (gottlieb 1972)": "H67wY58d",
    "space patrol (taito do brasil 1978)": "lSoF_7UR",
    "space platform - murray leinster (original 2024)": "gBT8KXUSBa",
    "space poker (ltd do brasil 1982)": "V96BA558zs",
    "space race (recel 1977)": "9ZguRM79xu",
    "space rider (geiger 1980)": "iMGNwZh0as",
    "space riders (atari 1978)": "gcoCsFkPXu",
    "space romance (original 2024)": "mRW1CUmoNB",
    "space sheriff gavan (x-or) (original 2021)": "BbjG5blF",
    "space shuttle (taito do brasil 1985)": "y3g4BRT5RI",
    "space shuttle (williams 1984)": "K3CP9475",
    "space station (williams 1987)": "oXe5YRSu",
    "space time (bally 1972)": "p85JNKSj",
    "space train (mac 1987)": "-FCEF2_X",
    "space tug - murray leinster (original 2024)": "hniTbwq8RP",
    "space walk (gottlieb 1979)": "4IB26PhN",
    "spaceramp (original 2020)": "eiScoWaL",
    "spanish eyes (williams 1972)": "HheC-5MX",
    "spark plugs (williams 1951)": "9l95xML9",
    "spawn (original 2023)": "W5T0W9mjYA",
    "speakeasy (bally 1982)": "UHfC_vUF",
    "speakeasy (playmatic 1977)": "LNHqoz_qVJ",
    "speakeasy 4 (bally 1982)": "U5CiF7iY",
    "special force (bally 1986)": "IeeUtXq3bF",
    "species (original 2023)": "OtuyAUt6DI",
    "spectrum (bally 1982)": "QCC-HH5X",
    "speed devils (digital illusions 1992)": "MHLrBppkrJ",
    "speed racer (original 2018)": "E6GJMdv5",
    "speed test (taito do brasil 1982)": "iqVOU959",
    "spellcast machine, the (original 2024)": "L7sjUNn9tF",
    "spider-man (black suited) (stern 2007)": "CoBrmsXIfg",
    "spider-man (stern 2007)": "Vj2D5bud",
    "spider-man (vault edition) (stern 2016)": "XvvLiExx",
    "spider-man (vault edition) - classic edition (stern 2016)": "zO-dubmF",
    "spider-man (zen studios 2010)": "9w367dKx",
    "spider-man - classic edition (stern 2007)": "yB8ekpyv",
    "spin out (gottlieb 1975)": "iswwFs2L",
    "spin wheel (gottlieb 1968)": "HDEvBkgo",
    "spin-a-card (gottlieb 1969)": "ZIhsuTN0",
    "spinning wheel (automaticos 1970)": "AIUxc_rwh7",
    "spirit (gottlieb 1982)": "tWyyskFb",
    "spirit of 76 (gottlieb 1975)": "ouy6bbdn",
    "splatter blast studio (original 2024)": "Dki4seduEM",
    "splatterhouse (original 2023)": "YFZxzQg7By",
    "split second (stern 1981)": "4Ne8jb8t_k",
    "spongebob (original 2020)": "7e4bBYB_",
    "spongebob squarepants (original 2008)": "KNbv2BfMIy",
    "spongebob squarepants pinball adventure - bronze edition (original 2023)": "3M7JQkzyJI",
    "spongebob squarepants pinball adventure - gold edition (original 2023)": "lg4zCwL2e4",
    "spongebob squarepants pinball adventure - platinum edition (original 2023)": "IEIGK9tK_-",
    "spongebob's bikini bottom pinball (original 2021)": "R3POPsVG",
    "spooky wednesday (original 2024)": "tYqg-vDGJT",
    "spot a card (gottlieb 1960)": "nyQBB5h1",
    "spot bowler (gottlieb 1950)": "7OoR0vBx3a",
    "spot pool (gottlieb 1976)": "UfmLWJqF",
    "spring break (gottlieb 1987)": "OdtAcY-X",
    "spy hunter (bally 1984)": "APSWZfC4",
    "squid game (original 2024)": "AfVvwS1biA",
    "stabby the unicorn (original 2026)": "6yX_YzYhHX",
    "stage door canteen (gottlieb 1945)": "yUQGbN9JdJ",
    "stampede (stern 1977)": "GRhY1ouMsK",
    "star action (williams 1973)": "LKZPmyoIzI",
    "star fire (playmatic 1985)": "ty8be241",
    "star gazer (stern 1980)": "hF1A9bDS",
    "star god (zaccaria 1980)": "nR8zWpLV",
    "star knights (original 2025)": "xyHb2kacjq",
    "star light (williams 1984)": "nbRf33AM",
    "star mission (durham 1977)": "FH3ktW09",
    "star pool (williams 1974)": "9UurYiKUHQ",
    "star race (gottlieb 1980)": "RdMYhqcO",
    "star ship (bally 1976)": "DGcSLI_k5e",
    "star tours (original 2024)": "iOek5Kd6d1",
    "star trek (bally 1979)": "52WOCBKf",
    "star trek (data east 1991)": "ya2sCTWN",
    "star trek (enterprise limited edition) (stern 2013)": "RGg0YRXJCb",
    "star trek (gottlieb 1971)": "6ZOPcrFP",
    "star trek - mirror universe edition (bally 1979)": "vFvFZ_Zz",
    "star trek - spock tribute (original 2022)": "237KyUUOp8",
    "star trek - the mirror universe (original 2014)": "wgtvgad46y",
    "star trek - the next generation (williams 1993)": "NszdbCkk",
    "star trek - voyager - seven of nine (borg edition) (original 2022)": "09WQOqShiT",
    "star trip (game plan 1979)": "1OnHb-hEZ8",
    "star wars (data east 1992)": "5mo99FmX",
    "star wars (original 2016)": "8J7Vaw8991",
    "star wars (original 2019)": "OcD2pQ06",
    "star wars (original 2023)": "pz1iWcH1mb",
    "star wars (original 2025)": "fqUNoSi3hg",
    "star wars (sonic 1987)": "fCERzTdn",
    "star wars - bounty hunter (original 2021)": "Ba357hhX",
    "star wars - episode i (original 2023)": "8cCo6w5hRT",
    "star wars - lite edition (original 2023)": "OR7RqLjDI0",
    "star wars - the bad batch (original 2022)": "0DHpnJGRkX",
    "star wars - the empire strikes back (hankin 1980)": "-LTc5vxS",
    "star wars death star assault (original 2011)": "ubrypO8rNY",
    "star wars death star assault - galactic edition (original 2011)": "w-0IPdiVQA",
    "star wars death star assault - ultimate pro (original 2011)": "bD2CM_AjOX",
    "star wars death star assault - ultimate pro - epic space battles (original 2011)": "Jau7Ccbvo7",
    "star wars pinball - ahch-to island (zen studios 2018)": "dQ8HmLvp",
    "star wars pinball - battle of mimban war (zen studios 2018)": "mccky9r4",
    "star wars pinball - boba fett (zen studios 2013)": "ig2_cQCu",
    "star wars pinball - calrissian chronicles (zen studios 2018)": "qvwCx8fC",
    "star wars pinball - classic collectibles (zen studios 2022)": "A7cOqRcg_A",
    "star wars pinball - darth vader (zen studios 2013)": "shc2Z3NK",
    "star wars pinball - droids (zen studios 2014)": "pwY7n-AE",
    "star wars pinball - episode iv a new hope (zen studios 2014)": "lN2AjWlp",
    "star wars pinball - episode v the empire strikes back (zen studios 2013)": "opQYaNGx",
    "star wars pinball - episode vi return of the jedi (zen studios 2013)": "JYowoi6k",
    "star wars pinball - han solo (zen studios 2014)": "M7mghvqe",
    "star wars pinball - masters of the force (zen studios 2014)": "XK-w7HiM",
    "star wars pinball - might of the first order (zen studios 2016)": "IE5-UYeb",
    "star wars pinball - rebels (zen studios 2015)": "2cxymrtz",
    "star wars pinball - rogue one (zen studios 2017)": "GU-3QlsS",
    "star wars pinball - solo (zen studios 2018)": "L1DXVTPm",
    "star wars pinball - starfighter assault (zen studios 2013)": "dUMRlwd2",
    "star wars pinball - the clone wars (zen studios 2013)": "7tmIfdAp",
    "star wars pinball - the force awakens (zen studios 2016)": "ZbV-l6_K",
    "star wars pinball - the last jedi (zen studios 2018)": "mofyWMuu",
    "star wars pinball - the mandalorian (zen studios 2022)": "jhhy9WHGYe",
    "star wars redux (original 2021)": "ZDwZwsz6pz",
    "star wars trilogy special edition (sega 1997)": "mJH39ywYDx",
    "star-jet (bally 1963)": "ktnXkO0X",
    "stardust (williams 1971)": "-paFBOWzxk",
    "stargate (gottlieb 1995)": "GyjGzeETP9",
    "stars (stern 1978)": "hc71lT3B",
    "starship troopers (sega 1997)": "HprFaAxj",
    "starship troopers - vpn edition (sega 1997)": "HWwR4R_E",
    "steel panther 1987 (original 2025)": "NzMMnZiUBJ",
    "steel wheel (digital illusions 1992)": "koWAEUR2a7",
    "stellar airship (geiger 1979)": "h6qPdKIE",
    "stellar wars (williams 1979)": "5_DerfzgwJ",
    "stephen king's children of the corn (original 2019)": "LVWo6aCU",
    "stephen king's pet sematary (original 2019)": "nnDQCFrX",
    "stephen king's sleepwalkers (original 2019)": "KOH3-yA9",
    "stephen king's the running man (original 2019)": "dgJ7M0nv",
    "steve miller band (original 2025)": "Xt6Jvkkr3r",
    "stick figure (original 2020)": "7a3m4SGu",
    "still crazy (williams 1984)": "WiRoKtTQ",
    "stingray (stern 1977)": "taGHdxf8",
    "stock car (gottlieb 1970)": "At0tXp1X",
    "stones'n'bones (digital illusions 1992)": "MqvmiJuj5W",
    "straight flush (williams 1970)": "MoF9H77Z",
    "strange science (bally 1986)": "3vRQsuk8",
    "strange world (gottlieb 1978)": "34pseWTK",
    "stranger things (original 2017)": "TfT2LAvBn-",
    "stranger things - stranger edition (original 2018)": "HPPhsjl-",
    "stranger things - stranger edition - season 4 edition (original 2018)": "N9oM8Qqiq_",
    "stranger things - stranger edition - season 4 premium edition (original 2018)": "VSk77qUEdw",
    "strato-flite (williams 1974)": "gKw9MaBE",
    "stray cats (original 2025)": "7EELUHfEUv",
    "stray cats - pup-pack edition (original 2025)": "Fr4QTth9yE",
    "street fighter ii (gottlieb 1993)": "j40aV2Ik",
    "streets of rage (original 2018)": "9UeRLofk",
    "strike (zaccaria 1978)": "ZM6EWQ4w6S",
    "strike master (williams 1991)": "T1cvZTYK",
    "strike zone (williams 1984)": "nUCBLsD2",
    "striker (gottlieb 1982)": "ih6RcOgu",
    "striker xtreme (stern 2000)": "gAyykXfA",
    "strikes and spares (bally 1978)": "Uu-v4WKqXy",
    "strikes n' spares (gottlieb 1995)": "X8zmv4hO",
    "strip joker poker (gottlieb 1978)": "wDdUcP3JNb",
    "stripping funny (inder 1974)": "EtJj5rm0",
    "struggle buggies (williams 1953)": "VaiSLQJ76q",
    "student prince (williams 1968)": "odPqyHG8",
    "sublime (original 2025)": "PDg8LiNOut",
    "sultan (taito do brasil 1979)": "Kh58Qu6b",
    "summer time (williams 1972)": "ieqbnuxt7O",
    "sunset riders pinball (original 2022)": "7wvhScu57q",
    "super bowl (bell games 1984)": "T2lyN3Hd",
    "super jumbo (gottlieb 1954)": "-rwuk9dd9N",
    "super league football (zen studios 2014)": "Su7J1NDK",
    "super league football - table_36 (zen studios 2014)": "b0P-oMbHzs",
    "super mario bros. (gottlieb 1992)": "PEgXJO2X",
    "super mario bros. mushroom world (gottlieb 1992)": "tdkda5uX",
    "super mario galaxy pinball (original 2020)": "5-urGT8M",
    "super nova (game plan 1980)": "fthyCqxH",
    "super orbit (gottlieb 1983)": "idvtS0h253",
    "super score (gottlieb 1967)": "azUEEHYB_O",
    "super soccer (gottlieb 1975)": "9pekIf3U",
    "super spin (gottlieb 1977)": "T7cLrlne",
    "super star (chicago coin 1975)": "4PXfG0qicc",
    "super star (williams 1972)": "6edsQ-uTNu",
    "super straight (sonic 1977)": "v9bavPiO",
    "super-flite (williams 1974)": "RmoKo3o5",
    "superman (atari 1979)": "1hsp9ByZ",
    "superman (original 2009)": "PTf5o6vbZ5",
    "superman - the animated series (original 2020)": "U84YYKoS",
    "superman - the animated series - pup-pack edition (original 2020)": "PSGPiAErXZ",
    "superman and the justice league (original 2024)": "eb0Mem1PSt",
    "supersonic (bally 1979)": "bKF8ERGrfV",
    "supertramp show (original 2025)": "5aBOqLG0pK",
    "supreme dance mix (original 2025)": "IKJ8sM897T",
    "sure shot (gottlieb 1976)": "Oe0O5fhw",
    "sure shot (taito do brasil 1981)": "-96bhaFV",
    "surf 'n safari (gottlieb 1991)": "bkU7TpsKXy",
    "surf champ (gottlieb 1976)": "6TfKzoecHr",
    "surf side (gottlieb 1967)": "2HuMAqxs",
    "surfer (gottlieb 1976)": "Sv32pMmEBA",
    "swamp thing (original 2024)": "LaF07nySIy",
    "swamp thing - bayou edition (original 2024)": "LpcG45DiQ9",
    "swashbuckler (recel 1979)": "9810VFmK",
    "sweet hearts (gottlieb 1963)": "1EsABkMf",
    "sweet sioux (gottlieb 1959)": "ARdJgsGeZL",
    "swing-along (gottlieb 1963)": "WimBSiuZ",
    "swinger (williams 1972)": "l58ILF9u",
    "sword dancer (original 2023)": "bIqu0GQmw9",
    "sword of fury, the (original 2019)": "tcJh-0oA",
    "swords of fury (williams 1988)": "TL_HtlKe",
    "t and c surf (original 2023)": "n5fBhDN15w",
    "t-rex (original 2019)": "wGqNj6LkzH",
    "t.k.o. (gottlieb 1979)": "HGGJrZz1",
    "table starter (original 2019)": "BktBghy8",
    "table with the least comprehensible theme ever, the (original 2018)": "AIqi6fZi",
    "tag-team pinball (gottlieb 1985)": "oHoYxBST",
    "tales from the crypt (data east 1993)": "9zTrafQ4",
    "tales of the arabian nights (williams 1996)": "CCkRwbGS",
    "talk talk (original 2025)": "BQuQNHbsr0",
    "talking word clock (original 2020)": "Z7SZUhpJ",
    "tam-tam (playmatic 1975)": "EuidlPB4",
    "tango & cash (original 2019)": "nUeNfKKa",
    "target alpha (gottlieb 1976)": "3DEjxdXt",
    "target pool (gottlieb 1969)": "BTWBtDfj",
    "target practice (original 2024)": "UAPmwe2_p4",
    "tarzan - lex barker tribute edition (original 2023)": "Wue6-obcnj",
    "taxi (williams 1988)": "D3o3q9sKP1",
    "taxi - lola edition (williams 1988)": "0UJab4nJZ7",
    "taxi driver (original 2024)": "Byi2sXGnOd",
    "taylor swift (original 2021)": "fmwdVZWI",
    "taylor swift eras tour pinball (original 2024)": "ieNtKIuvLm",
    "teacher's pet (williams 1965)": "qFovUW8d",
    "team america world police (original 2017)": "5f94OWec",
    "team one (gottlieb 1977)": "IrsjgApE",
    "tee'd off (gottlieb 1993)": "4RzJ36EA",
    "teenage mutant ninja turtles (data east 1991)": "1yPlOLBC",
    "teenage mutant ninja turtles (stern / data east remix) (original 2024)": "eiKQUmT6oX",
    "teenage mutant ninja turtles - pup-pack edition (data east 1991)": "w4Rer0Zep8",
    "teenage mutant ninja turtles remix (original 2021)": "sDjVbLN9mv",
    "ten stars (zaccaria 1976)": "nyAe8VMx",
    "ten strike classic (benchmark games 2003)": "9r2WBsJC",
    "tenacious d (original 2025)": "tmujAZ8grT",
    "terminator 2 - judgment day (williams 1991)": "IdH1eh5Owo",
    "terminator 2 - judgment day - chrome edition (williams 1991)": "c6ib8flL",
    "terminator 2 - judgment day - skynet - ultimate edition (williams 1991)": "dRPU97tG_2",
    "terminator 2 - judgment day - skynet edition (williams 1991)": "uJQ5ckf8h8",
    "terminator 3 - rise of the machines (stern 2003)": "7x9T2ymv",
    "terminator genisys (original 2019)": "oh91Unhnfn",
    "terminator salvation (original 2018)": "qt4NQBef",
    "terminator, the (original 2019)": "Psud_ztH",
    "terrific lake (sport matic 1987)": "DHnISKBlCP",
    "terrifier (original 2024)": "7FAR271a84",
    "terrifier - streamer friendly edition (original 2024)": "j7SOYtF5FT",
    "tesla (zen studios 2013)": "Ndr5Vh8K",
    "test pilots (original 2024)": "UVnm6uGXWc",
    "texas chainsaw massacre, the (original 2020)": "pZvJdYH6",
    "texas poker (original 2019)": "WfYeL1y6",
    "texas ranger (gottlieb 1972)": "FWdZu8xE",
    "theatre of houdini (original 2021)": "vx5bkbhb",
    "theatre of magic (bally 1995)": "kiiLM_GN",
    "they live (original 2023)": "y7d7DNt3Qt",
    "thor (zen studios 2013)": "IU7Zkqv1",
    "thornley (original 2025)": "gLemPxo9Dw",
    "three angels (original 2018)": "IRgxyCix",
    "thunder man (apple time 1987)": "CyG4kDtzvw",
    "thunderbirds (original 2022)": "1y0NVRDr_C",
    "thunderbirds - are go! (original 2022)": "1d3-RVUvTN",
    "thunderbirds 60th anniversary (original 2026)": "OXUBvOg1iI",
    "thundercats pinball (original 2023)": "xhpcI1231-",
    "ticket tac toe (williams 1996)": "mOjHtjDe9m",
    "tidal wave (gottlieb 1981)": "vqyvFLahi_",
    "tiger (gottlieb 1975)": "jOVVzXe8",
    "tiger king (original 2020)": "xeMEwnyh",
    "tiki bob's atomic beach party (original 2021)": "CVHe8R32",
    "tiki bob's swingin' holiday soiree (original 2022)": "-jJB5ZfQRh",
    "tiki time (original 2020)": "lKDPpEcL",
    "time 2000 (atari 1977)": "7oT1EdfSDc",
    "time fantasy (williams 1983)": "bmQT4buf",
    "time line (gottlieb 1980)": "iktTYdg9",
    "time lord (original 2022)": "vWT8GLvKPS",
    "time machine (data east 1988)": "vNqgU1YDF0",
    "time machine (ltd do brasil 1984)": "zMoWQ_PVLU",
    "time machine (zaccaria 1983)": "zT2tZRVg",
    "time traveler (original 2023)": "aGtYKFUWWj",
    "time tunnel (bally 1971)": "hLJnAay7",
    "time warp (williams 1979)": "0Pq8C0VW",
    "timon & pumbaa's jungle pinball (original 2021)": "_Ts_Wk7S",
    "tiro's (maresa 1969)": "XgftLcyb0Y",
    "titan (gottlieb 1982)": "kqzkysDPXr",
    "titan (taito do brasil 1981)": "InZG6JoX",
    "titan music (original 2025)": "ElmbaVvSE3",
    "title fight (gottlieb 1990)": "cRSV8XDJ",
    "tmnt (original 2020)": "Kw_m-X7ec5",
    "toledo (williams 1975)": "wu6Pa4X04A",
    "tom & jerry (original 2018)": "b6axSOpI",
    "tom petty (original 2020)": "kyNiwgv0",
    "tomb raider (original 2025)": "bwcVdfNOkM",
    "tomb raider - a survival is born (original 2019)": "GVFYxkwl",
    "tommy boy (original 2021)": "IFe_O5ZeeC",
    "tool (original 2020)": "AWo3MJjw",
    "top card (gottlieb 1974)": "qojwopi4",
    "top dawg (williams 1988)": "ZSH3f9cM",
    "top gun (original 2019)": "ehCWCc--",
    "top hand (gottlieb 1973)": "4NQBsG_T",
    "top of the pops xmas pinball (original 2020)": "7kjope_e",
    "top score (gottlieb 1975)": "cYTJ0ENe",
    "topaz (inder 1979)": "s4wU8MGh7o",
    "torch (gottlieb 1980)": "xnJ3RrQ5",
    "tornado rally (original 2024)": "PS2uU-GEi9",
    "torpedo alley (data east 1988)": "fj7lWr9F",
    "torpedo!! (petaco 1976)": "VVZ51yXzdr",
    "total nuclear annihilation (spooky pinball 2017)": "ZvgMtIsme4",
    "total nuclear annihilation - welcome to the future edition (spooky pinball 2017)": "WKrqYHntcH",
    "totem (gottlieb 1979)": "CIpPAgLr",
    "toto (original 2025)": "DReeI1bf7c",
    "touchdown (gottlieb 1984)": "cFKLZDPs",
    "touchdown (williams 1967)": "byEFYfph",
    "toxic tattoo (original 2020)": "5EgHryzS",
    "toy story 90s pinball (original 2024)": "jv59nu-WNs",
    "trade winds (williams 1962)": "ajca1wnW",
    "trailer (playmatic 1985)": "xtuFBf0V",
    "trailer park boys - pin-ballers (original 2024)": "W6YLM398ZC",
    "tramway (williams 1973)": "e_9xR9Lp",
    "transformers (pro) (stern 2011)": "QCIktnpS",
    "transformers - the movie 1986 (original 2019)": "-BIEKO2q",
    "transformers g1 (original 2018)": "NVPpFZ38",
    "transporter the rescue (bally 1989)": "Xl7nUlzY",
    "travel time (williams 1972)": "Asp1n_t_Dj",
    "treff (walter steiner 1949)": "jq0vleBiEm",
    "tri zone (williams 1979)": "Cum8yakf",
    "trials of kaladon (original 2021)": "o9NOktle",
    "trick 'r treat (original 2025)": "A2tWThQM10",
    "trick or treat (codemasters 1995)": "_dIoMLu1a5",
    "trick shooter (ltd do brasil 1980)": "ZDPVwRnwO-",
    "trident (stern 1979)": "LQwMh6uV",
    "triple action (williams 1973)": "vDZ42HyxFI",
    "triple strike (williams 1975)": "IoAtHCmx",
    "triple x (williams 1973)": "VcBuBIH54w",
    "tripping tractors (original 2025)": "9ZHFbnyKzJ",
    "triumph (original 2021)": "Q0Y2vcF_",
    "tron classic (original 2018)": "xvRzOeMm",
    "tron classic - pup-pack edition (original 2018)": "3p3shVicOe",
    "tron legacy - ultimate doflinx cabinet edition  (original 2016)": "7URlZHUpv8",
    "tron neon (original 2024)": "OhE1dEJEEu",
    "tropic fun (williams 1973)": "cBxty2cIfK",
    "truck stop (bally 1988)": "HURfV7p8",
    "turrican (original 2018)": "SQxtKL05",
    "twilight zone (bally 1993)": "g5oHhr9SIf",
    "twilight zone - b&w edition (bally 1993)": "6PKuEaZ-",
    "twin peaks (original 2022)": "Gr9n2wfh",
    "twin peaks - remix edition (original 2022)": "C-vQAmkgzq",
    "twinky (chicago coin 1967)": "uKcUlo9Fj8",
    "twisted metal (original 2024)": "VsUs5klZjw",
    "twister (sega 1996)": "BwFEC9N9",
    "tx-sector (gottlieb 1988)": "gtRiKNS6",
    "tyrannosaurus (gottlieb 1985)": "4mkxci4q1j",
    "u-boat 65 (nuova bell games 1988)": "Bcznsvu1",
    "u-foes (original 2019)": "JFiya62l",
    "u2 (original 2024)": "ocKUrSdotD",
    "u2 360 (original 2025)": "OR0lT6Fx4Z",
    "u2 reskin (original 2025)": "EevJqZDEOx",
    "ub40 (original 2025)": "4ulM5NQiHQ",
    "ultron (original 2022)": "3MB2Vnn-",
    "underwater (recel 1976)": "Z-3_BPpcZB",
    "unicorcs (original 2024)": "r2hXCCIUvY",
    "universe (gottlieb 1959)": "tzEfHK2cFO",
    "universe (zaccaria 1976)": "zacBpIwu",
    "unreal tournament 99 capture the flag (original 2021)": "Qs8WtXow",
    "untouchables, the (original 2023)": "qsbc6jeKW7",
    "v.1 (idsa 1986)": "s8NeWzRw",
    "v12 (zen studios 2013)": "nPMTSUob",
    "vampire (bally 1971)": "iN8AzYCOw1",
    "vampirella (original 2024)": "syKtO8XvRc",
    "van halen (original 2020)": "B3a7rbey",
    "van halen (original 2025)": "nAh3nmTWiG",
    "vasco da gama (original 2020)": "lXsd-ptf",
    "vector (bally 1982)": "SYaXZbcp",
    "vector pinball (field one) (dozing cat software 2010)": "M5cKCCuXLL",
    "vegas (gottlieb 1990)": "f90d5qRk",
    "vegas (taito do brasil 1980)": "xGsCQ1ve",
    "venom (zen studios 2014)": "G4ezO8gY",
    "verne's world (spinball s.a.l. 1996)": "o0xA2LBd",
    "verne’s mysterious island (zen studios 2023)": "dbBrujes3E",
    "victory (gottlieb 1987)": "PBhrbuPy",
    "viking (bally 1980)": "p1rFk9R4GF",
    "viking king (ltd do brasil 1979)": "IufyUTZf",
    "vikings (original 2022)": "BKbUboJ03l",
    "viper (stern 1981)": "8W1yGtD4",
    "viper night drivin' (sega 1998)": "6qFvtdfj",
    "viper night drivin' - jp's viper night drivin' (sega 1998) (sega 1998)": "BFBwDKWzdq",
    "volcano (gottlieb 1981)": "5JqJ0BCG",
    "volkan steel and metal (original 2023)": "qIOgOh8WTt",
    "volley (gottlieb 1976)": "cMYjZKqV",
    "volley (taito do brasil 1981)": "UGEORBws",
    "voltan escapes cosmic doom (bally 1979)": "BO3fPepR",
    "voodoo ranger (original 2025)": "-QPR_pilo-",
    "voodoo's carnival pinball (original 2022)": "yTl763VWR7",
    "vortex (taito do brasil 1983)": "Ux3_EB2lyE",
    "vortex plunder (original 2025)": "m1fldFg855",
    "vpin workshop example & resource table (original 2021)": "3JSONYdl",
    "vpx foosball 2019 (original 2019)": "MgMYkPgV",
    "vr clean room with tutorial (original 2020)": "W1Pzqaqi8I",
    "vr room educational toyboy (original 2020)": "Be252-N_8O",
    "vulcan (gottlieb 1977)": "fdhhS1EO",
    "vulcan iv (rowamet 1982)": "i76EYN3zRK",
    "wacky races (original 2022)": "rWZlUIAfOh",
    "wade wilson (original 2019)": "FO5C7Q3Y",
    "wailing asteroid - murray leinster, the (original 2024)": "-ukyovb7UA",
    "walking dead (limited edition), the (stern 2014)": "QQJwJxRD",
    "walking dead (pro), the (stern 2014)": "1qM9eknMD5",
    "walking dead, the (original 2016)": "OlBaouRUX_",
    "walking dead, the (zen studios 2014)": "sU-ssRi1",
    "walkure (original 2025)": "36AJ0UrccW",
    "walkyria (joctronic 1986)": "L0OZJWWk",
    "wallace and gromit (original 2006)": "ZmeaeFcvnM",
    "warlok (williams 1982)": "H27e9-W4p4",
    "warrior sea (electromatic 1977)": "DF05i-QwoD",
    "warriors, the (original 2023)": "khFr1bNgTy",
    "watchmen (original 2019)": "luERq-1Q",
    "waterworld (gottlieb 1995)": "xfkeJbQq",
    "way of the dragon, the (original 2020)": "mBdC7YjY",
    "wayne's world (original 2020)": "zvoLtJFn",
    "wednesday (original 2023)": "OOwnOHYS0H",
    "wheel (maresa 1974)": "CVrCASw4",
    "wheel of fortune (stern 2007)": "JZ-IzOWd",
    "whirl-wind (gottlieb 1958)": "vXE1-CEo",
    "whirlwind (williams 1990)": "jqb7_mA0",
    "white christmas (original 2023)": "krwSgtByDK",
    "white water (williams 1993)": "MGSsVMlD",
    "white water - soaking wet (williams 1993)": "rr42JPjLi9",
    "whitesnake (original 2025)": "yau8WTxU-j",
    "who dunnit (bally 1995)": "nrRaikNu",
    "who framed roger rabbit (original 2021)": "FMtZqXc_",
    "who's tommy pinball wizard, the (data east 1994)": "vvVop8xT",
    "whoa nellie! big juicy melons (stern 2015)": "1fmcIchL7K",
    "whoa nellie! big juicy melons (whizbang pinball 2011)": "mSKsqxkE",
    "whoa nellie! big juicy melons - nude edition (stern 2015)": "Osu_5tYsuy",
    "wiedzmin (original 2024)": "2eHDPKvIkS",
    "wiggler, the (bally 1967)": "RELsEnoK",
    "wild card (williams 1977)": "EzpnWtUL",
    "wild fyre (stern 1978)": "dRneY5pu",
    "wild life (gottlieb 1972)": "KHNTchYp",
    "wild west (codemasters 1995)": "t6Jc0961Tj",
    "wild west (original 2024)": "V0tcEjvMt5",
    "wild west rampage (zen studios 2015)": "VQBw0p4d",
    "wild wild west (gottlieb 1969)": "qpf5IgkH",
    "wild wild west, the (original 2022)": "C9qiYKRShn",
    "willow (original 2025)": "6Hk8Z5Qo2g",
    "willy wonka & the chocolate factory (original 2020)": "tUJGp95Y",
    "willy wonka & the chocolate factory - limited edition (original 2020)": "X84foynedV",
    "willy wonka & the chocolate factory - pup-pack edition (original 2020)": "6CLmyhzOK2",
    "willy's wonderland (original 2021)": "tDICHZKM",
    "wimbledon (electromatic 1978)": "meSdCIqXhZ",
    "winner (williams 1971)": "uZaJEXNJ",
    "wipe out (gottlieb 1993)": "eahB14sy",
    "witcher, the (original 2020)": "mW3jP1tq",
    "wizard! (bally 1975)": "bIfkmE1j",
    "wizard, the (original 2021)": "2I-ZhnUxgy",
    "wolf man (peyper 1987)": "wOhjkgM3",
    "wolfenstein 3d (original 2015)": "8lhpLjrv",
    "wolfenstein 3d - ultimate mission (original 2026)": "0ODWJ9nNR3",
    "wolverine (zen studios 2010)": "sYqkvr5-",
    "wonderland (williams 1955)": "KxnvTpy0vt",
    "woodcutter, the (original 2025)": "GcfJ8nY4W-",
    "woody woodpecker (original 2022)": "tH5zY44XZB",
    "world challenge soccer (gottlieb 1994)": "L8905A0V",
    "world cup (williams 1978)": "11sxAwjH",
    "world cup soccer (bally 1994)": "GcvIOJxH4j",
    "world fair (gottlieb 1964)": "5sRUYHS97r",
    "world poker tour (stern 2006)": "A_VKDwYE",
    "world series (gottlieb 1972)": "bFsHf1Qe",
    "world war hulk (zen studios 2014)": "7Gc7yD0a",
    "world war z pinball (zen studios 2023)": "NFJr9OfQx8",
    "world's fair jig-saw (rock-ola 1933)": "Cu-1Q1c_",
    "woz (original 2018)": "bcHIj8Y7",
    "woz - yellow brick road limited edition (original 2018)": "DZ_LLbNkPD",
    "wrath of the elder gods (zen studios 2023)": "Q-92ZbsawL",
    "wwf royal rumble (data east 1994)": "siQr5H1o",
    "wyrd sisters (original 2005)": "VZNJHNKA9a",
    "x files, the (original 2021)": "e7CgUsgH6K",
    "x files, the (sega 1997)": "BXSOEZsJ",
    "x's & o's (bally 1984)": "tcABqX7Q",
    "x-men (zen studios 2013)": "L2epL7LU",
    "x-men magneto le (stern 2012)": "fX42kbrX",
    "x-men wolverine le (stern 2012)": "8rt-IoaJvt",
    "xena warrior princess pinball - table_167 (zen studios 2024)": "ahZv85K6BU",
    "xenon (bally 1980)": "aQuoB8Um0K",
    "xenon - out of breath edition (bally 1980)": "QzxYtemvBb",
    "xenotilt hostile pinball action (wiznwar, flarb llc 2024)": "G14BXa_dWu",
    "yamanobori (komaya 1981)": "gOq3VVOY",
    "yello pinball cha cha (original 2021)": "x7KMQgcQ_t",
    "yellow submarine (original 2020)": "jFSxIWXn",
    "yes (original 2025)": "hZwkYmhtjy",
    "young frankenstein (original 2016)": "rcjsv2h9",
    "young frankenstein (original 2021)": "wrBI7RTr",
    "young frankenstein (original 2025)": "lixjunCEDn",
    "you’ll shoot your eye out! (original 2024)": "WkzBKsIaqe",
    "yukon (special) (williams 1971)": "jc1tuYIv8F",
    "yukon (williams 1971)": "BeQwg_XY",
    "zarza (taito do brasil 1982)": "iYcI52uOdE",
    "zeke's peak (taito 1984)": "DPJ7lKv9",
    "zephy (ltd do brasil 1982)": "oBBg3XsLgQ",
    "zip-a-doo (bally 1970)": "aDwJXX79",
    "zira (playmatic 1980)": "9gDc49XV",
    "zissou - the life aquatic (original 2022)": "IPhDfXdVtv",
    "zodiac (williams 1971)": "kc1FB8NS08",
    "zonderik pinball (belgamko 2010)": "74eECByxZ4",
    "zone fury (original 2023)": "CXtqUmfDUy",
    "zz top (original 2021)": "UCpWufnwis",
    "zz top (original 2025)": "uS0mxoSZJb",}


class VPXStandaloneMergingUtility:
    def __init__(self, root):
        self.root = root
        self.root.title(f"VPX UTILITY v{VERSION} - FULL RESTORATION")
        self.root.geometry("1400x1000")
        self.root.minsize(1200, 900)
        self.root.resizable(True, True) 
        self.root.configure(bg="#1e1e1e") 
        
        self.config_file = os.path.join(os.path.expanduser("~"), ".vpx_utility_config.json")
        self.sources = {"tables": tk.StringVar(), "vpinmame": tk.StringVar(), "pupvideos": tk.StringVar(), "music": tk.StringVar()}
        self.target = tk.StringVar()
        self.enable_patch_lookup = tk.BooleanVar(value=True)
        self.include_media = tk.BooleanVar(value=False)
        self.media_format = tk.StringVar(value="VPinFE")  # VPinFE or Batocera
        
        # File tracking for summary
        self.file_stats = {
            'tables': 0, 'roms': 0, 'backglass': 0, 'altsound': 0, 'altcolor': 0, 
            'pup_packs': 0, 'music_tracks': 0, 'patches': 0, 'vbs_files': 0
        }
        
        # Media DB - loaded in background at startup
        self.vpinmdb      = {}   # { id: {1k:{table:url,...}, wheel:url, ...} }
        self.vpsdb_lookup = {}   # { "rom_or_name_lower": id }
        self.media_db_ready = False
        
        self.load_settings()
        self.vpx_files = []
        self.setup_ui()
        
        # Load media DB in background so UI is not blocked
        threading.Thread(target=self.load_media_db, daemon=True).start()

    def load_settings(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    for key, val in data.get("sources", {}).items():
                        if key in self.sources: self.sources[key].set(val)
                    if "target" in data: self.target.set(data["target"])
            except: pass

    def _make_section(self, parent, label, accent):
        """Creates a modern section with a slim colored top-border and label."""
        outer = tk.Frame(parent, bg=accent, pady=1)
        outer.pack(fill="x", padx=28, pady=(8, 0))
        inner = tk.Frame(outer, bg="#1a1e2e", pady=6, padx=12)
        inner.pack(fill="x")
        tk.Label(inner, text=label, bg="#1a1e2e", fg=accent,
                 font=("Courier", 14, "bold", "underline")).pack(anchor="w")
        return inner

    def _make_btn(self, parent, text, color, cmd, dim_color, height=2):
        """Rounded-feel button with hover."""
        btn = tk.Button(parent, text=text, bg=color, fg="#0a0d1a",
                        font=("Courier", 16, "bold"), relief="flat",
                        bd=0, height=height, cursor="hand2", command=cmd,
                        activebackground=dim_color, activeforeground="#0a0d1a",
                        disabledforeground="#555566")
        btn.bind("<Enter>", lambda e, b=btn, c=dim_color: b.config(bg=c) if b["state"] == "normal" else None)
        btn.bind("<Leave>", lambda e, b=btn, c=color:     b.config(bg=c) if b["state"] == "normal" else None)
        return btn

    def setup_ui(self):
        BG      = "#0a0d1a"   # deep navy black
        PANEL   = "#111526"   # slightly lighter panel
        BORDER  = "#1e2440"   # subtle border
        ACCENT1 = "#00e5ff"   # cyan   — sources
        ACCENT2 = "#ffd600"   # amber  — target
        GREEN   = "#00e676"   # green  — found / main action
        CYAN    = "#40c4ff"   # blue   — vbs
        ORANGE  = "#ff9100"   # orange — patch
        RED     = "#ff1744"   # red    — clear
        MUTED   = "#4a5080"   # muted text

        self.root.configure(bg=BG)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(18, 4))

        # Canvas title with white outline + cyan fill
        title_canvas = tk.Canvas(hdr, bg=BG, highlightthickness=0, height=62)
        title_canvas.pack(side="left", fill="x", expand=True)

        def draw_title(event=None):
            title_canvas.delete("all")
            cw = title_canvas.winfo_width() or 900
            cx = cw // 2
            txt = "VPX  STANDALONE  MERGING  TOOL"
            fnt = ("Courier", 42, "bold")
            # White outline — draw 8 times offset in every direction
            for dx, dy in [(-2,-2),(2,-2),(-2,2),(2,2),(-2,0),(2,0),(0,-2),(0,2)]:
                title_canvas.create_text(cx+dx, 31+dy, text=txt, font=fnt,
                                         fill="#ffffff", anchor="center")
            # Cyan fill on top
            title_canvas.create_text(cx, 31, text=txt, font=fnt,
                                     fill=ACCENT1, anchor="center")

        title_canvas.bind("<Configure>", draw_title)
        title_canvas.after(50, draw_title)

        tk.Label(hdr, text=f"v{VERSION}", font=("Courier", 10),
                 fg=MUTED, bg=BG).pack(side="right", anchor="n", pady=(4, 0))

        # thin separator line under header
        tk.Frame(self.root, bg=ACCENT1, height=1).pack(fill="x", padx=28, pady=(0, 6))

        # ── Sources ───────────────────────────────────────────────────────────
        src_sec = self._make_section(self.root, "◈  SOURCE FOLDERS", ACCENT1)
        LABELS = {"tables": "TABLES", "vpinmame": "VPINMAME", "pupvideos": "PUP VIDEOS", "music": "MUSIC"}
        for key in ["tables", "vpinmame", "pupvideos", "music"]:
            row = tk.Frame(src_sec, bg="#1a1e2e")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=LABELS[key], bg="#1a1e2e", fg="#ffffff",
                     font=("Courier", 11, "bold"), width=11, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=self.sources[key],
                     bg=BORDER, fg="#ffffff", font=("Courier", 10, "bold"),
                     relief="flat", bd=0,
                     insertbackground=ACCENT1).pack(side="left", fill="x", expand=True, padx=(4, 6), ipady=5)
            tk.Button(row, text="›", bg="#1e2856", fg=ACCENT1,
                      font=("Courier", 14, "bold"), relief="flat", bd=0,
                      width=3, cursor="hand2",
                      command=lambda k=key: self.browse_path(k, "source"),
                      activebackground="#2a3870", activeforeground=ACCENT1).pack(side="right")

        # ── Target ────────────────────────────────────────────────────────────
        tgt_sec = self._make_section(self.root, "◈  EXPORT TARGET", ACCENT2)
        tgt_row = tk.Frame(tgt_sec, bg="#1a1e2e")
        tgt_row.pack(fill="x", pady=2)
        tk.Entry(tgt_row, textvariable=self.target,
                 bg=BORDER, fg="#ffffff", font=("Courier", 10, "bold"),
                 relief="flat", bd=0,
                 insertbackground=ACCENT2).pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=5)
        tk.Button(tgt_row, text="›", bg="#2a2000", fg=ACCENT2,
                  font=("Courier", 13, "bold"), relief="flat", bd=0,
                  width=3, cursor="hand2",
                  command=lambda: self.browse_path(None, "target"),
                  activebackground="#3a3000", activeforeground=ACCENT2).pack(side="right")

        # ── Options row ───────────────────────────────────────────────────────
        opt_row = tk.Frame(self.root, bg=BG)
        opt_row.pack(fill="x", padx=28, pady=(10, 2))
        tk.Checkbutton(opt_row, text=" Enable Patch Lookup  (GitHub)",
                       variable=self.enable_patch_lookup,
                       bg=BG, fg=GREEN, selectcolor=BORDER,
                       font=("Courier", 11, "bold"), activebackground=BG,
                       activeforeground=GREEN, cursor="hand2").pack(side="left")
        
        tk.Checkbutton(opt_row, text=" Include Media Files",
                       variable=self.include_media,
                       bg=BG, fg=CYAN, selectcolor=BORDER,
                       font=("Courier", 11, "bold"), activebackground=BG,
                       activeforeground=CYAN, cursor="hand2").pack(side="left", padx=(20, 0))
        
        # Media format dropdown
        tk.Label(opt_row, text="Format:", bg=BG, fg=CYAN,
                 font=("Courier", 11, "bold")).pack(side="left", padx=(10, 5))
        media_dropdown = ttk.Combobox(opt_row, textvariable=self.media_format,
                                      values=["VPinFE", "Batocera", "PuP Media"],
                                      state="readonly", width=10,
                                      font=("Courier", 10))
        media_dropdown.pack(side="left")

        # ── Progress Bar ──────────────────────────────────────────────────────
        self.progress_frame = tk.Frame(self.root, bg=BG, height=1)
        self.progress_frame.pack(fill="x", padx=28, pady=0)
        self.progress_frame.pack_propagate(False)  # keep fixed height — prevents layout shift
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Neo.Horizontal.TProgressbar",
                        troughcolor=BORDER, background=ACCENT1,
                        borderwidth=0, thickness=6)
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode="determinate",
                                            style="Neo.Horizontal.TProgressbar")
        self.progress_label = tk.Label(self.progress_frame, text="", bg=BG, fg="#ffffff",
                                       font=("Courier", 10, "bold"))
        # bar and label hidden initially — frame stays packed to hold layout space

        # ── Main area (audit log + preview) ──────────────────────────────────
        main_container = tk.Frame(self.root, bg=BG, height=500)
        main_container.pack(fill="both", expand=True, padx=28, pady=(8, 4))
        main_container.pack_propagate(False)

        # Audit log
        audit_outer = tk.Frame(main_container, bg=BORDER, pady=1, padx=1)
        audit_outer.pack(side="left", fill="both", expand=True)
        audit_inner = tk.Frame(audit_outer, bg=PANEL)
        audit_inner.pack(fill="both", expand=True)

        # header bar for audit
        audit_hdr = tk.Frame(audit_inner, bg="#161a2e", pady=6)
        audit_hdr.pack(fill="x")
        # spacer left
        tk.Label(audit_hdr, text="", bg="#161a2e", width=8).pack(side="left")
        tk.Label(audit_hdr, text="AUDIT LOG",
                 bg="#161a2e", fg="#ffffff", font=("Courier", 14, "bold")).pack(side="left", expand=True)
        tk.Button(audit_hdr, text="✕  CLEAR", command=self.clear_list,
                  bg="#2a0010", fg=RED, font=("Courier", 11, "bold"),
                  relief="flat", bd=0, padx=12, pady=2, cursor="hand2",
                  activebackground="#3a0018", activeforeground=RED).pack(side="right", padx=6)

        self.audit_list = tk.Text(audit_inner, bg=PANEL, fg="#c0cce8",
                                  font=("Menlo", 13), state="disabled",
                                  padx=14, pady=8, relief="flat", bd=0,
                                  width=68, insertbackground=ACCENT1)
        scrollbar = tk.Scrollbar(audit_inner, command=self.audit_list.yview,
                                 bg=BORDER, troughcolor=PANEL,
                                 activebackground=MUTED, relief="flat", bd=0, width=8)
        self.audit_list.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.audit_list.pack(fill="both", expand=True)

        self.audit_list.tag_configure("table_name", foreground=ACCENT1, font=("Menlo", 15, "bold"))
        self.audit_list.tag_configure("found",   foreground=GREEN,   font=("Menlo", 13))
        self.audit_list.tag_configure("missing", foreground="#ffffff", font=("Menlo", 13))
        self.audit_list.tag_configure("yellow",  foreground=ACCENT2, font=("Menlo", 13, "bold"))
        self.audit_list.tag_configure("white",   foreground="#7080a0", font=("Menlo", 13))
        self.audit_list.drop_target_register(DND_FILES)
        self.audit_list.dnd_bind("<<Drop>>", self.handle_drop)

        # Centered drop hint overlay — shown when log is empty
        self.drop_hint = tk.Label(audit_inner,
                                  text="DROP  .VPX  TABLE  HERE",
                                  bg=PANEL, fg="#ffd600",
                                  font=("Courier", 22, "bold"),
                                  cursor="hand2",
                                  highlightthickness=2,
                                  highlightbackground="#ffffff",
                                  padx=16, pady=10)
        self.drop_hint.place(relx=0.5, rely=0.5, anchor="center")
        self.drop_hint.drop_target_register(DND_FILES)
        self.drop_hint.dnd_bind("<<Drop>>", self.handle_drop)

        # Preview panel
        prev_outer = tk.Frame(main_container, bg=BORDER, pady=1, padx=1, width=462)
        prev_outer.pack(side="right", fill="y", padx=(10, 0))
        prev_outer.pack_propagate(False)
        self.preview_frame = tk.Frame(prev_outer, bg=PANEL, width=460)
        self.preview_frame.pack(fill="both", expand=True)
        self.preview_frame.pack_propagate(False)

        # ── Header row: title + globe + back button ─────────────────────────
        prev_hdr = tk.Frame(self.preview_frame, bg=PANEL)
        prev_hdr.pack(fill="x", pady=(10, 4))

        # Globe button (VPS link) - left side
        self.btn_vps_link = tk.Button(prev_hdr, text="🌐",
                 bg=PANEL, fg="#40c4ff", font=("Arial", 20),
                 relief="flat", bd=0, cursor="hand2",
                 command=self._open_vps_link,
                 activebackground="#1a1e2e", activeforeground="#ffffff")
        self.btn_vps_link.pack(side="left", padx=(8, 0))
        self.btn_vps_link.pack_forget()  # hidden until VPS ID is available
        
        # Store VPS URL for the globe button
        self.current_vps_url = None

        self.preview_title = tk.Label(prev_hdr, text="TABLE PREVIEW",
                 bg=PANEL, fg="#ffffff", font=("Courier", 16, "bold"),
                 wraplength=420, justify="center")
        self.preview_title.pack(side="left", expand=True, fill="x", padx=(10, 0))

        self.btn_back_preview = tk.Button(prev_hdr, text="◀ ALL",
                 bg=PANEL, fg="#00e5ff", font=("Courier", 9, "bold"),
                 relief="flat", bd=0, cursor="hand2",
                 command=self._preview_back,
                 activebackground="#1a1e2e", activeforeground="#ffffff")
        self.btn_back_preview.pack(side="right", padx=(0, 8))
        self.btn_back_preview.pack_forget()  # hidden until multi-file grid is active

        tk.Frame(self.preview_frame, bg=BORDER, height=1).pack(fill="x", padx=10)

        # ── Single big view (DEFAULT) ─────────────────────────────────────────
        self.preview_single_frame = tk.Frame(self.preview_frame, bg=PANEL)
        self.preview_single_frame.pack(fill="both", expand=True)

        self.preview_canvas = tk.Canvas(self.preview_single_frame, bg="#0d101e",
                                        width=440, height=490, highlightthickness=0)
        self.preview_canvas.pack(pady=(8, 4), padx=10, fill="both", expand=True)

        self.preview_table_name = tk.Label(self.preview_single_frame, text="",
                                           bg=PANEL, fg="#ffffff",
                                           font=("Courier", 11, "bold"),
                                           wraplength=430, justify="center")
        self.preview_table_name.pack(pady=(2, 1))

        self.preview_rom_name = tk.Label(self.preview_single_frame, text="",
                                         bg=PANEL, fg=GREEN,
                                         font=("Courier", 8), wraplength=430)
        self.preview_rom_name.pack(pady=1)

        # ── Grid view (up to 6 thumbnails 2×3) — shown for multiple files ────
        self.preview_grid_frame = tk.Frame(self.preview_frame, bg=PANEL)
        # not packed yet — appears when 2+ files are dropped
        self.thumb_cells  = []
        self.thumb_images = []

        # ── Status bar ────────────────────────────────────────────────────────
        self.preview_status = tk.Label(self.preview_frame,
                                       text="Drop a .vpx file to preview",
                                       bg=PANEL, fg="#a0b4d0",
                                       font=("Courier", 9, "italic"), wraplength=440)
        self.preview_status.pack(side="bottom", pady=(4, 6))

        # State
        self.current_preview_image = None
        self.thumb_images  = []
        self._preview_data = []   # [{table_name, rom_name, image, thumb, loaded}]
        self._zoom_index   = None # slot being shown in single view from grid

        # ── Action buttons ────────────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(fill="x", padx=28, pady=(4, 6))

        self.btn_full = self._make_btn(btn_frame, "⚡  MAKE THE MAGIC HAPPEN",
                                       GREEN, lambda: self.start_thread("full"), "#33ff99")
        self.btn_full.config(state="disabled")
        self.btn_full.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_vbs = self._make_btn(btn_frame, "◎  CREATE CLEAN .VBS",
                                      CYAN, lambda: self.start_thread("vbs"), "#80d8ff")
        self.btn_vbs.config(state="disabled")
        self.btn_vbs.pack(side="left", fill="x", expand=True, padx=4)

        self.btn_fix = self._make_btn(btn_frame, "🔧  FIX SCRIPT",
                                      "#ff3366", lambda: self.start_thread("fix"), "#ff6699")
        self.btn_fix.config(state="disabled")
        self.btn_fix.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # ── Bottom bar ────────────────────────────────────────────────────────
        bot = tk.Frame(self.root, bg=BG)
        bot.pack(fill="x", padx=28, pady=(0, 10))

        # Load and resize logo to fit beside small text (~28px tall)
        try:
            _logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mf_logo.png")
            _logo_img = Image.open(_logo_path).convert("RGBA")
            _logo_img = _logo_img.resize((28, 28), Image.Resampling.LANCZOS)
            self._logo_photo = ImageTk.PhotoImage(_logo_img)
            tk.Label(bot, image=self._logo_photo, bg=BG).pack(side="right", padx=(4, 0))
        except Exception:
            self._logo_photo = None

        tk.Label(bot, text="Brought to you by Major Frenchy .",
                 font=("Courier", 11, "bold"), fg="#ffffff", bg=BG).pack(side="right")

    def log_audit(self, msg, tag=None):
        self.audit_list.config(state="normal"); self.audit_list.insert(tk.END, msg + "\n", tag); self.audit_list.config(state="disabled"); self.audit_list.see(tk.END)
    
    def log_hyperlink(self, text, url):
        """Log a clickable hyperlink"""
        self.audit_list.config(state="normal")
        # Store URL as tag name so we can retrieve it on click
        tag_name = f"link_{id(url)}"
        self.audit_list.tag_configure(tag_name, foreground="#40c4ff", font=("Menlo", 13, "underline"))
        self.audit_list.tag_bind(tag_name, "<Button-1>", lambda e, u=url: self.open_url(u))
        self.audit_list.tag_bind(tag_name, "<Enter>", lambda e: self.audit_list.config(cursor="hand2"))
        self.audit_list.tag_bind(tag_name, "<Leave>", lambda e: self.audit_list.config(cursor=""))
        self.audit_list.insert(tk.END, text, tag_name)
        self.audit_list.insert(tk.END, "\n")
        self.audit_list.config(state="disabled")
        self.audit_list.see(tk.END)
    
    def open_url(self, url):
        """Open URL in default browser"""
        import webbrowser
        webbrowser.open(url)
    
    def log_separator(self, style="single"):
        """Add visual separator lines"""
        if style == "double":
            self.log_audit("╔═══════════════════════════════════════════════════════╗", "white")
        elif style == "single":
            self.log_audit("─" * 55, "white")
        elif style == "bottom":
            self.log_audit("╚═══════════════════════════════════════════════════════╝", "white")
    
    def load_media_db(self):
        """Download live VPS database + vpinmdb, build lookup fresh every run."""
        try:
            self.root.after(0, lambda: self.preview_status.config(
                text="\u23f3 Loading media database...", fg="#ffcc00"))

            # ── 1. Download vpsdatabaseV2.json (updated daily) ─────────────
            req = urllib.request.Request(
                "https://raw.githubusercontent.com/xantari/VPS.Database/main/vpsdatabaseV2.json",
                headers={"User-Agent": "VPXMergeTool/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                vpsdata = json.loads(r.read().decode())
            entries = vpsdata.get("Entries", [])

            # ── 2. Build title -> vpinmdb_id lookup ────────────────────────
            AUTHOR_PREFIXES = [
                "jp's", "jps", "jp'", "vpw", "sg1", "flupper",
                "hauntfreaks", "davadruix", "jp\u2019s"
            ]

            def normalize(s):
                import re as _re
                s = s.lower()
                s = _re.sub(r"[\u2019\u2018`\']", "", s)
                s = _re.sub(r"[^a-z0-9\s]", " ", s)
                s = _re.sub(r"\s+", " ", s).strip()
                return s

            def word_sorted(s):
                """Canonical word-sorted key so word-order variants match."""
                words = sorted(w for w in s.split() if w not in ('the','a','an','of','and','in'))
                return " ".join(words)

            def make_keys(title):
                import re as _re
                keys = set()
                t = title.strip()
                keys.add(t.lower())
                norm_t = normalize(t)
                keys.add(norm_t)
                keys.add(word_sorted(norm_t))          # word-order invariant
                clean = _re.sub(r"\s*\(.*?\)", "", t).strip()
                norm_c = normalize(clean)
                keys.add(clean.lower())
                keys.add(norm_c)
                keys.add(word_sorted(norm_c))          # word-order invariant
                for prefix in AUTHOR_PREFIXES:
                    for pat in [prefix + "'s ", prefix + "s ", prefix + " ", prefix + "' "]:
                        if t.lower().startswith(pat.lower()):
                            rest = t[len(pat):].strip()
                            pl = prefix.rstrip("'s ").rstrip("'")
                            norm_r = normalize(rest)
                            keys.add(rest.lower())
                            keys.add(norm_r)
                            keys.add(word_sorted(norm_r))
                            keys.add(f"{rest.lower()} ({pl})")
                            keys.add(normalize(f"{rest} {pl}"))
                            break
                for suffix in [" le", " pro", " premium", " vr", " vault edition"]:
                    if norm_c.endswith(suffix):
                        keys.add(norm_c[:-len(suffix)].strip())
                return {k for k in keys if k and len(k) > 1}

            lookup = {}
            for e in entries:
                if e.get("MajorCategory") != "Table":
                    continue
                eid_raw = e.get("ExternalId", "")
                if "|" not in eid_raw:
                    continue
                vpinmdb_id = eid_raw.split("|")[0]
                title = e.get("Title", "").strip()
                if not title or not vpinmdb_id:
                    continue
                for key in make_keys(title):
                    if key not in lookup:
                        lookup[key] = vpinmdb_id

            self.vpsdb_lookup = lookup

            # ── 3. Supplement with live VPS spreadsheet (2,400+ entries) ──
            # This is the authoritative source - same one vpinfe uses
            vps_urls = [
                "https://virtualpinballspreadsheet.github.io/vps-db/db/vpsdb.json",
                "https://raw.githubusercontent.com/VirtualPinballSpreadsheet/vps-db/master/db/vpsdb.json",
            ]
            for vps_url in vps_urls:
                try:
                    req_vps = urllib.request.Request(
                        vps_url, headers={"User-Agent": "VPXMergeTool/1.0"})
                    with urllib.request.urlopen(req_vps, timeout=20) as r:
                        vpsdb_live = json.loads(r.read().decode())
                    added = 0
                    for entry in vpsdb_live:
                        eid = entry.get("id", "")
                        if not eid:
                            continue
                        name = entry.get("name", "").strip()
                        if name:
                            for key in make_keys(name):
                                if key not in lookup:
                                    lookup[key] = eid
                                    added += 1
                        for rom in entry.get("roms", []):
                            if isinstance(rom, dict):
                                for k in ("id", "name"):
                                    v = rom.get(k, "")
                                    if v and v.lower() not in lookup:
                                        lookup[v.lower()] = eid
                    self.vpsdb_lookup = lookup
                    break

                except Exception as ve:
                    continue


            # ── 3. Download vpinmdb.json (image index) ─────────────────────
            req2 = urllib.request.Request(
                "https://raw.githubusercontent.com/superhac/vpinmediadb/refs/heads/main/vpinmdb.json",
                headers={"User-Agent": "VPXMergeTool/1.0"})
            with urllib.request.urlopen(req2, timeout=20) as r:
                self.vpinmdb = json.loads(r.read().decode())

            # ── 4. Load user custom mappings (optional) ──────────────────
            custom_map_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_mappings.txt")
            if os.path.exists(custom_map_path):
                try:
                    with open(custom_map_path, 'r', encoding='utf-8') as cf:
                        for line in cf:
                            line = line.strip()
                            if not line or line.startswith('#'):
                                continue
                            if '=' in line:
                                table_name, vpinmdb_id = line.split('=', 1)
                                table_name = table_name.strip()
                                vpinmdb_id = vpinmdb_id.strip()
                                if table_name and vpinmdb_id:
                                    # Add both raw and normalized versions
                                    self.vpsdb_lookup[table_name.lower()] = vpinmdb_id
                                    norm = re.sub(r"[^\w\s]", " ", table_name.lower())
                                    norm = re.sub(r"\s+", " ", norm).strip()
                                    self.vpsdb_lookup[norm] = vpinmdb_id
                except Exception:
                    pass  # Silently ignore custom mapping errors
            
            # ── 5. Load embedded VPS database ─────────────────────────────
            # Use the embedded VPS_TABLE_LOOKUP dictionary (2,668 tables)
            for table_name, table_id in VPS_TABLE_LOOKUP.items():
                if table_name not in self.vpsdb_lookup:
                    self.vpsdb_lookup[table_name] = table_id
            
            # ── 6. Load local CSV database (optional fallback) ────────────
            csv_db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pinballxdatabase.csv")
            if os.path.exists(csv_db_path):
                try:
                    import csv
                    with open(csv_db_path, 'r', encoding='utf-8-sig') as csvf:
                        reader = csv.DictReader(csvf)
                        for row in reader:
                            table_full = row.get('Table Name (Manufacturer Year)', '').strip()
                            if not table_full:
                                continue
                            
                            # Extract base name (before author/version info)
                            # Format: "Table Name (Manufacturer Year) Author Version"
                            # We want just the "Table Name (Manufacturer Year)" part
                            parts = table_full.split()
                            # Find where manufacturer/year ends
                            base_end = -1
                            for i, part in enumerate(parts):
                                if part.endswith(')'):
                                    base_end = i
                                    break
                            
                            if base_end > 0:
                                base_name = ' '.join(parts[:base_end+1])
                            else:
                                base_name = table_full
                            
                            # Also try without manufacturer/year
                            clean_name = re.sub(r'\s*\([^)]+\)\s*', '', base_name).strip()
                            
                            # PRIORITY: Use VPS Table ID if available (e.g., VAx9weFV)
                            table_id = row.get('Table ID', '').strip()
                            if table_id:
                                vid = table_id
                            elif row.get('IPDB Number', '').strip() and row.get('IPDB Number', '').strip() != '-':
                                # Fallback to IPDB number
                                ipdb = row.get('IPDB Number', '').strip()
                                vid = f"ipdb_{ipdb}"
                            else:
                                # Last resort: use normalized name
                                vid = normalize(clean_name).replace(' ', '_')
                            
                            # Add various name formats to lookup
                            for name_var in [base_name, clean_name, table_full]:
                                if name_var:
                                    norm = normalize(name_var)
                                    if norm and norm not in self.vpsdb_lookup:
                                        self.vpsdb_lookup[norm] = vid
                                        self.vpsdb_lookup[name_var.lower()] = vid
                except Exception:
                    pass  # Silently ignore CSV errors
            
            self.media_db_ready = True
            n = len(self.vpsdb_lookup)
            m = len(self.vpinmdb)
            self.root.after(0, lambda: self.preview_status.config(
                text=f"\u2713 Ready  {n:,} titles | {m:,} media", fg="#00ff00"))

        except Exception as e:
            err = str(e)[:45]
            # Fall back to bundled lookup if present
            lookup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vps_title_lookup.json")
            if os.path.exists(lookup_path):
                with open(lookup_path, "r", encoding="utf-8") as f:
                    combined = json.load(f)
                    self.vpsdb_lookup = combined.get("vpinmdb", combined) if isinstance(combined, dict) else {}
                self.media_db_ready = True
                self.root.after(0, lambda: self.preview_status.config(
                    text="\u26a0 Using cached DB (offline)", fg="#ffcc00"))
            else:
                self.root.after(0, lambda: self.preview_status.config(
                    text=f"\u26a0 DB failed: {err}", fg="#ff6600"))

    def _open_vps_link(self):
        """Open VPS link when globe button is clicked"""
        if self.current_vps_url:
            import webbrowser
            webbrowser.open(self.current_vps_url)
    
    def update_preview(self, table_name, rom_name=None):
        """Register a table for preview. 1 file = big single view. 2-6 = grid."""
        # Find or assign slot
        for i, d in enumerate(self._preview_data):
            if d["table_name"] == table_name:
                slot = i; break
        else:
            if len(self._preview_data) >= 6:
                return
            slot = len(self._preview_data)
            self._preview_data.append({"table_name": table_name, "rom_name": rom_name,
                                       "image": None, "thumb": None, "loaded": False})

        n = len(self._preview_data)

        if n == 1:
            # ── Single big view ───────────────────────────────────────────────
            self.preview_grid_frame.pack_forget()
            self.preview_single_frame.pack(fill="both", expand=True)
            self.btn_back_preview.pack_forget()
            self._zoom_index = None
            self.preview_title.config(text=table_name[:38])
            self.preview_table_name.config(text=table_name)
            self.preview_rom_name.config(text=f"ROM: {rom_name}" if rom_name else "")
            
            # Check for VPS ID and show/hide globe button
            vps_id = self._lookup_vps_id(table_name)
            if vps_id:
                self.current_vps_url = f"https://virtualpinballspreadsheet.github.io/tables?game={vps_id}"
                self.btn_vps_link.pack(side="left", padx=(8, 0))
            else:
                self.current_vps_url = None
                self.btn_vps_link.pack_forget()
            
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                self.preview_canvas.winfo_width()//2 or 220,
                self.preview_canvas.winfo_height()//2 or 245,
                text="⏳", font=("Arial", 32), fill="#ffcc00", anchor="center")
        else:
            # ── Rebuild grid layout to match new count ────────────────────────
            self._rebuild_grid(n)
            if self._zoom_index is None:
                self.preview_single_frame.pack_forget()
                self.preview_grid_frame.pack(fill="both", expand=True, padx=6, pady=6)
            self.preview_title.config(text=f"{n} TABLES")
            # Re-setup all existing slots after grid rebuild
            for i, d in enumerate(self._preview_data):
                self._setup_thumb_cell(i, d["table_name"])
                if d.get("loaded"):
                    self._render_thumb(i)

        # Start image fetch for this slot
        self._start_fetch(slot, table_name, rom_name)

    # Layout map: n_files -> (rows, cols)
    GRID_LAYOUT = {2: (1,2), 3: (1,3), 4: (2,2), 5: (2,3), 6: (2,3)}

    def _rebuild_grid(self, n):
        """Destroy and recreate grid cells to match layout for n files."""
        rows, cols = self.GRID_LAYOUT.get(n, (2, 3))

        # Destroy old cells
        for widget in self.preview_grid_frame.winfo_children():
            widget.destroy()
        self.thumb_cells  = []
        self.thumb_images = []

        # Remove old row/col configs
        for i in range(6):
            self.preview_grid_frame.columnconfigure(i, weight=0, minsize=0)
            self.preview_grid_frame.rowconfigure(   i, weight=0, minsize=0)

        # Thumb size based on layout
        #  1×2 → wide, short   1×3 → wide, short   2×2 → medium   2×3 → small
        sizes = {(1,2): (210, 260), (1,3): (138, 220),
                 (2,2): (210, 190), (2,3): (138, 150)}
        tw, th = sizes.get((rows, cols), (138, 150))

        for row in range(rows):
            self.preview_grid_frame.rowconfigure(row, weight=1)
            for col in range(cols):
                self.preview_grid_frame.columnconfigure(col, weight=1)
                cell = tk.Frame(self.preview_grid_frame, bg="#0d101e",
                                highlightthickness=1, highlightbackground="#2a3060")
                cell.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
                c = tk.Canvas(cell, bg="#0d101e", highlightthickness=0,
                              width=tw, height=th)
                c.pack(fill="both", expand=True)
                lbl = tk.Label(cell, text="", bg="#0d101e", fg="#a0b4d0",
                               font=("Courier", 7), wraplength=tw-10, justify="center")
                lbl.pack(fill="x", pady=(0, 2))
                self.thumb_cells.append((c, lbl))

    def _start_fetch(self, slot, table_name, rom_name):
        """Look up media DB and kick off background image download."""
        if not self.media_db_ready or not self.vpsdb_lookup or not self.vpinmdb:
            self._on_no_image(slot, table_name); return

        def normalize(s):
            s = s.lower()
            s = re.sub(r"[\'\u2019\u2018`]", "", s)
            s = re.sub(r"[^a-z0-9\s]", " ", s)
            return re.sub(r"\s+", " ", s).strip()

        def word_sorted(s):
            return " ".join(sorted(w for w in s.split() if w not in ("the","a","an","of","and","in")))

        raw = table_name.strip()
        nr  = normalize(raw)
        clean = re.sub(r"\s*\(.*?\)", "", raw).strip()
        nc    = normalize(clean)
        
        candidates = [raw.lower(), nr, word_sorted(nr), clean.lower(), nc, word_sorted(nc)]
        
        # Try hyphenated variations (Spider-Man ↔ Spiderman)
        if '-' in raw:
            no_hyphen = raw.replace('-', '').replace('  ', ' ')
            candidates.append(normalize(no_hyphen))
        
        # Known hyphenated names - try both with and without hyphen
        known_hyphenated = {
            'spiderman': 'spider-man',
            'xmen': 'x-men',
            'tmachine': 't-machine',
        }
        clean_lower = clean.lower()
        for unhyphen, hyphen in known_hyphenated.items():
            if unhyphen in clean_lower:
                # Replace in the clean version
                hyph_version = clean_lower.replace(unhyphen, hyphen)
                candidates.append(normalize(hyph_version))
        
        # Expand abbreviations
        if ' le' in nc or nc.endswith(' le'):
            # LE = Limited Edition
            expanded = nc.replace(' le', ' limited edition')
            candidates.append(expanded)
        
        # Try with/without "The" at start
        if clean.lower().startswith('the '):
            without_the = clean[4:].strip()
            candidates.append(normalize(without_the))
        else:
            candidates.append(normalize(f"the {clean}"))
        
        # Handle parenthetical manufacturer/year
        sm = re.search(r"\(([^)]+)\)\s*$", raw)
        if sm:
            a = sm.group(1).strip(); rest = raw[:sm.start()].strip(); nr2 = normalize(rest)
            candidates += [f"{a.lower()}s {rest.lower()}", f"{a.lower()} {rest.lower()}",
                           normalize(f"{a} {rest}"), word_sorted(nr2)]
            # Try just the manufacturer name without year
            mfg_match = re.match(r"^([A-Za-z]+)", a)
            if mfg_match:
                mfg = mfg_match.group(1)
                candidates.append(normalize(f"{mfg} {rest}"))
        
        # Strip common suffixes (most specific first)
        suffixes = [
            ' pinball adventure', ' pinball adventures', 
            ' the pinball adventure', ' the pinball adventures',
            ' vault edition', ' premium', ' le', ' pro', 
            ' vr', ' vpw', ' sg1', ' vpu'
        ]
        for sfx in suffixes:
            if nc.endswith(sfx): 
                stripped = nc[:-len(sfx)].strip()
                if stripped:
                    candidates.append(stripped)
                    # Also try plural/singular variations
                    if stripped.endswith('s'):
                        candidates.append(stripped[:-1])
                    else:
                        candidates.append(stripped + 's')
        
        seen, unique = set(), []
        for c in candidates:
            if c and c not in seen: seen.add(c); unique.append(c)

        media_id = next((self.vpsdb_lookup[k] for k in unique if k in self.vpsdb_lookup), None)
        if not media_id:
            # Fuzzy matching fallback: word-based similarity
            best_id, best_score = None, 0.0
            table_words = set(nc.split())  # Words from normalized table name
            
            for lk, lid in self.vpsdb_lookup.items():
                if len(lk) < 3: continue
                db_words = set(lk.split())
                
                # Method 1: Word overlap (if table has "hellboy" and DB has "hellboy", match!)
                common = table_words & db_words
                if common:
                    score = len(common) / max(len(table_words), len(db_words))
                    if score > best_score:
                        best_score = score
                        best_id = lid
                
                # Method 2: Substring matching for single-word tables
                if len(table_words) == 1 and len(db_words) == 1:
                    tw = list(table_words)[0]
                    dw = list(db_words)[0]
                    if tw in dw or dw in tw:
                        score = min(len(tw), len(dw)) / max(len(tw), len(dw))
                        if score > best_score:
                            best_score = score
                            best_id = lid
            
            # Accept if confidence is high enough
            if best_id and best_score >= 0.5: media_id = best_id

        if not media_id or media_id not in self.vpinmdb:
            # Debug: log what we found
            if media_id:
                print(f"DEBUG: Found ID '{media_id}' for '{table_name}' but NOT in vpinmdb")
                print(f"  Candidates tried: {unique[:5]}")
                # Check if ID exists in vpinmdb at all
                if media_id in self.vpinmdb:
                    print(f"  ID IS in vpinmdb but no image URL found")
                    print(f"  Entry: {self.vpinmdb[media_id]}")
                else:
                    print(f"  ID NOT in vpinmdb (media database doesn't have this table)")
            else:
                print(f"DEBUG: No ID found for '{table_name}'")
                print(f"  Candidates tried: {unique[:5]}")
                # Try to find similar keys
                similar = [k for k in list(self.vpsdb_lookup.keys())[:100] if 'leprechaun' in k.lower()]
                if similar:
                    print(f"  Similar keys in database: {similar[:5]}")
            self._on_no_image(slot, table_name); return

        entry = self.vpinmdb[media_id]
        url = (entry.get("1k", {}).get("table") or entry.get("1k", {}).get("fss") or entry.get("wheel"))
        if not url:
            self._on_no_image(slot, table_name); return

        threading.Thread(target=self._fetch_image_for_slot,
                         args=(url, slot, table_name), daemon=True).start()

    def _fetch_image_for_slot(self, url, slot, table_name):
        """Background: download + prepare full + thumb images, then update UI."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VPXMergeTool/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img = img.rotate(-90, expand=True)

            # Try wheel
            wheel = None
            try:
                wurl = re.sub(r"1k/.*\.png$", "wheel.png", url)
                if wurl != url:
                    req2 = urllib.request.Request(wurl, headers={"User-Agent": "VPXMergeTool/1.0"})
                    with urllib.request.urlopen(req2, timeout=10) as r2:
                        wheel = Image.open(io.BytesIO(r2.read())).convert("RGBA")
            except Exception:
                wheel = None

            full  = img.copy()
            thumb = img.copy()
            thumb.thumbnail((196, 146), Image.Resampling.LANCZOS)

            self._preview_data[slot]["image"]  = full
            self._preview_data[slot]["wheel"]  = wheel
            self._preview_data[slot]["thumb"]  = thumb
            self._preview_data[slot]["loaded"] = True

            self.root.after(0, lambda s=slot: self._render_slot(s))
        except Exception:
            self.root.after(0, lambda s=slot, n=table_name: self._on_no_image(s, n))

    def _render_slot(self, slot):
        """Render slot: big view if single/zoomed, thumbnail if grid."""
        if slot >= len(self._preview_data): return
        data = self._preview_data[slot]
        n    = len(self._preview_data)

        if n == 1 or self._zoom_index == slot:
            # ── Full single view ──────────────────────────────────────────────
            self._render_single(slot)
        else:
            # ── Grid thumbnail ────────────────────────────────────────────────
            self._render_thumb(slot)

    def _render_single(self, slot):
        """Draw full-size image with wheel overlay onto the big canvas."""
        data  = self._preview_data[slot]
        img   = data.get("image")
        wheel = data.get("wheel")
        if not img: return

        self.preview_canvas.update_idletasks()
        cw = self.preview_canvas.winfo_width()  or 440
        ch = self.preview_canvas.winfo_height() or 490

        full = img.copy()
        full.thumbnail((cw - 24, ch - 24), Image.Resampling.LANCZOS)
        pf_w, pf_h = full.size

        composite = Image.new("RGBA", (cw, ch), (26, 26, 26, 255))
        px, py = (cw - pf_w)//2, (ch - pf_h)//2
        composite.paste(full, (px, py), full)

        if wheel:
            from PIL import ImageDraw
            ws = int(cw * 0.34)
            wimg = wheel.copy(); wimg = wimg.resize((ws, ws), Image.Resampling.LANCZOS)
            ww, wh = wimg.size
            wx, wy = (cw - ww)//2, ch - wh - 24
            shadow = Image.new("RGBA", (ww+8, wh+8), (0,0,0,0))
            ImageDraw.Draw(shadow).ellipse([0,0,ww+7,wh+7], fill=(0,0,0,120))
            composite.paste(shadow, (wx-4, wy-4), shadow)
            composite.paste(wimg, (wx, wy), wimg)

        photo = ImageTk.PhotoImage(composite)
        self.current_preview_image = photo
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(cw//2, ch//2, anchor="center", image=photo)
        ix, iy = (cw - pf_w)//2, (ch - pf_h)//2
        self.preview_canvas.create_rectangle(ix-2, iy-2, ix+pf_w+2, iy+pf_h+2,
                                              outline="#ffffff", width=2, fill="")
        self.preview_status.config(text="✓ Preview loaded", fg="#00ff00")

    def _render_thumb(self, slot):
        """Draw thumbnail image into a grid cell."""
        if slot >= len(self.thumb_cells): return
        data  = self._preview_data[slot]
        thumb = data.get("thumb")
        if not thumb: return
        canvas, lbl = self.thumb_cells[slot]
        photo = ImageTk.PhotoImage(thumb)
        while len(self.thumb_images) <= slot: self.thumb_images.append(None)
        self.thumb_images[slot] = photo
        cw = canvas.winfo_width()  or 200
        ch = canvas.winfo_height() or 150
        canvas.delete("all")
        canvas.create_image(cw//2, ch//2, anchor="center", image=photo)
        tw, th = thumb.size
        ix, iy = (cw-tw)//2, (ch-th)//2
        canvas.create_rectangle(ix-1, iy-1, ix+tw+1, iy+th+1,
                                 outline="#ffffff", width=1, fill="")

    def _on_no_image(self, slot, table_name):
        """No image available — show placeholder in the right context."""
        n = len(self._preview_data)
        if n == 1 or self._zoom_index == slot:
            self.show_placeholder_preview(table_name)
        else:
            if slot >= len(self.thumb_cells): return
            canvas, _ = self.thumb_cells[slot]
            canvas.delete("all")
            cw = canvas.winfo_width() or 200
            ch = canvas.winfo_height() or 150
            canvas.create_rectangle(4, 4, cw-4, ch-4, fill="#1a1a1a", outline="#2a3060")
            canvas.create_text(cw//2, ch//2, text="No Preview",
                               fill="#444466", font=("Arial", 8, "bold"), anchor="center")

    def _setup_thumb_cell(self, slot, table_name):
        """Set up grid cell label and click binding."""
        if slot >= len(self.thumb_cells): return
        canvas, lbl = self.thumb_cells[slot]
        short = (table_name[:26] + "…") if len(table_name) > 26 else table_name
        lbl.config(text=short)
        canvas.delete("all")
        cw = canvas.winfo_width() or 200; ch = canvas.winfo_height() or 150
        canvas.create_text(cw//2, ch//2, text="⏳",
                           font=("Arial", 18), fill="#ffcc00", anchor="center")
        canvas.bind("<Button-1>", lambda e, s=slot: self._preview_zoom(s))
        lbl.bind(   "<Button-1>", lambda e, s=slot: self._preview_zoom(s))

    def _preview_zoom(self, slot):
        """Click on grid thumbnail → show in big single view."""
        if slot >= len(self._preview_data): return
        self._zoom_index = slot
        data = self._preview_data[slot]
        # Switch to single view
        self.preview_grid_frame.pack_forget()
        self.preview_single_frame.pack(fill="both", expand=True)
        self.btn_back_preview.pack(side="right", padx=(0, 8))
        self.preview_title.config(text=data["table_name"][:38])
        self.preview_table_name.config(text=data["table_name"])
        self.preview_rom_name.config(text=f"ROM: {data['rom_name']}" if data.get("rom_name") else "")
        if data.get("loaded"):
            self._render_single(slot)
        else:
            self.preview_canvas.delete("all")
            cw = self.preview_canvas.winfo_width() or 440
            ch = self.preview_canvas.winfo_height() or 490
            self.preview_canvas.create_text(cw//2, ch//2, text="⏳ Loading...",
                                             fill="#ffcc00", font=("Arial", 14), anchor="center")

    def _preview_back(self):
        """Back from zoomed single view → return to grid."""
        self._zoom_index = None
        self.preview_single_frame.pack_forget()
        self.preview_grid_frame.pack(fill="both", expand=True, padx=6, pady=6)
        self.btn_back_preview.pack_forget()
        self.preview_title.config(text=f"{len(self._preview_data)} TABLES")
        self.preview_table_name.config(text="")
        self.preview_rom_name.config(text="")

    def show_placeholder_preview(self, table_name):
        """Draw placeholder on the big single canvas."""
        self.preview_canvas.delete("all")
        cw = self.preview_canvas.winfo_width()  or 440
        ch = self.preview_canvas.winfo_height() or 490
        self.preview_canvas.create_rectangle(10, 10, cw-10, ch-10,
                                             fill="#1a1a1a", outline="#00ccff", width=2)
        self.preview_canvas.create_text(cw//2, ch//2-20, text="No Preview\nAvailable",
                                        fill="#666666", font=("Arial", 11, "bold"), justify="center")
        short = (table_name[:32] + "…") if len(table_name) > 32 else table_name
        self.preview_canvas.create_text(cw//2, ch//2+30, text=short,
                                        fill="#00ccff", font=("Arial", 8),
                                        justify="center", width=cw-40)
        self.current_preview_image = None

    def browse_path(self, key, mode):
        path = filedialog.askdirectory()
        if path:
            if mode == "source": self.sources[key].set(path)
            else: self.target.set(path)
            self.save_settings()

    def extract_script(self, path):
        try:
            if path.lower().endswith('.vbs'):
                with open(path, 'rb') as f:
                    raw = f.read()
                # Auto-detect encoding by BOM — Windows VBS files are often UTF-16 LE
                if raw[:2] == b'\xff\xfe':
                    return raw.decode('utf-16-le', errors='ignore').encode('latin-1', errors='ignore')
                elif raw[:2] == b'\xfe\xff':
                    return raw.decode('utf-16-be', errors='ignore').encode('latin-1', errors='ignore')
                elif raw[:3] == b'\xef\xbb\xbf':
                    return raw[3:]  # strip UTF-8 BOM, rest is plain ASCII/latin-1
                return raw  # plain ASCII or latin-1, return as-is
            if olefile.isOleFile(path):
                with olefile.OleFileIO(path) as ole:
                    for s in ole.listdir():
                        if any(x in str(s).lower() for x in ["gamestru", "mac", "version"]): continue
                        with ole.openstream(s) as stream:
                            d = stream.read()
                            # Must contain "Option Explicit" or "Option Base" - the definitive script marker
                            # This prevents matching binary streams that happen to contain ' bytes
                            idx = d.lower().find(b'option ')
                            if idx == -1:
                                continue
                            # Verify this is actually text: 95%+ printable chars in first 200 bytes after marker
                            sample = d[idx:idx+200]
                            printable = sum(1 for b in sample if b >= 0x20 or b in (0x09, 0x0a, 0x0d))
                            if len(sample) > 0 and printable / len(sample) < 0.95:
                                continue  # binary stream, skip it
                            # Scan backwards from idx to include comment header before Option
                            start = idx
                            for back in range(idx - 1, max(idx - 100000, -1), -1):
                                b = d[back]
                                # Stop at any non-text byte (not tab, LF, CR, space, or printable ASCII/latin-1)
                                if b < 0x09 or (0x0e <= b <= 0x1f):
                                    start = back + 1
                                    # Walk forward to start of next line
                                    while start < idx and d[start] in (0x0a, 0x0d):
                                        start += 1
                                    break
                            else:
                                start = 0
                            raw = d[start:]
                            # Strip OLE stream padding and ENDB footer from the end
                            endb = raw.rfind(b'ENDB')
                            if endb != -1:
                                raw = raw[:endb].rstrip(b'\x00\x04')
                            else:
                                raw = raw.rstrip(b'\x00')
                            return raw
        except: pass
        return None

    def find_github_patch(self, table_name):
        """Search GitHub repo for matching patch file using fuzzy matching"""
        try:
            # GitHub API endpoint for repo contents
            api_url = "https://api.github.com/repos/jsm174/vpx-standalone-scripts/contents"
            
            # Get list of folders in the repo
            req = urllib.request.Request(api_url)
            req.add_header('User-Agent', 'VPX-Utility')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                folders = json.loads(response.read().decode())
            
            # Use the same fuzzy matching as media files
            table_base = os.path.splitext(table_name)[0]
            
            # Try to find matching folder
            best_match = None
            best_score = 0.0
            
            for item in folders:
                if item['type'] == 'dir':
                    folder_name = item['name']
                    
                    # Exact match (case-insensitive)
                    if folder_name.lower() == table_base.lower():
                        best_match = item
                        best_score = 1.0
                        break
                    
                    # Fuzzy match using media fuzzy scorer
                    score = _mfuzzy(table_base, folder_name)
                    if score > best_score:
                        best_score = score
                        best_match = item
            
            # Accept if score >= 50%
            if best_match and best_score >= 0.5:
                # Get contents of the matched folder
                folder_url = best_match['url']
                req = urllib.request.Request(folder_url)
                req.add_header('User-Agent', 'VPX-Utility')
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    files = json.loads(response.read().decode())
                
                # Find the .vbs file (not .original, not starting with "patch:")
                for file in files:
                    if file['type'] == 'file' and file['name'].endswith('.vbs'):
                        if not file['name'].endswith('.original') and not file['name'].startswith('patch:'):
                            return {
                                'found': True,
                                'name': file['name'],
                                'download_url': file['download_url'],
                                'folder': best_match['name'],
                                'score': best_score
                            }
            
            return {'found': False}
        
        except Exception as e:
            return {'found': False, 'error': str(e)}

    def download_patch(self, download_url, save_path):
        """Download patch file from GitHub"""
        try:
            # GitHub API already returns properly encoded URLs in download_url field
            # We just need to use it directly
            req = urllib.request.Request(download_url)
            req.add_header('User-Agent', 'VPX-Utility')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
            
            with open(save_path, 'wb') as f:
                f.write(content)
            
            return True
        except Exception as e:
            print(f"DEBUG: Patch download failed - {str(e)}")
            print(f"  URL: {download_url}")
            return False

    def auto_fix_script(self, script):
        """Auto-patch common VPX standalone incompatibilities."""
        if not script:
            return script, []

        fixes_applied = []
        fixed = script

        # 1. Fix WScript.Shell registry reads for NVRAM path
        if 'WScript.Shell' in fixed or 'WshShell' in fixed:
            # Replace GetNVramPath function
            import re
            pattern = r'Function GetNVramPath\(\).*?End [Ff]unction'
            if re.search(pattern, fixed, re.DOTALL | re.IGNORECASE):
                replacement = r'Function GetNVramPath()' + '\n    GetNVramPath = ".\\\\pinmame\\\\nvram\\\\"' + '\nEnd Function'
                fixed = re.sub(pattern, replacement, fixed, flags=re.DOTALL | re.IGNORECASE)
                fixes_applied.append("Fixed GetNVramPath() to use local pinmame folder")

            # Remove standalone WScript.Shell CreateObject lines (any variable name)
            lines = fixed.split('\n')
            new_lines = []
            for line in lines:
                # Match: Set <variable> = CreateObject("WScript.Shell")
                if re.search(r'Set\s+\w+\s*=\s*CreateObject\s*\(\s*["\']WScript\.Shell', line, re.IGNORECASE):
                    new_lines.append("    ' " + line.strip() + " ' REMOVED - not supported in VPX standalone")
                    if "Fixed WScript.Shell CreateObject" not in fixes_applied:
                        fixes_applied.append("Removed WScript.Shell CreateObject (not supported)")
                else:
                    new_lines.append(line)
            fixed = '\n'.join(new_lines)

        # 2. Comment out problematic registry reads
        if 'RegRead' in fixed:
            lines = fixed.split('\n')
            new_lines = []
            for line in lines:
                if 'RegRead' in line and '=' in line:
                    # Extract variable being assigned
                    var_match = re.search(r'(\w+)\s*=.*RegRead', line)
                    if var_match:
                        var_name = var_match.group(1)
                        new_lines.append("    ' " + line.strip() + " ' REMOVED")
                        new_lines.append(f'    {var_name} = ".\\\\\\\\pinmame\\\\\\\\nvram\\\\\\\\" \' Auto-fixed by VPX Utility')
                        if "Fixed RegRead" not in fixes_applied:
                            fixes_applied.append("Fixed RegRead to use local path")
                    else:
                        new_lines.append("    ' " + line.strip())
                else:
                    new_lines.append(line)
            fixed = '\n'.join(new_lines)

        # 3. Stub out other problematic COM objects
        problematic_objects = [
            ('SAPI.SpVoice', 'text-to-speech'),
            ('WMPlayer.OCX', 'Windows Media Player'),
        ]
        for obj, desc in problematic_objects:
            if obj in fixed:
                lines = fixed.split('\n')
                new_lines = []
                for line in lines:
                    if f'CreateObject("{obj}")' in line or f"CreateObject('{obj}')" in line:
                        new_lines.append("    ' " + line.strip() + f" ' REMOVED - {desc} not supported")
                        fixes_applied.append(f"Removed {desc} CreateObject")
                    else:
                        new_lines.append(line)
                fixed = '\n'.join(new_lines)

        # 4. Remove deprecated B2S.Server properties
        deprecated_props = ['ShowDMDOnly', 'ShowFrame', 'ShowTitle']
        b2s_fixed = False
        for prop in deprecated_props:
            if prop in fixed:
                lines = fixed.split('\n')
                new_lines = []
                for line in lines:
                    if f'.{prop}' in line and '=' in line:
                        new_lines.append("    ' " + line.strip() + " ' REMOVED - deprecated B2S property")
                        b2s_fixed = True
                    else:
                        new_lines.append(line)
                fixed = '\n'.join(new_lines)
        if b2s_fixed:
            fixes_applied.append("Removed deprecated B2S properties (ShowDMDOnly, ShowFrame, ShowTitle)")

        return fixed, fixes_applied


    def scan_and_copy_media(self, source_pup_path, table_name, target_table_folder, folder_name=None):
        """
        Scan and copy media files based on selected format.
        - VPinFE: Outputs to target_table_folder/medias/, named after table_name
        - Batocera: Outputs next to VPX file, named after folder_name
        - PuP Media: Outputs to target_table_folder/medias/, keeps original names/structure
        
        Args:
            source_pup_path: Path to PUP source folder
            table_name: VPX filename without extension (for matching source media)
            target_table_folder: Destination folder for table
            folder_name: Folder name (for Batocera naming) - defaults to table_name
        """
        if not self.include_media.get():
            return []
        if not source_pup_path:
            return []

        if folder_name is None:
            folder_name = table_name

        media_format = self.media_format.get()
        
        if media_format == "Batocera":
            # Batocera: media goes next to VPX file (in table folder root)
            # Skip if any Batocera media already exists
            if any(os.path.exists(os.path.join(target_table_folder, f"table{ext}"))
                   for ext in [".mp4", ".avi", ".png"]):
                return []
            return self._scan_batocera_media(source_pup_path, table_name, target_table_folder, folder_name)
        elif media_format == "PuP Media":
            # PuP Media: media in medias/ subfolder, keeps original names/structure
            media_dest = os.path.join(target_table_folder, "medias")
            if os.path.isdir(media_dest):
                return []
            return self._scan_original_media(source_pup_path, table_name, media_dest)
        else:  # VPinFE
            # VPinFE: media goes in medias/ subfolder
            media_dest = os.path.join(target_table_folder, "medias")
            if os.path.isdir(media_dest):
                return []
            return self._scan_vpinfe_media(source_pup_path, table_name, media_dest)

    def _scan_batocera_media(self, source_pup_path, table_name, media_dest, folder_name):
        """
        Batocera format: Same POPMedia source as VPinFE, simple fixed output names.
        Source: POPMedia/Visual Pinball X/Playfield, Menu, Backglass, etc.
        Output: table.mp4, backglass.mp4, dmd.mp4, wheel.png (simple fixed names)
        
        Uses table_name to MATCH source media.
        """
        parent = os.path.dirname(source_pup_path.rstrip('/\\'))
        popmedia = os.path.join(parent, "POPMedia", "Visual Pinball X")
        
        if not os.path.exists(popmedia):
            return []

        # Batocera output naming - simple fixed names
        media_mappings = [
            ("Playfield",    [".mp4", ".avi", ".f4v"],              "table"),       # table.mp4
            ("Backglass",    [".mp4", ".avi", ".f4v"],              "backglass"),   # backglass.mp4
            ("Backglass",    [".png", ".jpg", ".jpeg"],             "backglass"),   # backglass.png
            ("Menu",         [".mp4", ".avi", ".f4v"],              "dmd"),         # dmd.mp4
            ("Menu",         [".png", ".jpg", ".jpeg"],             "dmd"),         # dmd.png
            ("Wheel",        [".png", ".apng", ".jpg"],             "wheel"),       # wheel.png
            ("AudioLaunch",  [".mp3", ".wav"],                      "audiolaunch"), # audiolaunch.mp3
            ("Audio",        [".mp3", ".wav"],                      "audio"),       # audio.mp3
        ]

        copied = []

        for folder_type, extensions, target_base in media_mappings:
            src_folder = os.path.join(popmedia, folder_type)
            if not os.path.exists(src_folder):
                continue

            try:
                candidates = [f for f in os.listdir(src_folder)
                              if os.path.splitext(f)[1].lower() in extensions]
            except Exception:
                continue

            # Match source media using table_name (VPX filename)
            best_file, best_score = None, 0.0
            for fname in candidates:
                fbase = os.path.splitext(fname)[0]
                if fbase.lower() == table_name.lower():
                    best_file, best_score = fname, 1.0
                    break
                score = _mfuzzy(table_name, fbase)
                if score > best_score:
                    best_score, best_file = score, fname

            if not best_file or best_score < 0.5:
                continue

            ext = os.path.splitext(best_file)[1].lower()
            target_name = f"{target_base}{ext}"
            src_file = os.path.join(src_folder, best_file)
            dst_file = os.path.join(media_dest, target_name)

            # Skip if already copied
            if os.path.exists(dst_file):
                continue

            try:
                os.makedirs(media_dest, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                copied.append({
                    'original': f"{folder_type}/{best_file}",
                    'renamed':  target_name,
                    'score':    best_score,
                })
            except Exception:
                pass

        if copied:
            self._write_media_log(media_dest, folder_name, copied)
        return copied

    def _scan_original_media(self, source_pup_path, table_name, media_dest):
        """
        PuP Media format: Copy ALL media from POPMedia, keeping original names and folder structure.
        Source: POPMedia/Visual Pinball X/* (all subfolders)
        Output: medias/FolderName/originalname.ext
        
        Dynamically scans all subfolders and copies matching files.
        """
        parent = os.path.dirname(source_pup_path.rstrip('/\\'))
        popmedia = os.path.join(parent, "POPMedia", "Visual Pinball X")
        
        if not os.path.exists(popmedia):
            return []

        copied = []

        # Scan ALL subfolders in POPMedia
        try:
            all_folders = [d for d in os.listdir(popmedia) 
                          if os.path.isdir(os.path.join(popmedia, d))]
        except Exception:
            return []

        for folder_name in all_folders:
            src_folder = os.path.join(popmedia, folder_name)
            
            try:
                all_files = os.listdir(src_folder)
            except Exception:
                continue

            # Find best matching file by table name
            best_file, best_score = None, 0.0
            for fname in all_files:
                file_path = os.path.join(src_folder, fname)
                if not os.path.isfile(file_path):
                    continue
                
                fbase = os.path.splitext(fname)[0]
                # Exact match
                if fbase.lower() == table_name.lower():
                    best_file, best_score = fname, 1.0
                    break
                # Fuzzy match
                score = _mfuzzy(table_name, fbase)
                if score > best_score:
                    best_score, best_file = score, fname

            if not best_file or best_score < 0.5:
                continue

            # Copy to medias/FolderName/originalfilename.ext
            src_file = os.path.join(src_folder, best_file)
            dest_folder = os.path.join(media_dest, folder_name)
            dest_file = os.path.join(dest_folder, best_file)

            try:
                os.makedirs(dest_folder, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                copied.append({
                    'original': f"{folder_name}/{best_file}",
                    'renamed':  f"{folder_name}/{best_file}",
                    'score':    best_score,
                })
            except Exception:
                pass

        if copied:
            self._write_media_log(media_dest, table_name, copied)
        return copied

    def _scan_vpinfe_media(self, source_pup_path, table_name, media_dest):
        """
        VPinFE format: POPMedia/Visual Pinball X/subfolder structure
        Playfield/ Menu/ Loading/ etc.
        """
        parent = os.path.dirname(source_pup_path.rstrip('/\\'))
        popmedia = os.path.join(parent, "POPMedia", "Visual Pinball X")
        
        if not os.path.exists(popmedia):
            return []

        media_mappings = [
            ("Playfield",    [".mp4", ".avi", ".f4v"],   "table"),
            ("Menu",         [".mp4", ".avi", ".f4v"],   "fulldmd"),
            ("Loading",      [".mp4", ".avi", ".f4v"],   "loading"),
            ("Gameinfo",     [".png", ".jpg", ".jpeg"],  "flyer"),
            ("GameHelp",     [".png", ".jpg", ".jpeg"],  "rules"),
            ("Backglass",    [".mp4", ".avi", ".f4v"],   "bg"),
            ("AudioLaunch",  [".mp3", ".wav"],           "audiolaunch"),
            ("Audio",        [".mp3", ".wav"],           "audio"),
            ("Wheel",        [".png", ".apng", ".jpg"],  "wheel"),
        ]

        copied = []

        for folder_name, extensions, target_base in media_mappings:
            src_folder = os.path.join(popmedia, folder_name)
            if not os.path.exists(src_folder):
                continue

            try:
                candidates = [f for f in os.listdir(src_folder)
                              if os.path.splitext(f)[1].lower() in extensions]
            except Exception:
                continue

            best_file, best_score = None, 0.0
            for fname in candidates:
                fbase = os.path.splitext(fname)[0]
                if fbase.lower() == table_name.lower():
                    best_file, best_score = fname, 1.0
                    break
                score = _mfuzzy(table_name, fbase)
                if score > best_score:
                    best_score, best_file = score, fname

            if not best_file or best_score < 0.5:
                continue

            ext = os.path.splitext(best_file)[1].lower()
            target_name = f"{target_base}{ext}"
            src_file = os.path.join(src_folder, best_file)
            dst_file = os.path.join(media_dest, target_name)

            try:
                os.makedirs(media_dest, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                copied.append({
                    'original': f"{folder_name}/{best_file}",
                    'renamed':  target_name,
                    'score':    best_score,
                })
            except Exception:
                pass

        if copied:
            self._write_media_log(media_dest, table_name, copied)
        return copied

    def _write_media_log(self, media_dest, table_name, copied):
        """Write media_log.ini file"""
        try:
            with open(os.path.join(media_dest, "media_log.ini"), 'w', encoding='utf-8') as lf:
                lf.write(f"# Media Rename Log — {table_name}\n")
                lf.write(f"# Generated by VPXmerge\n")
                lf.write(f"# Original = Renamed\n\n")
                lf.write(f"[{table_name}]\n")
                for item in copied:
                    lf.write(f"{item['original']} = {item['renamed']}\n")
        except Exception:
            pass

    def _lookup_vps_id(self, table_name):
        """Look up VPS Table ID from table name using fuzzy matching"""
        if not hasattr(self, 'vpsdb_lookup') or not self.vpsdb_lookup:
            return None
        
        def normalize(s):
            s = s.lower()
            s = re.sub(r"[\'\u2019\u2018`]", "", s)
            s = re.sub(r"[^a-z0-9\s]", " ", s)
            return re.sub(r"\s+", " ", s).strip()
        
        raw = table_name.strip()
        nr = normalize(raw)
        clean = re.sub(r"\s*\(.*?\)", "", raw).strip()
        nc = normalize(clean)
        
        candidates = [raw.lower(), nr, clean.lower(), nc]
        
        # Try exact match first
        for candidate in candidates:
            if candidate in self.vpsdb_lookup:
                return self.vpsdb_lookup[candidate]
        
        # Fuzzy matching fallback: word-based similarity (same as preview)
        best_id, best_score = None, 0.0
        table_words = set(nc.split())
        
        for lk, lid in self.vpsdb_lookup.items():
            if len(lk) < 3: continue
            db_words = set(lk.split())
            
            # Word overlap
            common = table_words & db_words
            if common:
                score = len(common) / max(len(table_words), len(db_words))
                if score > best_score:
                    best_score = score
                    best_id = lid
        
        # Accept if confidence is high enough (50% match)
        if best_id and best_score >= 0.5:
            return best_id
        
        return None

    def audit_logic(self, mode):
        # Random pinball quotes for "Make Magic Happen"
        pinball_quotes = [
            "TILT! Just kidding... let's roll!",
            "Bumpers engaged, flippers ready!",
            "Time to rack up some high scores!",
            "Multi-ball mode: ACTIVATED!",
            "Nudge it real good!",
            "Extra ball earned! Let's go!",
            "Jackpot incoming!",
            "Skill shot lined up perfectly!",
            "The silver ball never lies!",
            "Flipper fingers ready!",
            "Lock and load those balls!",
            "Plunger pulled, magic initiated!",
            "Warning: Addictive gameplay ahead!",
            "Remember: It's all in the wrists!",
            "The ball is wild, the table is yours!",
            "Gravity? Never heard of her!",
            "Launching into pinball paradise!",
            "Table manners: Optional. Skill: Required!",
            "Keep your eye on the ball... literally!",
            "Free game? No, better... FREE FILES!"
        ]
        
        # Reset file stats
        self.file_stats = {
            'tables': 0, 'roms': 0, 'backglass': 0, 'altsound': 0, 'altcolor': 0, 
            'pup_packs': 0, 'music_tracks': 0, 'patches': 0, 'vbs_files': 0
        }
        
        t_dir, v_dir, p_dir, m_dir = [self.sources[k].get() for k in ["tables", "vpinmame", "pupvideos", "music"]]
        target_root = self.target.get()
        
        # Show progress bar for non-scan modes
        if mode != "scan":
            self.progress_frame.config(height=36, pady=4)
            self.progress_bar.pack(fill="x")
            self.progress_label.pack(anchor="w")
            self.progress_bar['value'] = 0
            self.progress_label.config(text="Initializing...")
        
        # Show random quote and progress message for full mode
        if mode == "full":
            quote = random.choice(pinball_quotes)
            self.log_audit(quote, "found")
            self.log_audit("--- COPYING IN PROGRESS ---", "white")
            self.log_audit("")
        elif mode == "patch":
            self.log_audit("🔍 SEARCHING FOR PATCHES...", "white")
            self.log_audit("")
        elif mode == "fix":
            self.log_audit("🔧 AUTO-FIXING SCRIPT FOR VPX STANDALONE...", "white")
            self.log_audit("")
        
        total_files = len(self.vpx_files)
        
        for idx, f in enumerate(self.vpx_files):
            fname = os.path.basename(f); v_base = os.path.splitext(fname)[0]
            script_raw = self.extract_script(f)  # raw bytes - used for writing carbon copy
            # Decode to string for all regex/text operations
            script = script_raw.decode('latin-1', errors='ignore') if isinstance(script_raw, bytes) else (script_raw or '')
            if not script and mode == "scan":
                self.log_audit(f"⚠ Could not read script from: {fname}", "missing")
            table_dest = os.path.join(target_root, v_base)
            
            # Update progress
            if mode != "scan":
                progress = ((idx + 1) / total_files) * 100
                self.progress_bar['value'] = progress
                self.progress_label.config(text=f"Processing {idx + 1}/{total_files}: {v_base}")
                self.root.update_idletasks()
            
            # Setup Folder Structure — patch saves next to source, full/fix need table subfolder
            if mode in ["full", "fix"]: os.makedirs(table_dest, exist_ok=True)
            
            # Extract ROM name for preview
            rom_for_preview = None
            if script:
                rom_for_preview = _detect_rom(script)
            
            # Update preview with table info
            self.root.after(0, lambda tn=v_base, rn=rom_for_preview: self.update_preview(tn, rn))
            
            # Visual separator for table
            if mode == "scan": 
                self.log_separator("double")
                # Look up VPS ID
                vps_id = self._lookup_vps_id(v_base)
                if vps_id:
                    self.log_audit(f"  Table: {fname} ( VPS Table ID: {vps_id} )", "table_name")
                else:
                    self.log_audit(f"  Table: {fname}", "table_name")
                self.log_separator("single")
            elif mode == "full": 
                shutil.copy2(f, os.path.join(table_dest, fname))
                self.file_stats['tables'] += 1
                
                # Copy media files if enabled
                if self.include_media.get():
                    media_dest_check = os.path.join(table_dest, "medias")
                    if os.path.isdir(media_dest_check):
                        self.log_audit(f"10-MEDIA: SKIPPED (medias/ already exists)", "yellow")
                    else:
                        media_copied = self.scan_and_copy_media(p_dir, v_base, table_dest, os.path.basename(table_dest))
                        if media_copied:
                            self.log_audit(f"10-MEDIA: {len(media_copied)} files copied → medias/", "found")
                            for item in media_copied:
                                self.log_audit(f"   → {item['original']} → {item['renamed']}  ({item['score']:.0%})", "found")
                            self.file_stats['media'] = self.file_stats.get('media', 0) + len(media_copied)
                        else:
                            self.log_audit(f"10-MEDIA: No matching media found", "missing")
            elif mode == "patch": 
                self.log_separator("double")
                # Look up VPS ID
                vps_id = self._lookup_vps_id(v_base)
                if vps_id:
                    self.log_audit(f"  Table: {fname} ( VPS Table ID: {vps_id} )", "table_name")
                else:
                    self.log_audit(f"  Table: {fname}", "table_name")
                self.log_separator("single")

            # 1. ROM Logic — detect before backglass so audit order matches numbering
            rom = None
            if script and mode not in ["patch", "fix"]:
                rom = _detect_rom(script)
                if rom:
                    if mode == "scan": self.log_audit(f"1-ROM: {rom} (DETECTED IN SCRIPT ✓)", "found")
                    if not v_dir:
                        if mode == "scan": self.log_audit(f"   → zip lookup skipped (VPINMAME path not set)", "missing")
                    else:
                        # Search common rom locations: roms/ subfolder, and root vpinmame folder
                        r_src = None
                        for candidate in [
                            os.path.join(v_dir, "roms", f"{rom}.zip"),
                            os.path.join(v_dir, f"{rom}.zip"),
                        ]:
                            if os.path.exists(candidate):
                                r_src = candidate
                                break
                        if r_src:
                            if mode == "scan": self.log_audit(f"   → zip FOUND: {os.path.basename(r_src)}", "found")
                            elif mode == "full":
                                rd = os.path.join(table_dest, "pinmame", "roms")
                                os.makedirs(rd, exist_ok=True)
                                shutil.copy2(r_src, rd)
                                self.file_stats['roms'] += 1
                        else:
                            if mode == "scan": self.log_audit(f"   → zip NOT FOUND in vpinmame/roms/", "missing")
                else:
                    if mode == "scan": self.log_audit("1-ROM: NOT DETECTED IN SCRIPT", "missing")

            # 2. Backglass — purely file-based, no script needed
            if mode != "patch":
                # .directb2s always has exact same name as .vpx
                b2s_src = None
                b2s_fname = None
                file_dir = os.path.dirname(f)
                b2s_base = v_base

                # For .vbs drops: find the .vpx in same folder to get real base name
                if f.lower().endswith('.vbs'):
                    try:
                        for entry in os.scandir(file_dir):
                            if entry.name.lower().endswith('.vpx'):
                                b2s_base = os.path.splitext(entry.name)[0]
                                break
                    except Exception:
                        pass

                # Look in same folder as the file, then t_dir as fallback
                for search_dir in [file_dir, t_dir]:
                    if not search_dir:
                        continue
                    candidate = os.path.join(search_dir, f"{b2s_base}.directb2s")
                    if os.path.exists(candidate):
                        b2s_src, b2s_fname = candidate, f"{b2s_base}.directb2s"
                        break
                if b2s_src:
                    if mode == "scan": self.log_audit(f"2-BACKGLASS: {b2s_fname} (DETECTED)", "found")
                    elif mode == "full":
                        shutil.copy2(b2s_src, os.path.join(table_dest, b2s_fname))
                        self.file_stats['backglass'] += 1
                else:
                    if mode == "scan": self.log_audit("2-BACKGLASS: NOT FOUND", "missing")

                # 3. UltraDMD / FlexDMD Detection
                uses_ultradmd = (re.search(r'UltraDMDTimer\.Enabled\s*=\s*1', script, re.IGNORECASE) or
                                 re.search(r'UseUltraDMD\s*=\s*1',              script, re.IGNORECASE))
                uses_flexdmd  = (re.search(r'UseFlexDMD\s*=\s*1',   script, re.IGNORECASE) or
                                 re.search(r'Dim\s+FlexDMD\b',       script, re.IGNORECASE) or
                                 re.search(r'Sub\s+FlexDMD_init\b',  script, re.IGNORECASE) or
                                 re.search(r'\.ProjectFolder\s*=',   script, re.IGNORECASE))

                if uses_ultradmd or uses_flexdmd:
                    dmd_found = False
                    dmd_type  = "UltraDMD" if uses_ultradmd else "FlexDMD"

                    # Extract Const TableName = "Name of the Table" from VBS
                    tname_match = re.search(r'(?:Const\s+)?TableName\s*=\s*"([^"]+)"', script, re.IGNORECASE)
                    vbs_table_name = tname_match.group(1).strip() if tname_match else None

                    # For FlexDMD: extract folder name from ProjectFolder line
                    # Handles: .ProjectFolder = "./FolderName/"
                    #      or: .ProjectFolder = "./" & "FolderName" & "/"
                    flex_folder = None
                    if uses_flexdmd:
                        # Pattern 1: .ProjectFolder = "./FolderName/"
                        pf_match = re.search(r'ProjectFolder\s*=\s*"\./([^"/]+)/"', script, re.IGNORECASE)
                        if pf_match:
                            flex_folder = pf_match.group(1).strip()
                        else:
                            # Pattern 2: .ProjectFolder = "./" & "FolderName" & "/"
                            pf_match = re.search(r'ProjectFolder\s*=.*?"\./?"\s*&\s*"([^"]+)"', script, re.IGNORECASE)
                            if pf_match:
                                flex_folder = pf_match.group(1).strip()

                    # Build search names in priority order
                    search_names = []
                    if flex_folder:
                        search_names.append(flex_folder)   # exact folder from ProjectFolder
                    if vbs_table_name:
                        search_names.append(vbs_table_name)
                    search_names.append(v_base)
                    if rom:
                        search_names.append(rom)

                    # DMD folder lives next to the .vpx - search file_dir first, then t_dir as fallback
                    dmd_search_roots = list(dict.fromkeys([os.path.dirname(f), t_dir]))
                    # Try all known extensions INCLUDING bare name (e.g. MFDOOMDMD has no extension)
                    dmd_extensions = ['.FlexDMD', '.UltraDMD', '.DMD', 'DMD', '']

                    for search_name in search_names:
                        if dmd_found:
                            break
                        for ext in dmd_extensions:
                            if dmd_found:
                                break
                            dmd_folder = f"{search_name}{ext}"
                            for dmd_search_root in dmd_search_roots:
                                dmd_src = os.path.join(dmd_search_root, dmd_folder)
                                if os.path.exists(dmd_src) and os.path.isdir(dmd_src):
                                    dmd_found = True
                                    if mode == "scan":
                                        self.log_audit(f"3-ULTRADMD/FLEXDMD: {dmd_folder} (DETECTED)", "found")
                                    elif mode == "full":
                                        shutil.copytree(dmd_src, os.path.join(table_dest, dmd_folder), dirs_exist_ok=True)
                                        self.file_stats['ultradmd'] = self.file_stats.get('ultradmd', 0) + 1
                                    break

                    if not dmd_found:
                        tried = [f"{n}{e}" for n in search_names for e in dmd_extensions]
                        if flex_folder:
                            pass
                        if vbs_table_name:
                            pass

                # 4. AltSound / 5. AltColor / 6. PuP-Pack
                if rom:
                    for folder, label, num in [("altsound", "4-ALTSOUND", "full"), ("altcolor", "5-ALTCOLOR", "full")]:
                        src = os.path.join(v_dir, folder, rom)
                        if os.path.exists(src):
                            if mode == "scan": self.log_audit(f"{label}: {rom} (DETECTED)", "found")
                            elif mode == "full": 
                                shutil.copytree(src, os.path.join(table_dest, "pinmame", folder, rom), dirs_exist_ok=True)
                                if folder == "altsound": self.file_stats['altsound'] += 1
                                else: self.file_stats['altcolor'] += 1
                        else:
                            if mode == "scan": self.log_audit(f"{label}: NOT FOUND", "missing")
                
                # PUP pack: try rom name first, then v_base as fallback
                pup_found = False
                for pup_name in ([rom, v_base] if rom and rom != v_base else [v_base]):
                    if not pup_name: continue
                    pup_src = os.path.join(p_dir, pup_name)
                    if os.path.exists(pup_src):
                        if mode == "scan": self.log_audit(f"6-PUP-PACK: {pup_name} (DETECTED)", "found")
                        elif mode == "full":
                            shutil.copytree(pup_src, os.path.join(table_dest, "pupvideos", pup_name), dirs_exist_ok=True)
                            self.file_stats['pup_packs'] += 1
                        pup_found = True
                        break
                if not pup_found:
                    if mode == "scan": self.log_audit("6-PUP-PACK: NOT FOUND", "missing")

                # 7. Music Logic (Flat Export to 'music' folder)
                # 8. Music — collect all subfolder references from PlayMusic calls
                # Handles both:
                #   PlayMusic "OBWAT/OBWAT1.mp3"  -> subfolder OBWAT in m_dir
                #   PlayMusic "track.mp3"          -> flat file in m_dir root or named subfolder
                m_found = False
                f_folders = set()  # subfolder names to search for in m_dir

                # Extract subfolder from PlayMusic "folder/file.mp3" or PlayMusic "folder\file.mp3"
                pm_matches = re.findall(r'PlayMusic\s*["\']?([^"\',;\r\n]+)', script, re.IGNORECASE)
                for path in pm_matches:
                    path = path.strip().strip('"\'\\/ ')
                    # Check for subfolder separator (/ or \)
                    for sep in ['/', '\\\\', '\\']:
                        if sep in path:
                            folder = path.split(sep)[0].strip()
                            if folder:
                                f_folders.add(folder)
                            break

                # Also check MusicSubDirectory and fallback names
                subdir_m = re.search(r'MusicSubDirectory\s*=\s*"([^"]+)"', script, re.IGNORECASE)
                if subdir_m:
                    f_folders.add(subdir_m.group(1).replace("\\", "").strip())
                # Fallback: rom name and v_base as folder names
                f_folders.add(v_base)
                if rom:
                    f_folders.add(rom)

                if os.path.exists(m_dir):
                    all_sub = [d for d in os.listdir(m_dir) if os.path.isdir(os.path.join(m_dir, d))]
                    for target in sorted(f_folders):
                        for real in all_sub:
                            if real.lower() == target.lower():
                                m_found = True
                                full_m = os.path.join(m_dir, real)
                                music_files = sorted([trk for trk in os.listdir(full_m) if trk.lower().endswith(('.mp3', '.ogg', '.wav', '.flac'))])
                                if mode == "scan":
                                    files_str = ', '.join(music_files)
                                    self.log_audit(f"8-MUSIC: (DETECTED) {real}/ [{files_str}]", "found")
                                elif mode == "full":
                                    # Preserve subfolder structure: music/OBWAT/*.mp3
                                    dest_music = os.path.join(table_dest, "music", real)
                                    os.makedirs(dest_music, exist_ok=True)
                                    for trk in music_files:
                                        shutil.copy2(os.path.join(full_m, trk), dest_music)
                                    self.file_stats['music_tracks'] += len(music_files)
                if mode == "scan" and not m_found: self.log_audit("8-MUSIC: NOT FOUND", "missing")

                # 9. Patch Lookup (GitHub) - runs in all modes
                if self.enable_patch_lookup.get():
                    patch_result = self.find_github_patch(fname)
                    if patch_result['found']:
                        patch_name = patch_result['name']
                        if mode == "scan":
                            self.log_audit(f"9-PATCH: {patch_name} (DETECTED)", "found")
                        elif mode in ["full", "patch"]:
                            # For patch mode: save next to the source file
                            # For full mode: save inside the export table folder
                            if mode == "patch":
                                save_dir = os.path.dirname(f)
                            else:
                                save_dir = table_dest
                                os.makedirs(save_dir, exist_ok=True)
                            patch_save_path = os.path.join(save_dir, f"{v_base}.vbs")
                            if self.download_patch(patch_result['download_url'], patch_save_path):
                                self.log_audit(f"9-PATCH: {patch_name} (DOWNLOADED)", "found")
                                self.log_audit(f"   → Saved: {patch_save_path}", "found")
                                self.file_stats['patches'] += 1
                            else:
                                self.log_audit(f"9-PATCH: Download FAILED for {patch_name}", "missing")
                    else:
                        if mode == "scan":
                            self.log_audit("9-PATCH: NOT FOUND", "missing")
                        elif mode == "patch":
                            self.log_audit("9-PATCH: NOT FOUND", "missing")
                else:
                    if mode == "scan":
                        self.log_audit("9-PATCH: LOOKUP DISABLED", "missing")
                    elif mode == "patch":
                        self.log_audit("9-PATCH: LOOKUP IS DISABLED (Enable checkbox)", "missing")

                # VBS Creator
                if mode == "vbs":
                    vbs_path = os.path.join(table_dest, f"{v_base}.vbs")
                    if script_raw and len(script_raw) > 0:
                        raw_out = script_raw if isinstance(script_raw, bytes) else script.encode('latin-1', errors='replace')
                        raw_out = raw_out.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
                        os.makedirs(table_dest, exist_ok=True)
                        with open(vbs_path, "wb") as vf:
                            vf.write(raw_out)
                        self.log_audit(f"VBS CREATED: {v_base}.vbs ({len(raw_out):,} bytes)", "found")
                        self.file_stats['vbs_files'] += 1
                    else:
                        self.log_audit(f"VBS FAILED: could not extract script from {fname}", "missing")

                # Script Auto-Fixer
                if mode == "fix":
                    if script:
                        fixed_script, fixes = self.auto_fix_script(script)
                        if fixes:
                            # Copy VPX to target subfolder and save fixed VBS next to it
                            vpx_dest = os.path.join(table_dest, fname)
                            fix_path = os.path.join(table_dest, f"{v_base}.vbs")
                            # Only copy VPX if source and destination are different
                            if os.path.abspath(f) != os.path.abspath(vpx_dest):
                                shutil.copy2(f, vpx_dest)
                            with open(fix_path, "w", encoding='latin-1', errors='replace') as vf:
                                vf.write(fixed_script)
                            self.log_audit(f"✓ FIXED: {v_base}.vbs", "found")
                            for fix in fixes:
                                self.log_audit(f"   • {fix}", "found")
                            self.log_audit(f"   → VPX copied to: {table_dest}/", "found")
                            self.log_audit(f"   → Fixed VBS saved next to VPX", "found")
                            self.file_stats['vbs_files'] += 1
                        else:
                            self.log_audit(f"✓ NO ISSUES DETECTED in {fname}", "yellow")
                    else:
                        self.log_audit(f"✗ Could not read script from {fname}", "missing")

            if mode == "scan": 
                self.log_separator("bottom")
                self.log_audit("")
        self.root.after(0, self.reset_ui)
        
        # Hide progress bar — collapse frame back to 1px, no layout shift
        if mode != "scan":
            self.progress_bar.pack_forget()
            self.progress_label.pack_forget()
            self.progress_frame.config(height=1, pady=0)
        
        if mode != "scan" and target_root:
            self.log_audit("")
            # Display summary box
            self.log_separator("double")
            self.log_audit("                    📊 OPERATION SUMMARY", "yellow")
            self.log_separator("single")
            if self.file_stats['tables'] > 0:
                self.log_audit(f"  Tables Copied: {self.file_stats['tables']}", "found")
            if self.file_stats['roms'] > 0:
                self.log_audit(f"  ROMs Copied: {self.file_stats['roms']}", "found")
            if self.file_stats['backglass'] > 0:
                self.log_audit(f"  Backglasses: {self.file_stats['backglass']}", "found")
            if self.file_stats.get('ultradmd', 0) > 0:
                self.log_audit(f"  UltraDMD/FlexDMD Packs: {self.file_stats['ultradmd']}", "found")
            if self.file_stats['altsound'] > 0:
                self.log_audit(f"  AltSound Packs: {self.file_stats['altsound']}", "found")
            if self.file_stats['altcolor'] > 0:
                self.log_audit(f"  AltColor Packs: {self.file_stats['altcolor']}", "found")
            if self.file_stats['pup_packs'] > 0:
                self.log_audit(f"  PuP-Packs: {self.file_stats['pup_packs']}", "found")
            if self.file_stats['music_tracks'] > 0:
                self.log_audit(f"  Music Tracks: {self.file_stats['music_tracks']}", "found")
            if self.file_stats['patches'] > 0:
                self.log_audit(f"  Patches Downloaded: {self.file_stats['patches']}", "found")
            if self.file_stats['vbs_files'] > 0:
                self.log_audit(f"  VBS Files Created: {self.file_stats['vbs_files']}", "found")
            
            total_items = sum(self.file_stats.values())
            self.log_separator("single")
            self.log_audit(f"  TOTAL ITEMS PROCESSED: {total_items}", "yellow")
            self.log_separator("bottom")
            self.log_audit("")
            self.log_audit("--- TASK COMPLETED --- ENJOY!", "yellow")
            subprocess.run(["open", target_root])

    def handle_drop(self, event):
        self.clear_list()
        self.drop_hint.place_forget()  # hide drop hint once file is dropped
        # splitlist handles brace-wrapped paths; strip any residual {} for safety
        try:
            raw_files = self.root.tk.splitlist(event.data)
        except Exception:
            raw_files = event.data.split()
        files = []
        for f in raw_files:
            f = f.strip('{}').strip()
            # Handle paths that still have braces around them (spaces/parens in name)
            if f.startswith('{') and f.endswith('}'):
                f = f[1:-1]
            files.append(f)
        self.vpx_files = [f for f in files if f.lower().endswith(('.vpx', '.vbs'))]
        self.audit_logic("scan")

    def start_thread(self, mode):
        # Validate target folder is set for operations that need it
        if mode in ["full", "vbs", "fix"] and not self.target.get().strip():
            self.log_audit("⚠ Please set an Export Target folder before running.", "missing")
            return
        self.btn_full.config(state="disabled")
        self.btn_vbs.config(state="disabled")
        self.btn_fix.config(state="disabled")

        def _run():
            try:
                self.audit_logic(mode)
            except Exception as e:
                self.root.after(0, lambda: self.log_audit(f"⚠ Unexpected error: {e}", "missing"))
            finally:
                self.root.after(0, self.reset_ui)

        threading.Thread(target=_run, daemon=True).start()

    def reset_ui(self):
        if self.vpx_files:
            self.btn_full.config(state="normal")
            self.btn_fix.config(state="normal")
            # VBS export only makes sense for .vpx files (extracts embedded script)
            # For .vbs source files the file IS already the script
            all_vbs = all(f.lower().endswith('.vbs') for f in self.vpx_files)
            self.btn_vbs.config(state="disabled" if all_vbs else "normal")

    def clear_list(self):
        self.vpx_files = []
        self.audit_list.config(state="normal")
        self.audit_list.delete('1.0', tk.END)
        self.audit_list.config(state="disabled")
        self.btn_full.config(state="disabled")
        self.btn_vbs.config(state="disabled")
        self.btn_fix.config(state="disabled")
        # Show drop hint again
        try:
            self.drop_hint.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass
        
        # Reset preview — back to single view, clear all state
        self._preview_data = []
        self._zoom_index   = None
        self.thumb_images  = []
        self.current_preview_image = None
        for c, lbl in self.thumb_cells:
            c.delete("all"); lbl.config(text="")
        self.preview_grid_frame.pack_forget()
        self.preview_single_frame.pack(fill="both", expand=True)
        self.btn_back_preview.pack_forget()
        self.preview_canvas.delete("all")
        self.preview_title.config(text="TABLE PREVIEW")
        self.preview_table_name.config(text="")
        self.preview_rom_name.config(text="")
        self.preview_status.config(text="Drop a .vpx file to preview", fg="#888888")

    def save_settings(self):
        data = {"sources": {k: v.get() for k, v in self.sources.items()}, "target": self.target.get()}
        with open(self.config_file, "w") as f: json.dump(data, f)

if __name__ == "__main__":
    root = TkinterDnD.Tk(); app = VPXStandaloneMergingUtility(root); root.mainloop()
