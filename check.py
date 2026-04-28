import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.by import By
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

def monat_lesen(driver):
    try:
        feld = driver.find_element(By.XPATH, "//input[@type='text']")
        wert = feld.get_attribute("value")
        if wert and len(wert) > 2:
            return wert.strip()
    except:
        pass
    return "Unbekannt"

def freie_schichten_lesen(driver):
    """Liest alle Tage mit freien Schichten und deren Anzahl."""
    ergebnis = {}
    
    tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
    for tag in tage:
        text = tag.text.strip()
        if "freie Schicht" in text or "free shift" in text.lower():
            try:
                # Zahl aus Text holen (z.B. "20 freie Schichten" -> 20)
                zahl = int(text.split()[0])
                
                # Datum aus Zelle holen
                datum = "?"
                try:
                    zelle = tag.find_element(By.XPATH, "./ancestor::td")
                    zeilen = zelle.text.strip().split("\n")
                    tageszahl = zeilen[0].strip().replace(".", "")
                    if tageszahl.isdigit():
                        datum = tageszahl
                except:
                    pass
                
                ergebnis[datum] = zahl
            except:
                continue
    
    return ergebnis

def kalender_abrufen():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=de-DE")

    driver = webdriver.Chrome(options=options)
    alle_schichten = {}

    try:
        # Login
        driver.get("https://pep.karls.de/login")
        time.sleep(5)

        wait = WebDriverWait(driver, 20)
        id_feld = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "[formcontrolname='employeeId'] input, input[formcontrolname='employeeId']"
        )))
        id_feld.send_keys(USERNAME)

        pw_feld = driver.find_element(
            By.CSS_SELECTOR,
            "[formcontrolname='password'] input, input[formcontrolname='password']"
        )
        pw_feld.send_keys(PASSWORD)
        time.sleep(1)

        submit = driver.find_elements(By.XPATH, "//button[@type='submit']")
        if submit:
            driver.execute_script("arguments[0].click();", submit[0])
        time.sleep(5)

        # Kalender laden
        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        # Monat 1
        monat_1 = monat_lesen(driver)
        daten_1 = freie_schichten_lesen(driver)
        print(f"{monat_1}: {daten_1}")
        for tag, anzahl in daten_1.items():
            alle_schichten[f"{tag}. {monat_1}"] = anzahl

        # Nächsten Monat
        next_btn = driver.find_elements(By.CSS_SELECTOR, "div[title='Nächster Monat'], div[title='Next month'], div.button-orange-gradient")
        if next_btn:
            driver.execute_script("arguments[0].click();", next_btn[-1])
            time.sleep(3)
            monat_2 = monat_lesen(driver)
            daten_2 = freie_schichten_lesen(driver)
            print(f"{monat_2}: {daten_2}")
            for tag, anzahl in daten_2.items():
                alle_schichten[f"{tag}. {monat_2}"] = anzahl

    except Exception as e:
        print(f"Fehler: {e}")
        telegram_senden(f"⚠️ Bot Fehler: {e}")
    finally:
        driver.quit()

    return alle_schichten

# Start
print("Prüfe freie Schichten...")
aktuell = kalender_abrufen()
bekannt = laden()

nachricht = ""
for datum, anzahl in aktuell.items():
    alte_anzahl = bekannt.get(datum, 0)
    if anzahl > alte_anzahl:
        mehr = anzahl - alte_anzahl
        nachricht += f"• {datum}: +{mehr} freie Schichten ({anzahl} gesamt)\n"
        print(f"NEU: {datum}: {alte_anzahl} -> {anzahl}")

if nachricht:
    telegram_senden(f"🍓 Neue freie Schichten bei Karls!\n\n{nachricht}")
    print("Telegram gesendet!")
else:
    print("Keine Änderungen.")

speichern(aktuell)
