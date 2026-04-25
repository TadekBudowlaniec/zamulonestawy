"""
IG DM Bot — wysyła spersonalizowane wiadomości do trenerów personalnych.

Workflow:
  1. Przy pierwszym uruchomieniu: otwiera przeglądarkę, czeka aż zalogujesz się
     ręcznie na IG, potem zapisuje sesję i kontynuuje automatycznie.
  2. Otwiera stronę na Netlify, wpisuje token GitHub, synchronizuje dane
  3. Filtruje nienapisane profile
  4. Dla każdego: kopiuje wiadomość, otwiera profil IG, wysyła DM, zaznacza

Użycie:
  python ig_bot.py                  # domyślnie 10 wiadomości
  python ig_bot.py --count 5        # wyślij 5 wiadomości
  python ig_bot.py --delay 60       # 60s przerwy między wiadomościami
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# ─── CONFIG ──────────────────────────────────────────────────────────────────

def load_env(path):
    """Prosty loader .env — bez dodatkowych zależności."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_env(os.path.join(BASE_DIR, ".env"))

SITE_URL = os.environ.get("SITE_URL", "https://zamulence.netlify.app")
PROFILE_DIR = os.path.join(BASE_DIR, ".ig_browser_profile")
DEFAULT_COUNT = 10
MIN_DELAY = 45
MAX_DELAY = 75
ATTEMPTS_LIMIT = 3

IG_USERNAME = os.environ.get("IG_USERNAME", "")
IG_PASSWORD = os.environ.get("IG_PASSWORD", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

if not IG_USERNAME or not IG_PASSWORD or not GITHUB_TOKEN:
    sys.exit(
        "❌ Brak wymaganych zmiennych w .env\n"
        "   Skopiuj .env.example do .env i uzupełnij:\n"
        "     IG_USERNAME, IG_PASSWORD, GITHUB_TOKEN"
    )


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def random_delay(lo=MIN_DELAY, hi=MAX_DELAY):
    d = random.uniform(lo, hi)
    print(f"   ⏳ Czekam {d:.0f}s...")
    time.sleep(d)


def short_pause(lo=1.0, hi=2.5):
    time.sleep(random.uniform(lo, hi))


def _attempts_path(page_slug):
    suffix = f"_{page_slug}" if page_slug else ""
    return os.path.join(BASE_DIR, f"attempts{suffix}.json")


def _read_attempts(page_slug):
    p = _attempts_path(page_slug)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_attempts(page_slug, data):
    p = _attempts_path(page_slug)
    tmp = p + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except Exception:
        pass


def bump_attempt(page_slug, username):
    if not username or username == "?":
        return 0
    data = _read_attempts(page_slug)
    n = data.get(username, 0) + 1
    data[username] = n
    _write_attempts(page_slug, data)
    return n


def clear_attempt(page_slug, username):
    if not username or username == "?":
        return
    data = _read_attempts(page_slug)
    if username in data:
        del data[username]
        _write_attempts(page_slug, data)


def mark_profile_contacted(page, username):
    """Klika checkbox profilu na liście, żeby wypadł z 'Nienapisane'."""
    cards = page.query_selector_all(".profile-card")
    for card in cards:
        uname = card.query_selector(".profile-username a")
        if uname and uname.inner_text() == username:
            cb = card.query_selector("input[type='checkbox']")
            if cb and not cb.is_checked():
                cb.click()
                short_pause(0.5, 1.0)
                print(f"   🚫 Auto-odznaczono {username} (limit prób).")
            return


def handle_skip(page, page_slug, username, restore=False):
    """Wspólna obsługa pominiętego profilu: bump licznika + auto-mark po limicie."""
    if restore:
        restore_netlify(page)
    n = bump_attempt(page_slug, username)
    if n >= ATTEMPTS_LIMIT:
        print(f"   ⛔ Próba {n}/{ATTEMPTS_LIMIT} dla {username} — odznaczam.")
        mark_profile_contacted(page, username)
    elif n > 0:
        print(f"   ↩️  Próba {n}/{ATTEMPTS_LIMIT} dla {username}.")


def set_ig_cookies(ctx):
    """Ustawia cookies IG żeby ominąć dialog zgody na cookies."""
    ctx.add_cookies([
        {"name": "ig_cb", "value": "2", "domain": ".instagram.com", "path": "/"},
        {"name": "ig_did", "value": "1", "domain": ".instagram.com", "path": "/"},
    ])


def dismiss_ig_popups(page):
    """Zamyka popupy IG (powiadomienia, save login itp.)."""
    for sel in [
        "button:has-text('Nie teraz')",
        "button:has-text('Not Now')",
        "button:has-text('Not now')",
    ]:
        try:
            btn = page.wait_for_selector(sel, timeout=2000)
            if btn and btn.is_visible():
                btn.click()
                print("   🔕 Zamknięto popup IG")
                short_pause(1, 2)
        except PwTimeout:
            pass

    # Fallback: zamknij dialog cookies przez DOM
    try:
        cookie_btns = page.query_selector_all("div[role='dialog'] button")
        for btn in cookie_btns:
            if btn.is_visible():
                btn.click()
                print("   🍪 Zamknięto dialog (fallback)")
                short_pause(2, 3)
                break
    except Exception:
        pass


def is_logged_in_ig(page):
    """Sprawdza czy user jest zalogowany na IG (szuka elementów niezalogowanego)."""
    for sel in [
        "input[name='username']",
        "a[href='/accounts/login/']",
        "button:has-text('Log in')",
        "button:has-text('Zaloguj się')",
        "button:has-text('Sign up')",
        "button:has-text('Zarejestruj się')",
    ]:
        el = page.query_selector(sel)
        if el and el.is_visible():
            return False
    return True


def goto_ig(page, url):
    """Nawiguje na stronę IG z odpowiednim timeout i wait strategy."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)


def ensure_ig_session(page):
    """Sprawdza sesję IG. Jeśli brak — otwiera IG i czeka na ręczne logowanie."""
    print("🌐 Sprawdzam sesję Instagram...")
    goto_ig(page, "https://www.instagram.com/")
    short_pause(3, 5)
    dismiss_ig_popups(page)

    if is_logged_in_ig(page):
        print("   ✅ Sesja IG aktywna.")
        return

    # Nie zalogowany — poproś o ręczne logowanie
    print()
    print("=" * 60)
    print("   ⚠️  NIE JESTEŚ ZALOGOWANY NA INSTAGRAM!")
    print()
    print("   Zaloguj się RĘCZNIE w otwartej przeglądarce.")
    print("   Bot poczeka i kontynuuje automatycznie.")
    print("=" * 60)
    print()

    goto_ig(page, "https://www.instagram.com/accounts/login/")
    short_pause(2, 3)
    dismiss_ig_popups(page)

    # Czekaj bez limitu aż user się zaloguje
    # Sprawdzaj co 5 sekund czy URL się zmienił z /login/
    while True:
        time.sleep(5)
        try:
            url = page.url
        except Exception:
            continue
        if "/accounts/login" not in url and "/accounts/signup" not in url:
            short_pause(2, 3)
            dismiss_ig_popups(page)
            short_pause(1, 2)
            dismiss_ig_popups(page)
            print("✅ Zalogowano na Instagram! Kontynuuję...")
            return


def click_login_as_ted(page):
    """Klika przycisk logowania dla użytkownika 'Ted' na ekranie wyboru."""
    # Szukaj wśród .login-btn tego z tekstem zawierającym 'ted'
    btns = page.query_selector_all(".login-btn")
    for btn in btns:
        try:
            txt = (btn.inner_text() or "").strip().lower()
        except Exception:
            continue
        if "ted" in txt:
            btn.click()
            short_pause()
            print("   Zalogowano na stronie jako Ted.")
            return

    # Fallback: dowolny klikalny element z tekstem 'ted'
    for sel in [
        "button:has-text('Ted')",
        "button:has-text('ted')",
        ":is(div, a)[role='button']:has-text('Ted')",
    ]:
        try:
            el = page.wait_for_selector(sel, timeout=1500)
            if el and el.is_visible():
                el.click()
                short_pause()
                print("   Zalogowano na stronie jako Ted (fallback).")
                return
        except PwTimeout:
            pass

    print("   ⚠️  Nie znalazłem przycisku logowania 'Ted' — sprawdź stronę.")


def install_clipboard_hook(page):
    """Podmienia navigator.clipboard.writeText, żeby skopiowana wiadomość
    trafiała do window.__lastCopied zamiast do systemowego schowka.
    Dzięki temu kilka instancji bota nie podkrada sobie wzajemnie tekstu."""
    page.evaluate("""() => {
        if (window.__clipHookInstalled) return;
        window.__clipHookInstalled = true;
        window.__lastCopied = null;
        const c = navigator.clipboard || {};
        c.writeText = async (txt) => {
            window.__lastCopied = txt;
            return Promise.resolve();
        };
        navigator.clipboard = c;
    }""")


def setup_netlify(page):
    """Loguje na stronie Netlify, wpisuje token, ustawia filtr."""
    page.goto(SITE_URL, wait_until="networkidle")
    short_pause()
    install_clipboard_hook(page)

    # Zaloguj jako Ted
    login_screen = page.query_selector("#loginScreen")
    if login_screen and login_screen.is_visible():
        click_login_as_ted(page)

    # Wpisz token GitHub i zsynchronizuj
    token_input = page.query_selector("#tokenInput")
    if token_input:
        token_input.fill(GITHUB_TOKEN)
        short_pause(0.3, 0.7)
        save_btn = page.query_selector("button:has-text('Zapisz token')")
        if save_btn:
            save_btn.click()
            print("   🔑 Token GitHub zapisany, synchronizacja...")
            short_pause(2.5, 4)

    # Ustaw filtr na "Nienapisane"
    status_filter = page.query_selector("#statusFilter")
    if status_filter:
        status_filter.select_option("pending")
        short_pause(0.5, 1.0)
        print("   🔍 Filtr: tylko nienapisane profile.")


def restore_netlify(page):
    """Wraca na stronę Netlify i przywraca stan (login + token + filtr).
    Wpisuje token za każdym razem, żeby wymusić świeżą synchronizację z GitHuba."""
    page.goto(SITE_URL, wait_until="networkidle")
    short_pause(1.2, 2.0)
    install_clipboard_hook(page)

    login_screen = page.query_selector("#loginScreen")
    if login_screen and login_screen.is_visible():
        click_login_as_ted(page)

    # Wpisz token i wymuś synchronizację z GitHub
    token_input = page.query_selector("#tokenInput")
    if token_input:
        token_input.fill("")
        short_pause(0.2, 0.4)
        token_input.fill(GITHUB_TOKEN)
        short_pause(0.3, 0.7)
        save_btn = page.query_selector("button:has-text('Zapisz token')")
        if save_btn:
            save_btn.click()
            print("   🔄 Re-sync: token wpisany, pobieram świeże dane z GitHub...")
            short_pause(2.5, 4)

    status_filter = page.query_selector("#statusFilter")
    if status_filter:
        status_filter.select_option("pending")
        short_pause(0.3, 0.7)


# ─── AI (GROQ) ───────────────────────────────────────────────────────────────

def extract_ig_context(page):
    """Wyciąga bio i alt-opisy 3 pierwszych postów z otwartego profilu IG."""
    try:
        data = page.evaluate("""() => {
            const out = { bio: '', posts: [] };
            // Bio: meta og:description jest najstabilniejsze
            const meta = document.querySelector("meta[property='og:description']");
            if (meta) {
                const c = (meta.getAttribute('content') || '').trim();
                // og:description ma format: "123 Followers, 45 Following, 6 Posts - @user on Instagram: \\"bio\\""
                const m = c.match(/Instagram[^:]*:\\s*[\\"'\\u201c\\u201d](.+?)[\\"'\\u201c\\u201d]\\s*$/);
                out.bio = m ? m[1].trim() : c;
            }
            // Fallback — tekst z sekcji header
            if (!out.bio) {
                const header = document.querySelector('header section');
                if (header) {
                    const txt = (header.innerText || '').trim();
                    const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
                    for (const l of lines) {
                        if (l.length > 20 && l.length < 400 &&
                            !/^(obserwuj|follow|message|wyślij|wiadomo|posty|obserwuj[a-ząćęłńóśźż]+|\\d)/i.test(l)) {
                            out.bio = l; break;
                        }
                    }
                }
            }
            // Alty pierwszych postów
            const imgs = document.querySelectorAll("a[href*='/p/'] img, a[href*='/reel/'] img");
            const seen = new Set();
            for (const img of imgs) {
                const a = (img.getAttribute('alt') || '').trim();
                if (a && !seen.has(a)) { seen.add(a); out.posts.push(a); }
                if (out.posts.length >= 3) break;
            }
            return out;
        }""")
        return data or {"bio": "", "posts": []}
    except Exception as e:
        print(f"   ⚠️  Nie udało się wyciągnąć kontekstu IG: {e}")
        return {"bio": "", "posts": []}


def generate_message_with_groq(city, ctx, fallback):
    """Woła Groq API i zwraca spersonalizowaną wiadomość; fallback przy błędzie."""
    if not GROQ_API_KEY:
        return fallback

    bio = (ctx.get("bio") or "").strip()[:500]
    posts = [p[:200] for p in (ctx.get("posts") or [])][:3]

    if not bio and not posts:
        return fallback

    system_prompt = (
        "Jesteś handlowcem oferującym strony internetowe dla stylistek paznokci. "
        "Piszesz krótkie, naturalne DM-y po polsku, bez formalnych zwrotów i emoji. "
        "Maks. 3–4 zdania. Nawiąż do konkretu z profilu (bio lub posty), potem "
        "napisz że po wpisaniu 'paznokcie [miasto]' w Google nie ma jej tam i większość "
        "klientek trafia do innych stylistek. Wspomnij przykład strony: "
        "https://paznokcie-preview.netlify.app/ . Zakończ zdaniem: "
        "'Daj znać jeśli temat interesuje.'"
    )
    user_prompt = (
        f"Miasto: {city}\n"
        f"Bio: {bio or '(puste)'}\n"
        f"Ostatnie posty (alt-opisy zdjęć): {' | '.join(posts) if posts else '(brak)'}\n\n"
        "Napisz DM."
    )

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.8,
        "max_tokens": 350,
    }

    try:
        req = urllib.request.Request(
            GROQ_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "ig-bot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        msg = (body["choices"][0]["message"]["content"] or "").strip()
        # Usuń ewentualne cudzysłowy otaczające
        if len(msg) >= 2 and msg[0] in "\"'“”„" and msg[-1] in "\"'“”„":
            msg = msg[1:-1].strip()
        if len(msg) < 40:
            print("   ⚠️  Groq zwrócił za krótką wiadomość — używam szablonu")
            return fallback
        return msg
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = ""
        print(f"   ⚠️  Groq HTTP {e.code}: {err_body[:200]} — używam szablonu")
        return fallback
    except Exception as e:
        print(f"   ⚠️  Groq API błąd: {e} — używam szablonu")
        return fallback


def log_ai_message(username, city, ctx, message):
    """Zapisuje wygenerowaną wiadomość do pliku do późniejszego przeglądu."""
    try:
        path = os.path.join(BASE_DIR, "ai_messages.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write(f"@{username} ({city}) — {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Bio: {(ctx.get('bio') or '')[:250]}\n")
            f.write(f"Posty: {ctx.get('posts') or []}\n")
            f.write("---\n")
            f.write(message + "\n")
    except Exception:
        pass


# ─── MAIN FLOW ───────────────────────────────────────────────────────────────

def send_messages(pw, count, base_delay, target_index, profile_dir, use_ai=False, page_slug=""):
    ctx = pw.chromium.launch_persistent_context(
        profile_dir,
        headless=False,
        locale="pl-PL",
        viewport={"width": 1280, "height": 900},
        permissions=["clipboard-read", "clipboard-write"],
    )

    # Ominij dialog cookies IG
    set_ig_cookies(ctx)

    page = ctx.new_page()
    sent = 0

    try:
        # ── 1. Sprawdź / zaloguj na Instagram ──────────────────────────
        ensure_ig_session(page)

        # ── 2. Konfiguracja strony Netlify ──────────────────────────────
        print(f"\n📄 Otwieram {SITE_URL} ...")
        setup_netlify(page)

        for i in range(count):
            print(f"\n── Wiadomość {i + 1}/{count} ──")

            # Weź profil z konkretnego indeksu (z listy nienapisanych)
            cards = page.query_selector_all(".profile-card")
            pending_cards = []
            for card in cards:
                cb = card.query_selector("input[type='checkbox']")
                if cb and not cb.is_checked():
                    pending_cards.append(card)

            if not pending_cards:
                print("⚠️  Brak niezaznaczonych profili — kończę.")
                break

            if target_index >= len(pending_cards):
                print(f"⚠️  Indeks {target_index + 1} poza zakresem "
                      f"(nienapisanych: {len(pending_cards)}) — kończę.")
                break

            target_card = pending_cards[target_index]
            print(f"   🎯 Indeks {target_index + 1}/{len(pending_cards)}")

            username_el = target_card.query_selector(".profile-username a")
            username = username_el.inner_text() if username_el else "?"
            city_el = target_card.query_selector(".profile-meta")
            city = city_el.inner_text().split("·")[0].strip() if city_el else "?"
            print(f"   👤 {username} ({city})")

            # Kliknij "Kopiuj"
            copy_btn = target_card.query_selector(".btn-copy")
            if not copy_btn:
                print("   ❌ Brak przycisku Kopiuj — pomijam.")
                handle_skip(page, page_slug, username)
                continue
            copy_btn.click()
            short_pause(0.4, 0.8)

            # Odczytaj wiadomość przechwyconą przez clipboard hook
            # (omija systemowy schowek — bezpieczne dla wielu instancji)
            message = page.evaluate("() => window.__lastCopied")
            if not message or len(message) < 20:
                print("   ❌ Schowek pusty lub za krótka treść — pomijam.")
                handle_skip(page, page_slug, username)
                continue
            print(f"   📋 Skopiowano wiadomość ({len(message)} znaków)")

            # Otwórz profil IG
            ig_link = target_card.query_selector("a.btn-pink")
            ig_url = ig_link.get_attribute("href") if ig_link else None
            if not ig_url:
                print("   ❌ Brak linku IG — pomijam.")
                handle_skip(page, page_slug, username)
                continue

            goto_ig(page, ig_url)
            short_pause(3, 5)
            dismiss_ig_popups(page)

            # Sprawdź czy sesja wygasła
            if not is_logged_in_ig(page):
                print("   ⚠️  Sesja IG wygasła!")
                ensure_ig_session(page)
                goto_ig(page, ig_url)
                short_pause(3, 5)

            # Opcjonalnie: wygeneruj spersonalizowaną wiadomość przez Groq
            if use_ai:
                ctx_data = extract_ig_context(page)
                preview = (ctx_data.get("bio") or "")[:80]
                print(f"   🧠 Bio: {preview!r} | posty: {len(ctx_data.get('posts', []))}")
                ai_message = generate_message_with_groq(city, ctx_data, message)
                if ai_message != message:
                    print(f"   ✨ Groq: wygenerowano wiadomość ({len(ai_message)} znaków)")
                    log_ai_message(username, city, ctx_data, ai_message)
                    message = ai_message
                else:
                    print("   ↩️  Fallback na szablon")

            # Zaobserwuj profil jeśli jeszcze nie obserwujesz
            follow_btn = None
            for sel in [
                ":is(div, button)[role='button']:has-text('Obserwuj')",
                ":is(div, button)[role='button']:has-text('Follow')",
                "button:has-text('Obserwuj')",
                "button:has-text('Follow')",
            ]:
                try:
                    candidate = page.wait_for_selector(sel, timeout=2000)
                    if candidate and candidate.is_visible():
                        txt = (candidate.inner_text() or "").strip()
                        # Upewnij się że to "Obserwuj"/"Follow", nie "Obserwowanie"/"Following"
                        if txt in ("Obserwuj", "Follow"):
                            follow_btn = candidate
                            break
                except PwTimeout:
                    pass

            if not follow_btn:
                # Fallback JS
                try:
                    follow_btn = page.evaluate_handle("""() => {
                        const all = document.querySelectorAll('div[role="button"], button');
                        for (const el of all) {
                            const txt = (el.textContent || '').trim();
                            if ((txt === 'Obserwuj' || txt === 'Follow') && el.offsetParent !== null) {
                                return el;
                            }
                        }
                        return null;
                    }""")
                    if follow_btn and str(follow_btn) != "null":
                        follow_btn = follow_btn.as_element()
                    else:
                        follow_btn = None
                except Exception:
                    follow_btn = None

            if follow_btn:
                follow_btn.click()
                print("   ➕ Zaobserwowano profil")
                short_pause(1.2, 2.2)
            else:
                print("   ✔️  Już obserwujesz")

            # Kliknij "Wyślij wiadomości" / "Message"
            msg_btn = None
            for sel in [
                # Tekst PL — różne formy
                ":is(div, button, a)[role='button']:has-text('Wyślij wiadomo')",
                "button:has-text('Wyślij wiadomo')",
                "div:has-text('Wyślij wiadomo'):not(:has(div:has-text('Wyślij wiadomo')))",
                # Tekst EN
                ":is(div, button, a)[role='button']:has-text('Message')",
                "button:has-text('Message')",
            ]:
                try:
                    msg_btn = page.wait_for_selector(sel, timeout=3000)
                    if msg_btn and msg_btn.is_visible():
                        break
                    msg_btn = None
                except PwTimeout:
                    msg_btn = None

            # Fallback: szukaj przez JS dowolnego klikalnego elementu z tekstem "wiadomo"
            if not msg_btn:
                try:
                    msg_btn = page.evaluate_handle("""() => {
                        const all = document.querySelectorAll('div[role="button"], button, a');
                        for (const el of all) {
                            const txt = (el.textContent || '').toLowerCase();
                            if ((txt.includes('wyślij wiadomo') || txt === 'message') && el.offsetParent !== null) {
                                return el;
                            }
                        }
                        return null;
                    }""")
                    if msg_btn and str(msg_btn) != "null":
                        msg_btn = msg_btn.as_element()
                    else:
                        msg_btn = None
                except Exception:
                    msg_btn = None

            if not msg_btn:
                print("   ❌ Nie znalazłem 'Wyślij wiadomość' — pomijam.")
                handle_skip(page, page_slug, username, restore=True)
                continue

            msg_btn.click()
            short_pause(2, 3)

            # Pole tekstowe w DM
            textarea = None
            for sel in [
                "div[role='textbox'][contenteditable='true']",
                "textarea[placeholder*='Message']",
                "textarea[placeholder*='Wyślij wiadomość']",
                "textarea",
            ]:
                try:
                    textarea = page.wait_for_selector(sel, timeout=5000)
                    if textarea and textarea.is_visible():
                        break
                    textarea = None
                except PwTimeout:
                    textarea = None

            if not textarea:
                print("   ❌ Nie znalazłem pola wiadomości — pomijam.")
                handle_skip(page, page_slug, username, restore=True)
                continue

            textarea.click()
            short_pause(0.3, 0.6)

            # Wpisz wiadomość bez użycia systemowego schowka
            # (insert_text emituje jeden event 'input', szybkie i bez kolizji)
            page.keyboard.insert_text(message)
            short_pause(1.2, 2.0)

            # Wyślij
            send_btn = page.query_selector("button:has-text('Wyślij')") or \
                       page.query_selector("button:has-text('Send')")
            if send_btn and send_btn.is_visible():
                send_btn.click()
            else:
                page.keyboard.press("Enter")

            short_pause(1.2, 2.0)
            sent += 1
            print(f"   ✅ Wysłano! ({sent}/{count})")
            clear_attempt(page_slug, username)

            # Wróć na Netlify i zaznacz checkbox
            restore_netlify(page)

            cards = page.query_selector_all(".profile-card")
            for card in cards:
                uname = card.query_selector(".profile-username a")
                if uname and uname.inner_text() == username:
                    cb = card.query_selector("input[type='checkbox']")
                    if cb and not cb.is_checked():
                        cb.click()
                        short_pause(0.5, 1.0)
                        print(f"   ☑️  Zaznaczono {username}")
                    break

            # Pauza między wiadomościami
            if i < count - 1:
                lo = max(base_delay - 15, 20)
                hi = base_delay + 15
                random_delay(lo, hi)

    except KeyboardInterrupt:
        print("\n\n⛔ Przerwano ręcznie (Ctrl+C).")
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
    finally:
        print(f"\n📊 Podsumowanie: wysłano {sent} wiadomości.")
        input("   Naciśnij Enter żeby zamknąć przeglądarkę...")
        ctx.close()


def main():
    global SITE_URL, GROQ_MODEL
    parser = argparse.ArgumentParser(description="IG DM Bot")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help=f"Ile wiadomości wysłać (domyślnie {DEFAULT_COUNT})")
    parser.add_argument("--delay", type=int, default=60,
                        help="Średni czas przerwy między wiadomościami (domyślnie 60s)")
    parser.add_argument("--page", default="",
                        help="Podstrona na Netlify (np. 'paznokcie'). Puste = strona główna.")
    parser.add_argument("--index", type=int, default=None,
                        help="Indeks (od 1) profilu z listy nienapisanych. "
                             "Jeśli nie podany — zapyta w konsoli.")
    parser.add_argument("--profile", type=str, default=None,
                        help="Numer/nazwa profilu przeglądarki "
                             "(np. 1 -> .ig_browser_profile1). "
                             "Jeśli nie podany — zapyta w konsoli.")
    parser.add_argument("--ai", action="store_true",
                        help="Generuj spersonalizowane wiadomości przez Groq API "
                             "na podstawie bio i postów (wymaga GROQ_API_KEY w .env).")
    parser.add_argument("--groq-model", type=str, default=None,
                        help=f"Model Groq (domyślnie {GROQ_MODEL}).")
    args = parser.parse_args()

    if args.ai and not GROQ_API_KEY:
        sys.exit("❌ --ai wymaga GROQ_API_KEY w .env (https://console.groq.com/keys)")
    if args.groq_model:
        GROQ_MODEL = args.groq_model

    # Dostosuj URL do wybranej podstrony
    if args.page:
        SITE_URL = SITE_URL.rstrip("/") + "/" + args.page.strip("/")
        print(f"🎯 Tryb: {args.page} ({SITE_URL})")

    if args.index is not None:
        target_index = args.index - 1
    else:
        while True:
            raw = input("Od którego indeksu (od 1) z nienapisanych zacząć? ").strip()
            try:
                target_index = int(raw) - 1
                if target_index < 0:
                    raise ValueError
                break
            except ValueError:
                print("   ❌ Podaj liczbę całkowitą >= 1.")

    if args.profile is not None:
        profile_choice = args.profile.strip()
    else:
        profile_choice = input(
            "Numer profilu przeglądarki (np. 1, 2, 3, 4) "
            "lub Enter dla domyślnego: "
        ).strip()

    if profile_choice:
        profile_dir = os.path.join(BASE_DIR, f".ig_browser_profile{profile_choice}")
    else:
        profile_dir = PROFILE_DIR

    print(f"▶️  Bot będzie pisał do profilu o indeksie {target_index + 1} "
          f"z listy nienapisanych (po każdym DM lista się odświeży).")
    print(f"   📁 Profil przeglądarki: {profile_dir}")
    if args.ai:
        print(f"   🧠 AI: Groq ({GROQ_MODEL}) — spersonalizowane wiadomości")

    with sync_playwright() as pw:
        send_messages(pw, args.count, args.delay, target_index, profile_dir,
                      use_ai=args.ai, page_slug=(args.page or "").strip("/"))


if __name__ == "__main__":
    main()
