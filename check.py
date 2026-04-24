import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Zugangsdaten aus GitHub Secrets ---
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

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    frueh_schichten = set()

    try:
        # Einloggen
        driver.get("https://pep.karls.de/")
        wait.until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(USERNAME)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        # Kalender laden
        wait.until(EC.url_contains("dashboard"))
        driver.get("https://pep.karls.de/dashboard/personal")
        time.sleep(3)

        # Alle Tage im Kalender finden und anklicken
        tage = driver.find_elements(By.CSS_SELECTOR, ".calendar-day, [class*='day']")

        for tag in tage:
            try:
                tag.click()
                time.sleep(1.5)

                # Schichten im Popup lesen
                eintraege = driver.find_elements(By.XPATH, "//*[contains(text(), 'FRÜH')]")
                for e in eintraege:
                    text = e.text.strip()
                    if "FRÜH" in text and text:
                        frueh_schichten.add(text)

                # Popup schließen
                close = driver.find_elements(By.XPATH, "//button[contains(text(), 'SCHLIESSEN')]")
                if close:
                    close[0].click()
                    time.sleep(0.5)
            except:
                continue

    finally:
        driver.quit()

    return frueh_schichten

# --- Hauptlogik ---
print("Prüfe auf neue Frühschichten...")
aktuell = schichten_abrufen()
bekannt = laden()

neu = aktuell - bekannt

if neu:
    nachricht = "🍓 NEUE FRÜHSCHICHT bei Karls!\n\n"
    for s in neu:
        nachricht += f"• {s}\n"
    telegram_senden(nachricht)
    print(f"✅ {len(neu)} neue Schicht(en) gefunden – Telegram gesendet!")
    speichern(aktuell)
else:
    print("Keine neuen Frühschichten.")
    speichern(aktuell)
