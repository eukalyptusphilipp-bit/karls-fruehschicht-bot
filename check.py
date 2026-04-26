import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

USERNAME = os.environ["KARLS_USERNAME"]
PASSWORD = os.environ["KARLS_PASSWORD"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

BEKANNTE_FILE = "bekannte_schichten.json"


def telegram_senden(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text[:4000]})


def laden():
    try:
        with open(BEKANNTE_FILE) as f:
            return set(json.load(f))
    except:
        return set()


def speichern(schichten):
    with open(BEKANNTE_FILE, "w") as f:
        json.dump(list(schichten), f)


def popup_schliessen(driver):
    """Versucht das Popup auf mehrere Arten zu schließen."""
    geschlossen = False
    # Versuche 1: SCHLIESSEN-Button (Deutsch & Englisch)
    for text in ["SCHLIESSEN", "CLOSE", "Schließen", "Close"]:
        buttons = driver.find_elements(
            By.XPATH, f"//button[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'), '{text.upper()}')]"
        )
        if buttons:
            try:
                driver.execute_script("arguments[0].click();", buttons[0])
                geschlossen = True
                break
            except:
                pass

    # Versuche 2: X-Button / mat-dialog-close
    if not geschlossen:
        for sel in ["button[mat-dialog-close]", "button.close", ".mat-dialog-close", "[aria-label='close']", "[aria-label='Close']"]:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            if elems:
                try:
                    driver.execute_script("arguments[0].click();", elems[0])
                    geschlossen = True
                    break
                except:
                    pass

    # Versuche 3: ESC
    if not geschlossen:
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            pass

    time.sleep(1.5)


def popup_offen(driver):
    """Gibt True zurück wenn ein Modal/Dialog offen ist."""
    dialoge = driver.find_elements(By.CSS_SELECTOR, "mat-dialog-container, .modal, .cdk-overlay-container .cdk-overlay-pane")
    return any(d.is_displayed() for d in dialoge)


def fruehschicht_im_popup(driver):
    """
    Sucht im offenen Popup nach FRÜH-Schichten.
    Ignoriert 'Vorläufige Planung' / 'Preliminary'.
    Gibt Liste von Schicht-Texten zurück.
    """
    gefunden = []

    # Alle Elemente die FRÜH oder EARLY enthalten
    kandidaten = driver.find_elements(
        By.XPATH, "//*[contains(text(), 'FRÜH') or contains(text(), 'Früh') or contains(text(), 'EARLY') or contains(text(), 'Early')]"
    )

    for elem in kandidaten:
        try:
            zeile = elem.text.strip()
            if not zeile or len(zeile) < 3:
                continue

            # Vorläufige Planung / Preliminary überspringen
            try:
                eltern_text = elem.find_element(By.XPATH, "..").text
                if any(x in eltern_text for x in ["Vorläufige", "Preliminary", "vorläufig"]):
                    continue
            except:
                pass

            # Nur Zeilen mit echtem Schicht-Inhalt (Zeit oder Beschreibung)
            if "FRÜH" in zeile.upper():
                gefunden.append(zeile)
        except:
            continue

    return gefunden


def alle_tage_im_monat(driver):
    """
    Gibt alle klickbaren Kalendertag-Zellen zurück.
    Versucht mehrere Selektoren um robust zu sein.
    """
    tage = []

    # Strategie 1: <td> mit einer Tageszahl (typisch für Angular-Kalender)
    for sel in [
        "td.cal-day-cell",
        "td[class*='day']",
        "td[class*='cal-day']",
        ".fc-daygrid-day",          # FullCalendar
        "td[data-date]",
        "div[class*='day-cell']",
    ]:
        tage = driver.find_elements(By.CSS_SELECTOR, sel)
        if tage:
            print(f"  → Tage gefunden mit Selektor: {sel} ({len(tage)} Zellen)")
            break

    # Strategie 2: Alle <td> im Kalender-Bereich die eine Zahl enthalten
    if not tage:
        alle_td = driver.find_elements(By.CSS_SELECTOR, "table td")
        tage = [
            td for td in alle_td
            if td.text.strip().split("\n")[0].strip().isdigit()
        ]
        print(f"  → Fallback: {len(tage)} <td>-Zellen mit Tageszahl")

    return tage


def monat_scannen(driver, frueh_schichten, monat_name):
    """Klickt JEDEN Tag im Kalender an und prüft auf FRÜH-Schichten."""
    time.sleep(3)

    tage = alle_tage_im_monat(driver)
    print(f"\n📅 {monat_name}: {len(tage)} Tage gefunden – jeden anklicken...\n")

    for i in range(len(tage)):
        # Tage-Liste nach jedem Klick neu holen (DOM kann sich ändern)
        tage = alle_tage_im_monat(driver)
        if i >= len(tage):
            print(f"  Tag {i+1}: nicht mehr vorhanden, überspringe")
            break

        tag_zelle = tage[i]

        # Datum aus der Zelle lesen
        datum = monat_name
        try:
            zellen_text = tag_zelle.text.strip().split("\n")
            tageszahl = zellen_text[0].strip()
            if tageszahl.isdigit():
                datum = f"{tageszahl}. {monat_name}"
        except:
            pass

        # Vergangene / deaktivierte Tage überspringen
        try:
            klassen = tag_zelle.get_attribute("class") or ""
            if any(x in klassen for x in ["disabled", "past", "grey", "gray", "other-month", "cal-out-month"]):
                continue
        except:
            pass

        print(f"  🔍 {datum} anklicken...")

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tag_zelle)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", tag_zelle)
            time.sleep(2.5)

            # Prüfen ob Popup geöffnet wurde
            if not popup_offen(driver):
                # Manchmal braucht es länger
                time.sleep(1.5)
                if not popup_offen(driver):
                    print(f"    → Kein Popup für {datum}")
                    continue

            # FRÜH-Schichten im Popup suchen
            schichten = fruehschicht_im_popup(driver)
            for s in schichten:
                eintrag = f"{datum} – {s}"
                frueh_schichten.add(eintrag)
                print(f"    ✅ FRÜH gefunden: {eintrag}")

            if not schichten:
                print(f"    → Keine FRÜH-Schicht")

            popup_schliessen(driver)

        except Exception as e:
            print(f"    ⚠️ Fehler bei {datum}: {e}")
            try:
                popup_schliessen(driver)
            except:
                pass
            continue


def monatsnamen_lesen(driver):
    """Liest den aktuell angezeigten Monatsnamen aus dem Kalender."""
    for sel in [
        "//input[@type='text']",
        "//*[contains(@class,'month-title')]",
        "//*[contains(@class,'cal-month-title')]",
        "//*[contains(@class,'fc-toolbar-title')]",
    ]:
        try:
            elem = driver.find_element(By.XPATH, sel)
            wert = elem.get_attribute("value") or elem.text
            if wert and len(wert) > 2:
                return wert.strip()
        except:
            continue
    return "Unbekannter Monat"


def schichten_abrufen():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    frueh_schichten = set()

    try:
        # ── Login ──────────────────────────────────────────────
        driver.get("https://pep.karls.de/login")
        time.sleep(5)

        wait = WebDriverWait(driver, 20)

        # Employee-ID Feld
        id_feld = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "[formcontrolname='employeeId'] input, input[formcontrolname='employeeId']"
        )))
        id_feld.clear()
        id_feld.send_keys(USERNAME)

        # Passwort Feld
        pw_feld = driver.find_element(
            By.CSS_SELECTOR,
            "[formcontrolname='password'] input, input[formcontrolname='password']"
        )
        pw_feld.clear()
        pw_feld.send_keys(PASSWORD)
        time.sleep(1)

        # Login-Button
        buttons = driver.find_elements(By.XPATH, "//button[@type='submit']")
        if buttons:
            driver.execute_script("arguments[0].click();", buttons[0])
        time.sleep(5)

        # ── Kalender laden ─────────────────────────────────────
        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        # ── Aktueller Monat ────────────────────────────────────
        monat_1 = monatsnamen_lesen(driver)
        print(f"\n=== Monat 1: {monat_1} ===")
        monat_scannen(driver, frueh_schichten, monat_1)

        # ── Nächster Monat ─────────────────────────────────────
        # "Weiter"-Button suchen (gelb = btn-warning, oder Pfeil-Button)
        weiter_geklickt = False
        for sel in [
            "button.btn-warning",
            "button[aria-label='Next']",
            "button[aria-label='next']",
            ".cal-next-month",
            "button.fc-next-button",
        ]:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            # Nimm den letzten / zweiten gefundenen (oft gibt es Zurück + Weiter)
            if len(btns) >= 2:
                driver.execute_script("arguments[0].click();", btns[-1])
                weiter_geklickt = True
                break
            elif len(btns) == 1:
                driver.execute_script("arguments[0].click();", btns[0])
                weiter_geklickt = True
                break

        if weiter_geklickt:
            time.sleep(3)
            monat_2 = monatsnamen_lesen(driver)
            print(f"\n=== Monat 2: {monat_2} ===")
            monat_scannen(driver, frueh_schichten, monat_2)
        else:
            print("⚠️ Weiter-Button für nächsten Monat nicht gefunden.")
            telegram_senden("⚠️ Weiter-Button nicht gefunden – nur aktueller Monat wurde geprüft.")

    except Exception as e:
        print(f"🔴 Hauptfehler: {e}")
        telegram_senden(f"⚠️ Bot Fehler: {e}")
    finally:
        driver.quit()

    return frueh_schichten


# ── Hauptprogramm ──────────────────────────────────────────────────────────────
print("🔍 Prüfe auf neue Frühschichten (jeden Tag)...")
aktuell = schichten_abrufen()
bekannt = laden()
neu = aktuell - bekannt

if neu:
    nachricht = "🍓 NEUE FRÜHSCHICHT bei Karls!\n\n"
    for s in sorted(neu):
        nachricht += f"• {s}\n"
    telegram_senden(nachricht)
    print(f"✅ {len(neu)} neue Schicht(en) – Telegram gesendet!")
else:
    print("✅ Keine neuen Frühschichten.")

speichern(aktuell)
