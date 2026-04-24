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
    requests.post(url, json={"chat_id": CHAT_ID, "text": text})

def laden():
    try:
        with open(BEKANNTE_FILE) as f:
            return set(json.load(f))
    except:
        return set()

def speichern(schichten):
    with open(BEKANNTE_FILE, "w") as f:
        json.dump(list(schichten), f)

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

        # Karlsianer-ID eingeben
        id_feld = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[formcontrolname='employeeId'] input, input[formcontrolname='employeeId']")
        ))
        id_feld.send_keys(USERNAME)
        print("Karlsianer-ID eingegeben")

        # Passwort eingeben
        pw_feld = driver.find_element(
            By.CSS_SELECTOR, "[formcontrolname='password'] input, input[formcontrolname='password']"
        )
        pw_feld.send_keys(PASSWORD)
        print("Passwort eingegeben")

        # Login Button klicken
        for selector in [
            "//button[@type='submit']",
            "//button[contains(text(),'Login')]",
            "//button[contains(text(),'Anmelden')]",
            "//button[contains(text(),'Einloggen')]"
        ]:
            buttons = driver.find_elements(By.XPATH, selector)
            if buttons:
                buttons[0].click()
                print(f"Login Button geklickt")
                break

        time.sleep(5)
        print("Nach Login URL:", driver.current_url)

        # Kalender laden
        driver.get("https://pep.karls.de/dashboard/personal")
        time.sleep(5)

        # Alle klickbaren Tage finden
        tage = driver.find_elements(By.CSS_SELECTOR, "[class*='day'], [class*='cell'], td")
        print(f"Gefundene Tage: {len(tage)}")

        for tag in tage[:60]:
            try:
                tag.click()
                time.sleep(2)

                eintraege = driver.find_elements(By.XPATH, "//*[contains(text(), 'FRÜH')]")
                for e in eintraege:
                    text = e.text.strip()
                    if "FRÜH" in text and len(text) > 3:
                        frueh_schichten.add(text)
                        print(f"Gefunden: {text}")

                close = driver.find_elements(By.XPATH, "//button[contains(text(), 'SCHLIESSEN')] | //button[contains(text(), 'Schließen')]")
                if close:
                    close[0].click()
                    time.sleep(0.5)
            except:
                continue

    except Exception as e:
        print(f"Fehler: {e}")
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
