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
    close = driver.find_elements(By.XPATH, "//button[contains(text(), 'SCHLIESSEN') or contains(text(), 'Schließen') or contains(text(), 'CLOSE') or contains(text(), 'Close')]")
    if close:
        driver.execute_script("arguments[0].click();", close[0])
    else:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    time.sleep(1)

def monat_scannen(driver, frueh_schichten):
    freie_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'free shifts') or contains(text(), 'free shift') or contains(text(), 'freie Schichten') or contains(text(), 'freie Schicht')]")
    print(f"Tage mit freien Schichten: {len(freie_buttons)}")

    for i, btn in enumerate(freie_buttons):
        try:
            # Datum aus der Zelle holen
            datum = ""
            try:
                zelle = btn.find_element(By.XPATH, "./ancestor::td")
                # Zahl im Tag (z.B. "30.")
                datum_elem = zelle.find_elements(By.XPATH, ".//*[contains(@class,'day-number') or contains(@class,'date') or contains(@class,'day')]")
                if datum_elem:
                    datum = datum_elem[0].text.strip()
                else:
                    datum = zelle.text.split("\n")[0].strip()
            except:
                pass

            print(f"Klicke Tag {i+1}, Datum: {datum}")
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(3)

            # Nur Schichten im Popup lesen – nicht "Preliminary planning"
            popup = driver.find_elements(By.XPATH, "//*[contains(@class,'modal') or contains(@class,'popup') or contains(@class,'dialog') or contains(@class,'overlay')]")
            
            if popup:
                popup_text = popup[0].find_elements(By.XPATH, ".//*[contains(text(), 'FRÜH')]")
                for e in popup_text:
                    zeile = e.text.strip()
                    if "FRÜH" in zeile and "Preliminary" not in zeile and len(zeile) > 3:
                        eintrag = f"{datum} – {zeile}"
                        frueh_schichten.add(eintrag)
                        print(f"✅ Gefunden: {eintrag}")
            else:
                # Fallback: alle FRÜH ohne Preliminary
                eintraege = driver.find_elements(By.XPATH, "//*[contains(text(), 'FRÜH')]")
                for e in eintraege:
                    zeile = e.text.strip()
                    eltern_text = e.find_element(By.XPATH, "..").text
                    if "FRÜH" in zeile and "Preliminary" not in eltern_text and len(zeile) > 3:
                        eintrag = f"{datum} – {zeile}"
                        frueh_schichten.add(eintrag)
                        print(f"✅ Gefunden: {eintrag}")

            popup_schliessen(driver)

        except Exception as e:
            print(f"Fehler bei Tag {i+1}: {e}")
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
    wait = WebDriverWait(driver, 20)
    frueh_schichten = set()

    try:
        driver.get("https://pep.karls.de/login")
        time.sleep(5)

        id_feld = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[formcontrolname='employeeId'] input, input[formcontrolname='employeeId']")
        ))
        id_feld.send_keys(USERNAME)

        pw_feld = driver.find_element(
            By.CSS_SELECTOR, "[formcontrolname='password'] input, input[formcontrolname='password']"
        )
        pw_feld.send_keys(PASSWORD)

        time.sleep(2)
        buttons = driver.find_elements(By.XPATH, "//button[@type='submit']")
        if buttons:
            driver.execute_script("arguments[0].click();", buttons[0])
        time.sleep(5)

        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        # Aktuellen Monat scannen
        print("=== Aktueller Monat ===")
        monat_scannen(driver, frueh_schichten)

        # Nächsten Monat
        next_buttons = driver.find_elements(By.XPATH, "//button[contains(@class,'next') or contains(@aria-label,'next') or contains(@aria-label,'vor') or contains(text(),'→') or contains(text(),'>')]")
        if next_buttons:
            driver.execute_script("arguments[0].click();", next_buttons[0])
            time.sleep(3)
            print("=== Nächster Monat ===")
            monat_scannen(driver, frueh_schichten)

    except Exception as e:
        print(f"Hauptfehler: {e}")
        telegram_senden(f"⚠️ Bot Fehler: {e}")
    finally:
        driver.quit()

    return frueh_schichten

print("Prüfe auf neue Frühschichten...")
aktuell = schichten_abrufen()
bekannt = laden()
neu = aktuell - bekannt

if neu:
    nachricht = "🍓 NEUE FRÜHSCHICHT bei Karls!\n\n"
    for s in neu:
        nachricht += f"• {s}\n"
    telegram_senden(nachricht)
    print(f"✅ {len(neu)} neue Schicht(en) – Telegram gesendet!")
else:
    print("Keine neuen Frühschichten.")

speichern(aktuell)
