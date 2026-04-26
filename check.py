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
    try:
        close = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(text())='SCHLIESSEN']"))
        )
        driver.execute_script("arguments[0].click();", close)
    except:
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            pass
    time.sleep(1.5)


def monatsnamen_lesen(driver):
    try:
        feld = driver.find_element(By.XPATH, "//input[@type='text']")
        wert = feld.get_attribute("value")
        if wert:
            return wert.strip()
    except:
        pass
    return "Unbekannter Monat"


def naechsten_monat_klicken(driver):
    """
    Versucht den Weiter-Pfeil auf mehrere Arten zu finden.
    Gibt debug-Info aus damit man sieht was gefunden wurde.
    """

    # DEBUG: alle Buttons auf der Seite ausgeben
    alle_buttons = driver.find_elements(By.TAG_NAME, "button")
    print(f"  DEBUG: {len(alle_buttons)} Buttons total auf der Seite")
    for idx, b in enumerate(alle_buttons):
        try:
            klassen = b.get_attribute("class") or ""
            text = b.text.strip()[:30]
            aria = b.get_attribute("aria-label") or ""
            title = b.get_attribute("title") or ""
            print(f"    Button[{idx}]: class='{klassen}' text='{text}' aria='{aria}' title='{title}'")
        except:
            pass

    # Strategie 1: btn-warning (gelbe Buttons) - zweiter ist "vor"
    btns = driver.find_elements(By.CSS_SELECTOR, "button.btn-warning")
    print(f"  btn-warning gefunden: {len(btns)}")
    if len(btns) >= 2:
        driver.execute_script("arguments[0].click();", btns[1])
        time.sleep(3)
        return True
    elif len(btns) == 1:
        # Nur ein Button - trotzdem versuchen
        driver.execute_script("arguments[0].click();", btns[0])
        time.sleep(3)
        return True

    # Strategie 2: Button mit Pfeil-Text oder aria-label
    for aria in ["next", "Next", "Nächster", "naechster", "vor", "forward"]:
        btns = driver.find_elements(By.XPATH, f"//button[@aria-label='{aria}' or @title='{aria}']")
        if btns:
            print(f"  Weiter-Button via aria-label='{aria}' gefunden")
            driver.execute_script("arguments[0].click();", btns[0])
            time.sleep(3)
            return True

    # Strategie 3: Button der nach dem Monats-Input kommt
    try:
        monat_input = driver.find_element(By.XPATH, "//input[@type='text']")
        # Alle Buttons nach dem Input
        parent = monat_input.find_element(By.XPATH, "./ancestor::div[contains(@class,'row') or contains(@class,'d-flex')][1]")
        buttons_im_bereich = parent.find_elements(By.TAG_NAME, "button")
        print(f"  Buttons im Monats-Bereich: {len(buttons_im_bereich)}")
        if len(buttons_im_bereich) >= 2:
            # Letzter Button = Weiter
            driver.execute_script("arguments[0].click();", buttons_im_bereich[-1])
            time.sleep(3)
            return True
    except Exception as e:
        print(f"  Strategie 3 Fehler: {e}")

    print("  KEIN Weiter-Button gefunden!")
    return False


def monat_scannen(driver, frueh_schichten, monat_name):
    time.sleep(3)

    tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
    tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]
    print(f"\n{monat_name}: {len(tage)} Tage mit freien Schichten")

    for i in range(len(tage)):
        tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
        tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]

        if i >= len(tage):
            break

        tag = tage[i]

        datum = monat_name
        try:
            zelle = tag.find_element(By.XPATH, "./ancestor::td")
            zeilen = zelle.text.strip().split("\n")
            tageszahl = zeilen[0].strip()
            if tageszahl.isdigit():
                datum = f"{tageszahl}. {monat_name}"
        except:
            pass

        print(f"  {datum} ({tag.text.strip()}) ...")

        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tag)
            time.sleep(0.4)
            driver.execute_script("arguments[0].click();", tag)
            time.sleep(3)

            try:
                WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located((By.XPATH, "//button[normalize-space(text())='SCHLIESSEN']"))
                )
            except:
                print(f"    -> Kein Popup")
                continue

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
        if naechsten_monat_klicken(driver):
            monat_2 = monatsnamen_lesen(driver)
            # Prüfen ob wirklich weitergeblättert wurde
            if monat_2 != monat_1:
                print(f"\n=== MONAT 2: {monat_2} ===")
                monat_scannen(driver, frueh_schichten, monat_2)
            else:
                print("  Monat hat sich nicht geändert - Button hat nicht funktioniert")
                telegram_senden("Weiter-Button hat Monat nicht gewechselt – nur aktueller Monat geprüft.")
        else:
            telegram_senden("Weiter-Button nicht gefunden – nur aktueller Monat geprüft.")

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
