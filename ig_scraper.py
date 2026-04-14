"""
Instagram Profile Scraper - wyszukuje profile trenerów personalnych
przez Google Search (widoczna przeglądarka, wpisywanie jak człowiek).

Uruchomienie: python ig_scraper.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import os
import re
import time
import random
import csv
import json
from dataclasses import dataclass
from urllib.parse import unquote

# ─── DANE: WOJEWÓDZTWA I MIASTA ─────────────────────────────────────────────

SEO_REGIONS = [
    {"name": "Podlaskie", "cities": ["Augustów","Białystok","Bielsk Podlaski","Brańsk","Choroszcz","Ciechanowiec","Czarna Białostocka","Czyżew","Drohiczyn","Goniądz","Grajewo","Hajnówka","Jedwabne","Kleszczele","Kolno","Knyszyn","Łapy","Łomża","Mońki","Rajgród","Sejny","Siemiatycze","Sokółka","Supraśl","Suwałki","Szczuczyn","Tykocin","Wasilków","Zabłudów","Zambrów"]},
    {"name": "Pomorskie", "cities": ["Brusy","Bytów","Chojnice","Czarna Woda","Czarne","Człuchów","Debrzno","Dzierzgoń","Gdańsk","Gdynia","Hel","Jastarnia","Kartuzy","Kościerzyna","Krynica Morska","Kwidzyn","Lębork","Malbork","Miastko","Nowy Dwór Gdański","Pelplin","Prabuty","Puck","Reda","Rumia","Skarszewy","Słupsk","Sopot","Starogard Gdański","Sztum","Tczew","Ustka","Wejherowo","Władysławowo"]},
    {"name": "Śląskie", "cities": ["Będzin","Bielsko-Biała","Bieruń","Blachownia","Bytom","Chorzów","Cieszyn","Czeladź","Czechowice-Dziedzice","Czerwionka-Leszczyny","Dąbrowa Górnicza","Gliwice","Imielin","Jastrzębie-Zdrój","Jaworzno","Kalety","Katowice","Knurów","Koziegłowy","Krzanowice","Krzepice","Kuźnia Raciborska","Lędziny","Lubliniec","Łaziska Górne","Miasteczko Śląskie","Mikołów","Myszków","Orzesze","Piekary Śląskie","Pilica","Poręba","Pszczyna","Pyskowice","Racibórz","Radlin","Ruda Śląska","Rybnik","Rydułtowy","Siemianowice Śląskie","Skoczów","Sławków","Sosnowiec","Sośnicowice","Strumień","Szczyrk","Świętochłowice","Tarnowskie Góry","Toszek","Tychy","Ustroń","Wilamowice","Wisła","Wodzisław Śląski","Wojkowice","Zabrze","Zawiercie","Żory","Żywiec"]},
    {"name": "Świętokrzyskie", "cities": ["Bodzentyn","Busko-Zdrój","Chęciny","Chmielnik","Daleszyce","Jędrzejów","Kazimierza Wielka","Kielce","Koprzywnica","Końskie","Kunów","Łagów","Małogoszcz","Opatów","Osiek","Ostrowiec Świętokrzyski","Pińczów","Połaniec","Sandomierz","Skalbmierz","Skarżysko-Kamienna","Starachowice","Staszów","Suchedniów","Wąchock","Wiślica"]},
    {"name": "Warmińsko-Mazurskie", "cities": ["Bartoszyce","Biała Piska","Bisztynek","Braniewo","Dobre Miasto","Elbląg","Ełk","Frombork","Giżycko","Górowo Iławeckie","Iława","Jeziorany","Kętrzyn","Kisielice","Lidzbark","Lidzbark Warmiński","Lubawa","Mikołajki","Miłakowo","Miłomłyn","Mrągowo","Nidzica","Nowe Miasto Lubawskie","Olecko","Olsztyn","Orneta","Ostróda","Pasłęk","Pieniężno","Ruciane-Nida","Sępopol","Susz","Szczytno","Tolkmicko","Węgorzewo"]},
    {"name": "Wielkopolskie", "cities": ["Bojanowo","Borek Wielkopolski","Budzyń","Chodzież","Czarnków","Czempiń","Dąbie","Dobra","Dolsk","Gniezno","Gostyń","Grabów nad Prosną","Grodzisk Wielkopolski","Jaraczewo","Jarocin","Kalisz","Kępno","Kleczew","Koło","Konin","Kościan","Krotoszyn","Krzywiń","Krzyż Wielkopolski","Leszno","Lwówek","Margonin","Międzychód","Mikstat","Mosina","Murowana Goślina","Nekla","Nowy Tomyśl","Oborniki","Odolanów","Opalenica","Ostrów Wielkopolski","Ostrzeszów","Pleszew","Poznań","Puszczykowo","Pyzdry","Rakoniewice","Rawicz","Rogoźno","Sieraków","Słupca","Stawiszyn","Sulmierzyce","Szamocin","Szamotuły","Ślesin","Śmigiel","Tuliszków","Turek","Ujście","Wągrowiec","Wieleń","Wielichowo","Wolsztyn","Września","Wyrzysk","Zbąszyń","Złotów"]},
    {"name": "Zachodniopomorskie", "cities": ["Barlinek","Białogard","Borne Sulinowo","Chociwel","Chojna","Darłowo","Dobra","Drawno","Drawsko Pomorskie","Dziwnów","Goleniów","Gryfice","Gryfino","Ińsko","Kamień Pomorski","Karlino","Kołobrzeg","Koszalin","Łobez","Maszewo","Mielno","Międzyzdroje","Myślibórz","Nowe Warpno","Połczyn-Zdrój","Polanów","Pyrzyce","Recz","Resko","Sianów","Sławno","Stargard","Stepnica","Suchań","Szczecin","Szczecinek","Świdwin","Świnoujście","Trzcińsko-Zdrój","Trzebiatów","Tychowo","Wałcz","Węgorzyno","Wolin","Złocieniec"]},
    {"name": "Dolnośląskie", "cities": ["Bardo","Bielawa","Bierutów","Bogatynia","Bolesławiec","Bolków","Brzeg Dolny","Chocianów","Chojnów","Duszniki-Zdrój","Dzierżoniów","Głogów","Głuszyca","Góra","Jawor","Jedlina-Zdrój","Jelcz-Laskowice","Kamienna Góra","Karpacz","Kowary","Kudowa-Zdrój","Legnica","Leśna","Lubań","Lubawka","Lubin","Lwówek Śląski","Malczyce","Milicz","Nowa Ruda","Oleśnica","Oława","Piechowice","Pieńsk","Polanica-Zdrój","Polkowice","Prusice","Przemków","Sobótka","Stronie Śląskie","Strzegom","Syców","Szklarska Poręba","Ścinawa","Środa Śląska","Świdnica","Świebodzice","Trzebnica","Twardogóra","Wałbrzych","Wąsosz","Węgliniec","Wleń","Wołów","Wrocław","Ząbkowice Śląskie","Zgorzelec","Ziębice","Złotoryja"]},
    {"name": "Kujawsko-Pomorskie", "cities": ["Aleksandrów Kujawski","Barcin","Bydgoszcz","Chełmno","Chełmża","Ciechocinek","Dobrzyń nad Wisłą","Golub-Dobrzyń","Górzno","Grudziądz","Inowrocław","Jabłonowo Pomorskie","Janikowo","Kamień Krajeński","Koronowo","Kowalewo Pomorskie","Kruszwica","Lipno","Mogilno","Mrocza","Nakło nad Notecią","Nieszawa","Nowe","Pakość","Piotrków Kujawski","Radziejów","Rypin","Solec Kujawski","Strzelno","Świecie","Toruń","Tuchola","Wąbrzeźno","Więcbork","Włocławek","Żnin"]},
    {"name": "Lubelskie", "cities": ["Annopol","Bełżyce","Biała Podlaska","Biłgoraj","Chełm","Dęblin","Frampol","Hrubieszów","Janów Lubelski","Józefów","Kazimierz Dolny","Kock","Kraśnik","Krasnobród","Krasnystaw","Łaszczów","Lubartów","Lublin","Łuków","Nałęczów","Opole Lubelskie","Ostrów Lubelski","Parczew","Piaski","Poniatowa","Puławy","Radzyń Podlaski","Rejowiec Fabryczny","Ryki","Świdnik","Szczebrzeszyn","Tarnogród","Terespol","Tomaszów Lubelski","Tyszowce","Włodawa","Zamość","Zwierzyniec"]},
    {"name": "Lubuskie", "cities": ["Babimost","Bytom Odrzański","Czerwieńsk","Dąbie","Dobiegniew","Gorzów Wielkopolski","Gozdnica","Iłowa","Jasień","Krosno Odrzańskie","Kostrzyn nad Odrą","Kożuchów","Lubsko","Łęknica","Małomice","Międzyrzecz","Nowa Sól","Ośno Lubuskie","Rzepin","Skwierzyna","Słubice","Strzelce Krajeńskie","Sulechów","Szlichtyngowa","Świebodzin","Torzym","Trzciel","Wschowa","Zielona Góra","Żagań","Żary"]},
    {"name": "Łódzkie", "cities": ["Aleksandrów Łódzki","Bełchatów","Biała Rawska","Błaszki","Brzeziny","Drzewica","Działoszyn","Głowno","Kamieńsk","Koluszki","Konstantynów Łódzki","Krośniewice","Kutno","Łask","Łęczyca","Łowicz","Łódź","Opoczno","Ozorków","Pajęczno","Piotrków Trybunalski","Poddębice","Przedbórz","Radomsko","Rawa Mazowiecka","Sieradz","Skierniewice","Sulejów","Szadek","Tomaszów Mazowiecki","Tuszyn","Uniejów","Warta","Wieluń","Zduńska Wola","Zgierz","Żychlin"]},
    {"name": "Małopolskie", "cities": ["Alwernia","Andrychów","Bochnia","Brzesko","Bukowno","Chełmek","Chrzanów","Ciężkowice","Czchów","Dąbrowa Tarnowska","Dobczyce","Gorlice","Jordanów","Kalwaria Zebrzydowska","Kraków","Krynica-Zdrój","Limanowa","Maków Podhalański","Miechów","Myślenice","Nowy Sącz","Nowy Targ","Olkusz","Oświęcim","Piwniczna-Zdrój","Proszowice","Rabka-Zdrój","Skała","Skawina","Słomniki","Stary Sącz","Sucha Beskidzka","Sułkowice","Szczawnica","Świątniki Górne","Tarnów","Trzebinia","Tuchów","Wadowice","Wieliczka","Wojnicz","Zakliczyn","Zakopane","Żabno"]},
    {"name": "Mazowieckie", "cities": ["Białobrzegi","Bieżuń","Błonie","Brok","Brwinów","Ciechanów","Garwolin","Gąbin","Gostynin","Góra Kalwaria","Grodzisk Mazowiecki","Grójec","Halinów","Iłża","Józefów","Karczew","Kałuszyn","Kobyłka","Konstancin-Jeziorna","Kosów Lacki","Kozienice","Legionowo","Lipsko","Łaskarzew","Łochów","Łomianki","Łosice","Maków Mazowiecki","Milanówek","Mińsk Mazowiecki","Mława","Mogielnica","Mszczonów","Nasielsk","Nowe Miasto nad Pilicą","Nowy Dwór Mazowiecki","Ożarów Mazowiecki","Ostrów Mazowiecka","Otwock","Piaseczno","Piastów","Pionki","Płock","Płońsk","Podkowa Leśna","Pruszków","Przasnysz","Pułtusk","Radom","Raciąż","Sanniki","Siedlce","Sierpc","Sochaczew","Sokołów Podlaski","Sulejówek","Szydłowiec","Tarczyn","Warszawa","Warka","Węgrów","Wołomin","Wyszków","Zakroczym","Ząbki","Zielonka","Żelechów","Żyrardów"]},
    {"name": "Opolskie", "cities": ["Baborów","Brzeg","Dobrodzień","Głogówek","Głubczyce","Gogolin","Grodków","Kędzierzyn-Koźle","Kluczbork","Kolonowskie","Korfantów","Lewin Brzeski","Namysłów","Niemodlin","Nysa","Olesno","Opole","Ozimek","Paczków","Praszka","Prudnik","Strzelce Opolskie","Tułowice","Ujazd","Zawadzkie"]},
    {"name": "Podkarpackie", "cities": ["Baranów Sandomierski","Brzozów","Dębica","Dukla","Dynów","Głogów Małopolski","Jarosław","Jasło","Kańczuga","Kolbuszowa","Krosno","Leżajsk","Lubaczów","Łańcut","Mielec","Narol","Nisko","Nowa Dęba","Pruchnik","Przemyśl","Przeworsk","Radomyśl Wielki","Ropczyce","Rudnik nad Sanem","Rzeszów","Sanok","Sędziszów Małopolski","Stalowa Wola","Strzyżów","Tarnobrzeg","Ulanów","Ustrzyki Dolne","Zagórz","Zaklików"]},
]

# ─── KONFIGURACJA ────────────────────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

IG_SKIP_USERNAMES = {
    "p", "reel", "reels", "explore", "stories", "tv", "accounts",
    "directory", "about", "legal", "developer", "help", "privacy",
    "terms", "api", "press", "static", "nametag", "direct", "lite",
    "web", "emails", "tags",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def phrase_slug(phrase: str) -> str:
    """Zamienia frazę na slug do nazw plików (np. 'trener personalny' -> 'trener_personalny')."""
    s = phrase.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "default"


def progress_path(phrase: str) -> str:
    return os.path.join(BASE_DIR, f"progress_{phrase_slug(phrase)}.json")


# Zachowane dla wstecznej kompatybilności (trenerzy)
PROGRESS_FILE = os.path.join(BASE_DIR, "progress.json")


def load_done_cities(phrase: str = None) -> set[str]:
    """Wczytuje miasta które już przeszukano dla danej frazy."""
    path = progress_path(phrase) if phrase else PROGRESS_FILE
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("done_cities", []))
        except Exception:
            pass
    return set()


def save_done_city(city: str, phrase: str = None):
    """Dodaje miasto do listy przeszukanych dla danej frazy."""
    path = progress_path(phrase) if phrase else PROGRESS_FILE
    done = load_done_cities(phrase)
    done.add(city)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"done_cities": sorted(done)}, f, ensure_ascii=False, indent=2)


def load_cities_from_html(path: str) -> set[str]:
    """Wyciąga miasta z istniejącego eksportu HTML."""
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        # Miasto jest w 4. kolumnie <td>
        cities = set(re.findall(
            r"<td>[^<]+</td>\s*<td><a[^>]+>[^<]+</a></td>\s*<td>([^<]+)</td>", html
        ))
        return cities
    except Exception:
        return set()


def reset_progress(phrase: str = None):
    """Resetuje postęp dla danej frazy."""
    path = progress_path(phrase) if phrase else PROGRESS_FILE
    if os.path.isfile(path):
        os.remove(path)


@dataclass
class ScrapedProfile:
    username: str
    url: str
    city: str
    region: str


# ─── SCRAPER ─────────────────────────────────────────────────────────────────

class Scraper:
    """Selenium scraper - wpisuje zapytanie w Google jak człowiek."""

    def __init__(self, delay_min=8, delay_max=18):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.driver = None
        self._stop = False
        self._query_count = 0

    def stop(self):
        self._stop = True

    def _sleep(self, seconds: float):
        """Sleep przerywany co 0.5s przez stop()."""
        elapsed = 0.0
        while elapsed < seconds and not self._stop:
            chunk = min(0.5, seconds - elapsed)
            time.sleep(chunk)
            elapsed += chunk

    def init_driver(self):
        """Uruchamia Chrome (widoczny)."""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-search-engine-choice-screen")
        options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)
        self.driver.implicitly_wait(5)
        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        self._query_count = 0

    def _dismiss_alert(self):
        """Zamyka alert przeglądarki jeśli istnieje."""
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
        except Exception:
            pass

    def _safe_page_source(self) -> str:
        """Pobiera page_source z obsługą alertów."""
        try:
            self._dismiss_alert()
            return self.driver.page_source
        except Exception:
            return ""

    def _is_blocked(self, html: str) -> bool:
        h = html.lower()
        if any(m in h for m in ['<li class="b_algo"', '<div class="g"', "web-result"]):
            return False
        blocked = ["unusual traffic", "g-recaptcha", "turnstile", "cf-turnstile",
                   "google.com/sorry", "/sorry/index", "solve this captcha",
                   "ostatni krok", "challenge/verify", "are not a robot"]
        return any(m in h for m in blocked)

    def _wait_captcha(self, callback=None):
        """Czeka BEZ LIMITU aż user rozwiąże CAPTCHA. Nie przechodzi dalej."""
        if callback:
            callback("WARN", ">>> CAPTCHA! Rozwiąż ją ręcznie w oknie Chrome... (czekam bez limitu)")
        while not self._stop:
            time.sleep(3)
            try:
                self._dismiss_alert()
                html = self.driver.page_source
                if not self._is_blocked(html):
                    if callback:
                        callback("INFO", "CAPTCHA rozwiązana! Kontynuuję...")
                    return True
            except Exception:
                pass
        return False

    def _type_query(self, query: str, callback=None):
        """Wpisuje zapytanie w pole Google jak człowiek."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        self._dismiss_alert()

        # Upewnij się że jesteśmy na Google
        try:
            current = self.driver.current_url
        except Exception:
            current = ""
        if "google" not in current:
            self.driver.get("https://www.google.com")
            self._sleep(random.uniform(2, 4))
            self._dismiss_alert()
            self._try_accept_cookies()

        # Sprawdź czy jest CAPTCHA zanim szukamy pola
        html = self._safe_page_source()
        if self._is_blocked(html):
            if not self._wait_captcha(callback):
                return False

        # Znajdź pole wyszukiwania
        box = None
        for sel in ["textarea[name='q']", "input[name='q']"]:
            elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                box = elems[0]
                break

        if not box:
            self.driver.get("https://www.google.com")
            self._sleep(3)
            self._dismiss_alert()
            self._try_accept_cookies()
            for sel in ["textarea[name='q']", "input[name='q']"]:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    box = elems[0]
                    break

        if not box:
            if callback:
                callback("ERROR", "Nie znaleziono pola wyszukiwania Google!")
            return False

        # Wyczyść i wpisz
        box.click()
        self._sleep(0.3)
        box.clear()
        box.send_keys(Keys.CONTROL, "a")
        box.send_keys(Keys.DELETE)
        self._sleep(0.3)

        for char in query:
            box.send_keys(char)
            time.sleep(random.uniform(0.03, 0.10))

        self._sleep(random.uniform(0.5, 1.5))
        box.send_keys(Keys.RETURN)
        self._sleep(random.uniform(2, 4))
        return True

    def _try_accept_cookies(self):
        """Próbuje zaakceptować Google cookies consent."""
        from selenium.webdriver.common.by import By
        try:
            for btn in self.driver.find_elements(By.TAG_NAME, "button"):
                txt = btn.text.lower()
                if any(w in txt for w in ["zaakceptuj", "akceptuj", "accept all", "accept", "zgadzam"]):
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(1)
                        return
        except Exception:
            pass

    def _extract_ig_profiles(self, html: str) -> list[str]:
        """Wyciąga unikalne username'y IG z HTML wyników Google."""
        found = set()

        # Dekoduj URL-encoded znaki (Google opakowuje linki)
        decoded = unquote(html)

        # Szukaj instagram.com/username w zdekodowanym HTML
        for m in re.finditer(r"instagram\.com/([a-zA-Z0-9_.]{2,30})(?:[/\"'?\s&<]|$)", decoded):
            username = m.group(1).lower()
            if username not in IG_SKIP_USERNAMES:
                found.add(username)

        return list(found)

    def _click_next_page(self) -> bool:
        """Kliknij 'Następna' w wynikach Google."""
        from selenium.webdriver.common.by import By

        try:
            # Google: przycisk "Następna" / "Next"
            for sel in ["a#pnnext", "a[aria-label='Next']"]:
                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if btns and btns[0].is_displayed():
                    btns[0].click()
                    self._sleep(random.uniform(2, 4))
                    return True

            # Fallback: szukaj po tekście
            for link in self.driver.find_elements(By.TAG_NAME, "a"):
                txt = link.text.lower().strip()
                if txt in ("następna", "next", "dalej"):
                    if link.is_displayed():
                        link.click()
                        self._sleep(random.uniform(2, 4))
                        return True
        except Exception:
            pass
        return False

    def search(self, query: str, callback=None) -> list[str]:
        """Wyszukuje w Google i zwraca listę username'ów IG (do 3 stron)."""
        if not self.driver:
            self.init_driver()

        if not self._type_query(query, callback):
            return []

        all_usernames = []
        seen = set()

        for page in range(3):  # strony 1, 2, 3
            if self._stop:
                break

            self._sleep(random.uniform(self.delay_min, self.delay_max))
            html = self._safe_page_source()

            if self._is_blocked(html):
                if not self._wait_captcha(callback):
                    break  # Tylko jeśli stop()
                html = self._safe_page_source()

            usernames = self._extract_ig_profiles(html)
            new = 0
            for u in usernames:
                if u not in seen:
                    seen.add(u)
                    all_usernames.append(u)
                    new += 1

            if callback:
                callback("INFO", f"Strona {page + 1}: +{new} profili ({len(all_usernames)} łącznie)")

            self._query_count += 1

            if page == 0 and new == 0:
                debug_path = os.path.join(os.path.dirname(__file__) or ".", "debug_last.html")
                with open(debug_path, "w", encoding="utf-8") as f:
                    f.write(html)
                if callback:
                    callback("WARN", f"Brak wyników - debug zapisany do {debug_path}")
                break

            # Przejdź na następną stronę
            if page < 2:
                if not self._click_next_page():
                    break
                # Dodatkowa losowa pauza między stronami
                self._sleep(random.uniform(2, 5))

        # Co ~20 zapytań restart drivera
        if self._query_count >= 20:
            if callback:
                callback("INFO", "Restart przeglądarki...")
            self.init_driver()

        return all_usernames

    def scrape_city(self, phrase: str, city: str, region: str, callback=None) -> list[ScrapedProfile]:
        query = f'site:instagram.com "{phrase}" "{city}"'
        if callback:
            callback("INFO", f"Szukam: {query}")

        usernames = self.search(query, callback)
        profiles = []
        for u in usernames:
            p = ScrapedProfile(
                username=u,
                url=f"https://www.instagram.com/{u}/",
                city=city, region=region,
            )
            profiles.append(p)
            if callback:
                callback("FOUND", f"@{u} -> instagram.com/{u} [{city}]")
        return profiles

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None


# ─── GUI ─────────────────────────────────────────────────────────────────────

class ScraperApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("IG Scraper - Trenerzy Personalni")
        self.root.geometry("1050x700")
        self.root.minsize(850, 550)

        self.scraper: Scraper | None = None
        self.found_profiles: list[ScrapedProfile] = []
        self.seen_urls: set[str] = set()
        self.is_running = False

        self._build_ui()

    def _build_ui(self):
        # ── Ustawienia ──
        sf = ttk.LabelFrame(self.root, text="Ustawienia", padding=10)
        sf.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(sf, text="Fraza:").grid(row=0, column=0, sticky=tk.W)
        self.phrase_var = tk.StringVar(value="paznokcie")
        ttk.Entry(sf, textvariable=self.phrase_var, width=35).grid(row=0, column=1, padx=5)

        ttk.Label(sf, text="Opóźnienie (s):").grid(row=0, column=2, padx=(15, 0))
        self.delay_min_var = tk.StringVar(value="8")
        self.delay_max_var = tk.StringVar(value="18")
        ttk.Entry(sf, textvariable=self.delay_min_var, width=4).grid(row=0, column=3)
        ttk.Label(sf, text="-").grid(row=0, column=4)
        ttk.Entry(sf, textvariable=self.delay_max_var, width=4).grid(row=0, column=5)

        ttk.Label(sf, text="Województwo:").grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.region_var = tk.StringVar(value="Wszystkie")
        region_names = ["Wszystkie"] + [r["name"] for r in SEO_REGIONS]
        ttk.Combobox(sf, textvariable=self.region_var, values=region_names,
                     state="readonly", width=35).grid(row=1, column=1, padx=5, pady=(5, 0))

        # ── Przyciski ──
        bf = ttk.Frame(self.root)
        bf.pack(fill=tk.X, padx=10, pady=5)

        self.start_btn = ttk.Button(bf, text="START", command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(bf, text="STOP", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="Eksport CSV", command=self._export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="Eksport HTML", command=self._export_html).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="Reset postępu", command=self._reset_progress).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="Wyczyść", command=self._clear).pack(side=tk.LEFT, padx=5)

        self.counter_var = tk.StringVar(value="Znalezione: 0")
        ttk.Label(bf, textvariable=self.counter_var, font=("Consolas", 11, "bold")).pack(side=tk.RIGHT, padx=10)

        # ── Postęp ──
        pf = ttk.Frame(self.root)
        pf.pack(fill=tk.X, padx=10, pady=2)
        self.progress_var = tk.StringVar(value="Gotowy")
        ttk.Label(pf, textvariable=self.progress_var).pack(side=tk.LEFT)
        self.progress_bar = ttk.Progressbar(pf, mode="determinate")
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

        # ── Tabela ──
        tf = ttk.LabelFrame(self.root, text="Wyniki", padding=5)
        tf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 2))

        cols = ("lp", "username", "url", "city", "region")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=12)
        self.tree.heading("lp", text="#")
        self.tree.heading("username", text="Username")
        self.tree.heading("url", text="Link Instagram")
        self.tree.heading("city", text="Miasto")
        self.tree.heading("region", text="Województwo")
        self.tree.column("lp", width=40, stretch=False)
        self.tree.column("username", width=150)
        self.tree.column("url", width=320)
        self.tree.column("city", width=140)
        self.tree.column("region", width=180)

        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self._copy_url)

        # ── Log ──
        lf = ttk.LabelFrame(self.root, text="Log", padding=5)
        lf.pack(fill=tk.X, padx=10, pady=(2, 10))
        self.log_text = scrolledtext.ScrolledText(lf, height=7, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.X)
        self.log_text.tag_configure("INFO", foreground="gray")
        self.log_text.tag_configure("FOUND", foreground="green")
        self.log_text.tag_configure("WARN", foreground="orange")
        self.log_text.tag_configure("ERROR", foreground="red")
        self.log_text.tag_configure("STATUS", foreground="blue")

    def _log(self, level: str, msg: str):
        def _do():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n", level)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        self.root.after(0, _do)

    def _add_profile(self, p: ScrapedProfile):
        def _do():
            if p.url in self.seen_urls:
                return
            self.seen_urls.add(p.url)
            self.found_profiles.append(p)
            idx = len(self.found_profiles)
            self.tree.insert("", tk.END, values=(idx, f"@{p.username}", p.url, p.city, p.region))
            self.counter_var.set(f"Znalezione: {idx}")
        self.root.after(0, _do)

    def _update_progress(self, current, total, city):
        def _do():
            pct = current / total * 100 if total else 0
            self.progress_bar["value"] = pct
            self.progress_var.set(f"{city} ({current}/{total})")
        self.root.after(0, _do)

    def _start(self):
        if self.is_running:
            return
        self.is_running = True
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        threading.Thread(target=self._worker, daemon=True).start()

    def _stop(self):
        self._log("WARN", "Zatrzymywanie...")
        if self.scraper:
            self.scraper.stop()
        self.is_running = False

    def _worker(self):
        phrase = self.phrase_var.get().strip()
        if not phrase:
            self._log("ERROR", "Podaj frazę!")
            self._finish()
            return

        delay_min = float(self.delay_min_var.get())
        delay_max = float(self.delay_max_var.get())

        self.scraper = Scraper(delay_min, delay_max)

        # Wybierz regiony
        sel = self.region_var.get()
        if sel == "Wszystkie":
            regions = SEO_REGIONS
        else:
            regions = [r for r in SEO_REGIONS if r["name"] == sel]

        # Wczytaj miasta do pominięcia dla aktualnej frazy
        phrase = self.phrase_var.get()
        skip_cities = load_done_cities(phrase)

        # Zbuduj listę miast (pomijając już przeszukane w tej sesji) i przemieszaj
        all_cities = [(c, r["name"]) for r in regions for c in r["cities"]]
        cities = [(c, r) for c, r in all_cities if c not in skip_cities]
        random.shuffle(cities)
        total = len(cities)
        skipped = len(all_cities) - total

        self._log("STATUS", f"Start: {total} miast do przeszukania (pominięto {skipped} już przeszukanych)")
        self._log("STATUS", "Chrome otworzy się widocznie. Jeśli CAPTCHA - rozwiąż ją ręcznie!")

        try:
            self.scraper.init_driver()
        except Exception as e:
            self._log("ERROR", f"Nie można uruchomić Chrome: {e}")
            self._finish()
            return

        try:
            for idx, (city, region) in enumerate(cities):
                if not self.is_running:
                    break

                self._update_progress(idx + 1, total, city)

                # Próbuj miasto max 3 razy - przy błędzie czekaj, nie pomijaj
                for attempt in range(3):
                    if not self.is_running:
                        break
                    try:
                        self.scraper._dismiss_alert()
                        profiles = self.scraper.scrape_city(phrase, city, region, callback=self._log)
                        for p in profiles:
                            self._add_profile(p)
                        break  # Sukces - wychodź z retry loop
                    except Exception as e:
                        self._log("ERROR", f"Błąd przy {city} (próba {attempt+1}/3): {e}")
                        if attempt < 2:
                            self._log("WARN", f"Czekam 30s i próbuję ponownie...")
                            self.scraper._dismiss_alert()
                            self.scraper._sleep(30)
                            # Sprawdź czy jest CAPTCHA
                            html = self.scraper._safe_page_source()
                            if self.scraper._is_blocked(html):
                                self.scraper._wait_captcha(callback=self._log)

                # Zapisz postęp - to miasto jest przeszukane (per-fraza)
                save_done_city(city, phrase)

                # Pauza między miastami
                if self.is_running and idx + 1 < total:
                    delay = random.uniform(delay_min, delay_max)
                    if (idx + 1) % 8 == 0:
                        delay += random.uniform(15, 35)
                        self._log("WARN", f"Pauza ochronna {delay:.0f}s po {idx + 1} miastach...")
                    else:
                        self._log("INFO", f"Czekam {delay:.1f}s...")
                    self.scraper._sleep(delay)
        except Exception as e:
            self._log("ERROR", f"Nieoczekiwany błąd: {e}")
        finally:
            self.scraper.close()
            self._log("STATUS", f"ZAKOŃCZONO! Znaleziono {len(self.found_profiles)} profili.")
            self._finish()

    def _finish(self):
        def _do():
            self.is_running = False
            self.start_btn.configure(state=tk.NORMAL)
            self.stop_btn.configure(state=tk.DISABLED)
            self.progress_var.set("Zakończono")
            self.progress_bar["value"] = 100
        self.root.after(0, _do)

    def _copy_url(self, event):
        sel = self.tree.selection()
        if sel:
            url = self.tree.item(sel[0], "values")[2]
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._log("INFO", f"Skopiowano: {url}")

    def _export_csv(self):
        if not self.found_profiles:
            messagebox.showwarning("Brak", "Brak danych do eksportu.")
            return
        slug = phrase_slug(self.phrase_var.get())
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"ig_{slug}.csv")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["#", "Username", "URL", "Miasto", "Województwo"])
            for i, p in enumerate(self.found_profiles, 1):
                w.writerow([i, p.username, p.url, p.city, p.region])
        self._log("STATUS", f"Eksport: {path}")
        messagebox.showinfo("OK", f"Zapisano {len(self.found_profiles)} profili.")

    def _load_existing_profiles(self, path: str) -> list[ScrapedProfile]:
        """Wczytuje profile z istniejącego pliku HTML."""
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                html = f.read()
            profiles = []
            for m in re.finditer(
                r"<td>\d+</td>\s*<td>@([^<]+)</td>\s*"
                r"<td><a href=\"([^\"]+)\"[^>]*>[^<]*</a></td>\s*"
                r"<td>([^<]+)</td>\s*<td>([^<]+)</td>",
                html
            ):
                profiles.append(ScrapedProfile(
                    username=m.group(1), url=m.group(2),
                    city=m.group(3), region=m.group(4),
                ))
            return profiles
        except Exception:
            return []

    def _export_html(self):
        slug = phrase_slug(self.phrase_var.get())
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML", "*.html")],
                                            initialfile=f"ig_{slug}_rekordy.html")
        if not path:
            return

        # Wczytaj istniejące profile z pliku (jeśli istnieje)
        existing = self._load_existing_profiles(path)
        seen = {p.url for p in existing}

        # Dopisz nowe (bez duplikatów)
        new_count = 0
        for p in self.found_profiles:
            if p.url not in seen:
                seen.add(p.url)
                existing.append(p)
                new_count += 1

        all_profiles = existing
        rows = ""
        for i, p in enumerate(all_profiles, 1):
            rows += f"""<tr>
<td>{i}</td>
<td>@{p.username}</td>
<td><a href="{p.url}" target="_blank">{p.url}</a></td>
<td>{p.city}</td>
<td>{p.region}</td>
</tr>\n"""

        html = f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<title>IG Trenerzy Personalni - {len(all_profiles)} profili</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
h1 {{ color: #333; }}
table {{ border-collapse: collapse; width: 100%; background: white; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
th {{ background: #E1306C; color: white; padding: 10px 12px; text-align: left; position: sticky; top: 0; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #eee; }}
tr:hover {{ background: #f0f0f0; }}
a {{ color: #E1306C; text-decoration: none; font-weight: 500; }}
a:hover {{ text-decoration: underline; }}
.stats {{ color: #666; margin-bottom: 15px; }}
td input[type="checkbox"] {{ width: 18px; height: 18px; cursor: pointer; }}
</style>
<script>
document.addEventListener('DOMContentLoaded', function() {{
  const rows = document.querySelectorAll('table tr');
  const fields = [
    {{ key: 'odpisal',    cls: 'cb-odpisal' }},
    {{ key: 'zgodzilsie', cls: 'cb-zgodzilsie' }}
  ];
  rows.forEach((row, idx) => {{
    if (idx === 0) return;
    const link = row.querySelector('a');
    if (!link) return;
    const id = link.getAttribute('href');
    fields.forEach(f => {{
      const td = document.createElement('td');
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.className = f.cls;
      const sk = 'ig_' + f.key + '__' + id;
      cb.checked = localStorage.getItem(sk) === '1';
      cb.addEventListener('change', () => {{
        localStorage.setItem(sk, cb.checked ? '1' : '0');
      }});
      td.appendChild(cb);
      row.appendChild(td);
    }});
  }});
}});
</script>
</head>
<body>
<h1>Trenerzy Personalni - Instagram</h1>
<p class="stats">Znaleziono: <strong>{len(all_profiles)}</strong> profili</p>
<table>
<tr><th>#</th><th>Username</th><th>Link (kliknij)</th><th>Miasto</th><th>Województwo</th><th>Odpisał</th><th>Zgodził się</th></tr>
{rows}</table>
</body>
</html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self._log("STATUS", f"Eksport HTML: {len(all_profiles)} profili ({new_count} nowych, {len(all_profiles) - new_count} z poprzednich)")
        messagebox.showinfo("OK", f"Zapisano {len(all_profiles)} profili ({new_count} nowych dopisanych).")

    def _reset_progress(self):
        phrase = self.phrase_var.get()
        done = load_done_cities(phrase)
        if not done:
            messagebox.showinfo("Info", "Brak zapisanego postępu dla tej frazy.")
            return
        if messagebox.askyesno("Reset", f"Usunąć postęp dla frazy '{phrase}' ({len(done)} miast)?\nScraper zacznie przeszukiwać od nowa."):
            reset_progress(phrase)
            self._log("STATUS", f"Postęp dla '{phrase}' zresetowany.")

    def _clear(self):
        self.found_profiles.clear()
        self.seen_urls.clear()
        self.tree.delete(*self.tree.get_children())
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.counter_var.set("Znalezione: 0")
        self.progress_var.set("Gotowy")
        self.progress_bar["value"] = 0


if __name__ == "__main__":
    root = tk.Tk()
    ScraperApp(root)
    root.mainloop()
