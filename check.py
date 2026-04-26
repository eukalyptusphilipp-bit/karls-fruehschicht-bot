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
    """Schliesst Popup – akzeptiert SCHLIESSEN (DE) und CLOSE (EN)."""
    for text in ["SCHLIESSEN", "CLOSE"]:
        try:
            btn = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//button[normalize-space(text())='{text}']")
                )
            )
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
            return
        except:
            pass
    # Fallback: ESC
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except:
        pass
    time.sleep(2)


def popup_warten(driver):
    """Wartet bis Popup offen ist – erkennt SCHLIESSEN oder CLOSE."""
    try:
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//button[normalize-space(text())='SCHLIESSEN' or normalize-space(text())='CLOSE']"
            ))
        )
        return True
    except:
        return False


def monatsnamen_lesen(driver):
    """Liest den Monatsnamen – z.B. 'Mai 2026'."""
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
    Klickt den Weiter-Pfeil.
    Aus dem HTML wissen wir: es ist ein <div> mit title="Nächster Monat"
    und class="button-orange-gradient" – KEIN <button>!
    """
    selektoren = [
        "div[title='Nächster Monat']",
        "div[title='Next month']",
        "div[title='Naechster Monat']",
        "div.button-orange-gradient",
    ]

    for sel in selektoren:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        # Es gibt zwei orange Pfeile (zurück + vor), nehme den letzten
        if elems:
            ziel = elems[-1]
            print(f"  Weiter-Button gefunden: {sel} (Index {len(elems)-1})")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", ziel)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", ziel)
            time.sleep(3)
            neuer_monat = monatsnamen_lesen(driver)
            if neuer_monat != monat_vorher:
                print(f"  Monat gewechselt: {monat_vorher} -> {neuer_monat}")
                return True
            else:
                print(f"  Klick hat Monat nicht gewechselt, versuche naechsten Selektor...")

    print("  Kein Weiter-Button gefunden!")
    return False


def monat_scannen(driver, frueh_schichten, monat_name):
    """
    Findet alle Tage mit freien Schichten und klickt den klickbaren
    Container (div.cursor-pointer.fw-bold) an – nicht den inneren Text-div.
    """
    time.sleep(3)

    # Klickbarer Container der freien Schichten (aus HTML bekannt)
    # Struktur: div.row.m-0.border.mt-2.rounded.cursor-pointer.fw-bold
    #   └── div.col  └── div.col.text-center  "08 freie Schichten"
    container_sel = "div.cursor-pointer.fw-bold"
    alle_container = driver.find_elements(By.CSS_SELECTOR, container_sel)
    # Nur die mit "freie Schicht" oder "free shift" im Text
    tage = [
        c for c in alle_container
        if "freie Schicht" in c.text or "free shift" in c.text.lower()
    ]

    # Fallback: innerer div (alter Selektor)
    if not tage:
        tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
        tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]
        print(f"  Fallback-Selektor genutzt")

    print(f"\n{monat_name}: {len(tage)} Tage mit freien Schichten")

    for i in range(len(tage)):
        # Nach jedem Klick neu laden
        alle_container = driver.find_elements(By.CSS_SELECTOR, container_sel)
        tage = [
            c for c in alle_container
            if "freie Schicht" in c.text or "free shift" in c.text.lower()
        ]
        if not tage:
            tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
            tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]

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
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tag)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", tag)
            time.sleep(3)

            if not popup_warten(driver):
                print(f"    -> Kein Popup gefunden")
                continue

            # Dialog-Text auslesen
            dialog = driver.find_element(By.CSS_SELECTOR, "mat-dialog-container")
            alle_zeilen = dialog.text.split("\n")

            frueh_gefunden = False
            for idx, zeile in enumerate(alle_zeilen):
                zeile = zeile.strip()
                if not zeile or "FRÜH" not in zeile.upper():
                    continue
                # Kontext prüfen: Vorläufige Planung ignorieren
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
