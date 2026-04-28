import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
            return json.load(f)
    except:
        return {}


def speichern(daten):
    with open(BEKANNTE_FILE, "w") as f:
        json.dump(daten, f)


def monatsnamen_lesen(driver):
    try:
        feld = driver.find_element(By.XPATH, "//input[@type='text']")
        wert = feld.get_attribute("value")
        if wert and len(wert) > 2:
            return wert.strip()
    except:
        pass
    try:
        elems = driver.find_elements(By.XPATH,
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
    for sel in ["div[title='Nächster Monat']", "div[title='Next month']", "div.button-orange-gradient"]:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            driver.execute_script("arguments[0].click();", elems[-1])
            time.sleep(3)
            if monatsnamen_lesen(driver) != monat_vorher:
                return True
    return False


def monat_scannen(driver, monat_name):
    """
    Liest fuer jeden Tag die Anzahl freier Schichten aus.
    Gibt ein Dict zurueck: { "30. April 2026": 5, ... }
    Kein Popup, kein Klick – nur lesen.
    """
    time.sleep(3)
    ergebnis = {}

    tage = driver.find_elements(By.CSS_SELECTOR, "div.cursor-pointer.fw-bold")
    tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]

    if not tage:
        tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
        tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]

    print(f"{monat_name}: {len(tage)} Tage mit freien Schichten")

    for tag in tage:
        # Zahl aus Text extrahieren z.B. "08 freie Schichten" -> 8
        anzahl = 0
        try:
            text = tag.text.strip()
            zahl = ''.join(filter(str.isdigit, text.split("\n")[0]))
            if zahl:
                anzahl = int(zahl)
        except:
            pass

        # Datum aus uebergeordneter Zelle
        datum = monat_name
        try:
            zelle = tag.find_element(By.XPATH, "./ancestor::td")
            zeilen = zelle.text.strip().split("\n")
            tageszahl = zeilen[0].strip()
            if tageszahl.isdigit():
                datum = f"{tageszahl}. {monat_name}"
        except:
            pass

        ergebnis[datum] = anzahl
        print(f"  {datum}: {anzahl} freie Schichten")

    return ergebnis


def schichten_abrufen():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=de-DE")
    options.add_experimental_option("prefs", {"intl.accept_languages": "de,de-DE"})

    driver = webdriver.Chrome(options=options)
    aktuell = {}

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

        pw_feld = driver.find_element(By.CSS_SELECTOR,
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
        aktuell.update(monat_scannen(driver, monat_1))

        # Monat 2
        if naechsten_monat_klicken(driver, monat_1):
            monat_2 = monatsnamen_lesen(driver)
            print(f"\n=== MONAT 2: {monat_2} ===")
            aktuell.update(monat_scannen(driver, monat_2))
        else:
            print("Weiter-Button nicht gefunden.")

    except Exception as e:
        print(f"Hauptfehler: {e}")
        telegram_senden(f"Bot Fehler: {e}")
    finally:
        driver.quit()

    return aktuell


# Start
print("Pruefe auf Aenderungen bei freien Schichten...")
aktuell = schichten_abrufen()
bekannt = laden()

nachrichten = []
for datum, anzahl in aktuell.items():
    alte_anzahl = bekannt.get(datum, 0)
    if anzahl > alte_anzahl:
        nachrichten.append(f"📅 {datum}: {alte_anzahl} → {anzahl} freie Schichten")
        print(f"NEU: {datum}: {alte_anzahl} -> {anzahl}")

if nachrichten:
    text = "🍓 Mehr freie Schichten bei Karls!\n\n" + "\n".join(nachrichten)
    telegram_senden(text)
    print(f"{len(nachrichten)} Aenderung(en) – Telegram gesendet!")
else:
    print("Keine Aenderungen.")

speichern(aktuell)
