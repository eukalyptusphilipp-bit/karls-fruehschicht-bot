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


def popup_ist_offen(driver):
    """Prueft ob mat-dialog-container sichtbar ist."""
    try:
        dialoge = driver.find_elements(By.CSS_SELECTOR, "mat-dialog-container")
        return any(d.is_displayed() for d in dialoge)
    except:
        return False


def popup_warten(driver, sekunden=8):
    """Wartet bis mat-dialog-container erscheint."""
    try:
        WebDriverWait(driver, sekunden).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "mat-dialog-container"))
        )
        time.sleep(1)  # kurz warten bis Inhalt geladen
        return popup_ist_offen(driver)
    except:
        return False


def popup_schliessen(driver):
    """
    Schliesst Popup.
    Der Button hat CSS-Klasse 'outlined-button' und text-uppercase.
    Aktuelle DOM-Texte koennen sein: Schließen, Close, SCHLIESSEN, CLOSE.
    """
    geschlossen = False

    # Strategie 1: per Klasse (zuverlaessigste Methode)
    for sel in ["button.outlined-button", "button[class*='outlined-button']"]:
        btns = driver.find_elements(By.CSS_SELECTOR, sel)
        for btn in btns:
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    geschlossen = True
                    break
            except:
                pass
        if geschlossen:
            break

    # Strategie 2: per Text (alle Varianten)
    if not geschlossen:
        for text in ["SCHLIESSEN", "CLOSE", "Schließen", "Close", "schließen", "close"]:
            btns = driver.find_elements(By.XPATH, f"//button[contains(.,'{text}')]")
            for btn in btns:
                try:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        geschlossen = True
                        break
                except:
                    pass
            if geschlossen:
                break

    # Strategie 3: X-Button (aria-label)
    if not geschlossen:
        for sel in ["button[aria-label='Close']", "button[title='Close']", "button[aria-label='Schließen']"]:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            if btns:
                try:
                    driver.execute_script("arguments[0].click();", btns[0])
                    geschlossen = True
                    break
                except:
                    pass

    # Strategie 4: ESC
    if not geschlossen:
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            pass

    time.sleep(2)

    # Sicherstellen dass Dialog zu ist
    for _ in range(3):
        if not popup_ist_offen(driver):
            break
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            pass
        time.sleep(1)


def monatsnamen_lesen(driver):
    # Versuch 1: input type=text
    try:
        feld = driver.find_element(By.XPATH, "//input[@type='text']")
        wert = feld.get_attribute("value")
        if wert and len(wert) > 2:
            return wert.strip()
    except:
        pass

    # Versuch 2: Kendo DatePicker
    for sel in ["kendo-datepicker input", ".k-datepicker input"]:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, sel)
            wert = elem.get_attribute("value") or elem.text
            if wert and len(wert) > 2:
                return wert.strip()
        except:
            pass

    # Versuch 3: Text mit Jahreszahl
    try:
        elems = driver.find_elements(
            By.XPATH,
            "//*[contains(text(),'2025') or contains(text(),'2026') or contains(text(),'2027')]"
        )
        for e in elems:
            t = e.text.strip()
            if 4 <= len(t) <= 20 and any(str(y) in t for y in [2025, 2026, 2027]):
                return t
    except:
        pass

    return "Unbekannter Monat"


def naechsten_monat_klicken(driver, monat_vorher):
    """
    Weiter-Button ist ein <div> mit title='Nächster Monat'
    und class='button-orange-gradient'.
    """
    selektoren = [
        "div[title='Nächster Monat']",
        "div[title='Next month']",
        "div.button-orange-gradient",
    ]

    for sel in selektoren:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            ziel = elems[-1]  # letzter = Vorwärts-Pfeil
            print(f"  Weiter-Button: {sel}")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ziel)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", ziel)
            time.sleep(3)
            neuer_monat = monatsnamen_lesen(driver)
            if neuer_monat != monat_vorher:
                print(f"  OK: {monat_vorher} -> {neuer_monat}")
                return True

    print("  Kein Weiter-Button gefunden!")
    return False


def tag_anklicken(driver, element):
    """
    Versucht ein Kalender-Tag-Element anzuklicken.
    Probiert mehrere Methoden bis das Popup aufgeht.
    """
    # Methode 1: JS click auf Element selbst
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", element)
    time.sleep(2.5)
    if popup_ist_offen(driver):
        return True

    # Methode 2: Normaler Selenium click
    try:
        element.click()
        time.sleep(2.5)
        if popup_ist_offen(driver):
            return True
    except:
        pass

    # Methode 3: Klick auf inneres div.col.text-center
    try:
        inner = element.find_element(By.CSS_SELECTOR, "div.col.text-center")
        driver.execute_script("arguments[0].click();", inner)
        time.sleep(2.5)
        if popup_ist_offen(driver):
            return True
    except:
        pass

    # Methode 4: Klick auf uebergeordnetes td
    try:
        td = element.find_element(By.XPATH, "./ancestor::td")
        driver.execute_script("arguments[0].click();", td)
        time.sleep(2.5)
        if popup_ist_offen(driver):
            return True
    except:
        pass

    return False


def freie_tage_finden(driver):
    """Gibt alle Elemente zurueck die freie Schichten anzeigen."""
    # Primaer: klickbarer Container
    tage = driver.find_elements(By.CSS_SELECTOR, "div.cursor-pointer.fw-bold")
    tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]
    if tage:
        return tage

    # Fallback: innerer Text-div
    tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
    tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]
    return tage


def monat_scannen(driver, frueh_schichten, monat_name):
    time.sleep(3)

    tage = freie_tage_finden(driver)
    print(f"\n{monat_name}: {len(tage)} Tage mit freien Schichten")

    for i in range(len(tage)):
        tage = freie_tage_finden(driver)
        if i >= len(tage):
            break

        tag = tage[i]

        # Datum lesen
        datum = monat_name
        try:
            zelle = tag.find_element(By.XPATH, "./ancestor::td")
            zeilen = zelle.text.strip().split("\n")
            tageszahl = zeilen[0].strip()
            if tageszahl.isdigit():
                datum = f"{tageszahl}. {monat_name}"
        except:
            pass

        print(f"  {datum} ({tag.text.strip()[:30]}) ...")

        try:
            geoeffnet = tag_anklicken(driver, tag)

            if not geoeffnet:
                # Letzter Versuch: nochmal warten
                geoeffnet = popup_warten(driver, sekunden=5)

            if not geoeffnet:
                print(f"    -> Kein Popup trotz mehrerer Versuche")
                continue

            # Dialog-Text auslesen
            dialog = driver.find_element(By.CSS_SELECTOR, "mat-dialog-container")
            alle_zeilen = dialog.text.split("\n")

            frueh_gefunden = False
            for idx, zeile in enumerate(alle_zeilen):
                zeile = zeile.strip()
                if not zeile or "FRÜH" not in zeile.upper():
                    continue
                kontext = " ".join(alle_zeilen[max(0, idx - 2):idx + 3])
                if "Vorläufige" in kontext or "Preliminary" in kontext:
                    continue
                eintrag = f"{datum} – {zeile}"
                if eintrag not in frueh_schichten:
                    frueh_schichten.add(eintrag)
                    frueh_gefunden = True
                    print(f"    FRUEH: {eintrag}")

            if not frueh_gefunden:
                print(f"    -> Keine FRUEH-Schicht")

            popup_schliessen(driver)

        except Exception as e:
            print(f"    Fehler: {e}")
            try:
                popup_schliessen(driver)
            except:
                pass
            continue


def schichten_abrufen():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=de-DE")
    options.add_experimental_option("prefs", {"intl.accept_languages": "de,de-DE"})

    driver = webdriver.Chrome(options=options)
    frueh_schichten = set()

    try:
        # Login
        driver.get("https://pep.karls.de/login")
        time.sleep(5)

        wait = WebDriverWait(driver, 20)
        id_feld = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "[formcontrolname='employeeId'] input, input[formcontrolname='employeeId']"
        )))
        id_feld.clear()
        id_feld.send_keys(USERNAME)

        pw_feld = driver.find_element(
            By.CSS_SELECTOR,
            "[formcontrolname='password'] input, input[formcontrolname='password']"
        )
        pw_feld.clear()
        pw_feld.send_keys(PASSWORD)
        time.sleep(1)

        submit = driver.find_elements(By.XPATH, "//button[@type='submit']")
        if submit:
            driver.execute_script("arguments[0].click();", submit[0])
        time.sleep(5)

        # Kalender
        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        # Monat 1
        monat_1 = monatsnamen_lesen(driver)
        print(f"\n=== MONAT 1: {monat_1} ===")
        monat_scannen(driver, frueh_schichten, monat_1)

        # Monat 2
        print(f"\n-> Naechster Monat...")
        if naechsten_monat_klicken(driver, monat_1):
            monat_2 = monatsnamen_lesen(driver)
            print(f"\n=== MONAT 2: {monat_2} ===")
            monat_scannen(driver, frueh_schichten, monat_2)
        else:
            telegram_senden("Weiter-Button nicht gefunden – nur aktueller Monat geprueft.")

    except Exception as e:
        print(f"Hauptfehler: {e}")
        telegram_senden(f"Bot Fehler: {e}")
    finally:
        driver.quit()

    return frueh_schichten


# Start
print("Pruefe auf neue Fruehschichten...")
aktuell = schichten_abrufen()
bekannt = laden()
neu = aktuell - bekannt

if neu:
    nachricht = "NEUE FRUEHSCHICHT bei Karls!\n\n"
    for s in sorted(neu):
        nachricht += f"- {s}\n"
    telegram_senden(nachricht)
    print(f"{len(neu)} neue Schicht(en) - Telegram gesendet!")
else:
    print("Keine neuen Fruehschichten.")

speichern(aktuell)
