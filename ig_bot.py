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
import os
import random
import sys
import time

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

IG_USERNAME = os.environ.get("IG_USERNAME", "")
IG_PASSWORD = os.environ.get("IG_PASSWORD", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

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


def short_pause(lo=1.5, hi=3.5):
    time.sleep(random.uniform(lo, hi))


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
    short_pause(5, 8)
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
    short_pause(3, 5)
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
            short_pause(3, 5)
            dismiss_ig_popups(page)
            short_pause(2, 3)
            dismiss_ig_popups(page)
            print("✅ Zalogowano na Instagram! Kontynuuję...")
            return


def setup_netlify(page):
    """Loguje na stronie Netlify, wpisuje token, ustawia filtr."""
    page.goto(SITE_URL, wait_until="networkidle")
    short_pause()

    # Zaloguj jako pierwszy user
    login_screen = page.query_selector("#loginScreen")
    if login_screen and login_screen.is_visible():
        login_btns = page.query_selector_all(".login-btn")
        if login_btns:
            login_btns[0].click()
            short_pause()
            print("   Zalogowano na stronie jako pierwszy user.")

    # Wpisz token GitHub i zsynchronizuj
    token_input = page.query_selector("#tokenInput")
    if token_input:
        token_input.fill(GITHUB_TOKEN)
        short_pause(0.5, 1.0)
        save_btn = page.query_selector("button:has-text('Zapisz token')")
        if save_btn:
            save_btn.click()
            print("   🔑 Token GitHub zapisany, synchronizacja...")
            short_pause(4, 6)

    # Ustaw filtr na "Nienapisane"
    status_filter = page.query_selector("#statusFilter")
    if status_filter:
        status_filter.select_option("pending")
        short_pause(1, 2)
        print("   🔍 Filtr: tylko nienapisane profile.")


def restore_netlify(page):
    """Wraca na stronę Netlify i przywraca stan (login + filtr)."""
    page.goto(SITE_URL, wait_until="networkidle")
    short_pause(2, 3)

    login_screen = page.query_selector("#loginScreen")
    if login_screen and login_screen.is_visible():
        login_btns = page.query_selector_all(".login-btn")
        if login_btns:
            login_btns[0].click()
            short_pause()

    status_filter = page.query_selector("#statusFilter")
    if status_filter:
        status_filter.select_option("pending")
        short_pause(0.5, 1.0)


# ─── MAIN FLOW ───────────────────────────────────────────────────────────────

def send_messages(pw, count, base_delay):
    ctx = pw.chromium.launch_persistent_context(
        PROFILE_DIR,
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

            # Znajdź pierwszy niezaznaczony profil
            cards = page.query_selector_all(".profile-card")
            target_card = None
            for card in cards:
                cb = card.query_selector("input[type='checkbox']")
                if cb and not cb.is_checked():
                    target_card = card
                    break

            if not target_card:
                print("⚠️  Brak niezaznaczonych profili — kończę.")
                break

            username_el = target_card.query_selector(".profile-username a")
            username = username_el.inner_text() if username_el else "?"
            city_el = target_card.query_selector(".profile-meta")
            city = city_el.inner_text().split("·")[0].strip() if city_el else "?"
            print(f"   👤 {username} ({city})")

            # Kliknij "Kopiuj"
            copy_btn = target_card.query_selector(".btn-copy")
            if not copy_btn:
                print("   ❌ Brak przycisku Kopiuj — pomijam.")
                continue
            copy_btn.click()
            short_pause(0.5, 1.0)

            # Odczytaj ze schowka
            message = page.evaluate("() => navigator.clipboard.readText()")
            if not message or "trener personalny" not in message:
                print("   ❌ Schowek pusty lub zła treść — pomijam.")
                continue
            print(f"   📋 Skopiowano wiadomość ({len(message)} znaków)")

            # Otwórz profil IG
            ig_link = target_card.query_selector("a.btn-pink")
            ig_url = ig_link.get_attribute("href") if ig_link else None
            if not ig_url:
                print("   ❌ Brak linku IG — pomijam.")
                continue

            goto_ig(page, ig_url)
            short_pause(5, 8)
            dismiss_ig_popups(page)

            # Sprawdź czy sesja wygasła
            if not is_logged_in_ig(page):
                print("   ⚠️  Sesja IG wygasła!")
                ensure_ig_session(page)
                goto_ig(page, ig_url)
                short_pause(5, 8)

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
                short_pause(2, 4)
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
                restore_netlify(page)
                continue

            msg_btn.click()
            short_pause(3, 5)

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
                restore_netlify(page)
                continue

            textarea.click()
            short_pause(0.3, 0.6)

            # Wklej całą wiadomość ze schowka (Ctrl+V) — bezpieczniej niż type()
            page.evaluate("(txt) => navigator.clipboard.writeText(txt)", message)
            short_pause(0.3, 0.5)
            page.keyboard.press("Control+v")
            short_pause(2, 3)

            # Wyślij
            send_btn = page.query_selector("button:has-text('Wyślij')") or \
                       page.query_selector("button:has-text('Send')")
            if send_btn and send_btn.is_visible():
                send_btn.click()
            else:
                page.keyboard.press("Enter")

            short_pause(2, 3)
            sent += 1
            print(f"   ✅ Wysłano! ({sent}/{count})")

            # Wróć na Netlify i zaznacz checkbox
            restore_netlify(page)

            cards = page.query_selector_all(".profile-card")
            for card in cards:
                uname = card.query_selector(".profile-username a")
                if uname and uname.inner_text() == username:
                    cb = card.query_selector("input[type='checkbox']")
                    if cb and not cb.is_checked():
                        cb.click()
                        short_pause(1, 2)
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
    parser = argparse.ArgumentParser(description="IG DM Bot")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help=f"Ile wiadomości wysłać (domyślnie {DEFAULT_COUNT})")
    parser.add_argument("--delay", type=int, default=60,
                        help="Średni czas przerwy między wiadomościami (domyślnie 60s)")
    args = parser.parse_args()

    with sync_playwright() as pw:
        send_messages(pw, args.count, args.delay)


if __name__ == "__main__":
    main()
