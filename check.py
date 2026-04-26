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

def monat_scannen(driver, frueh_schichten, monat_name):
    time.sleep(3)
    
    # Alle "freie Schichten" Texte finden
    freie_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'freie Schichten') or contains(text(), 'freie Schicht') or contains(text(), 'free shifts') or contains(text(), 'free shift')]")
    print(f"{monat_name}: {len(freie_buttons)} Tage mit freien Schichten")

    for i in range(len(freie_buttons)):
        try:
            # Buttons neu laden nach jedem Popup
            freie_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'freie Schichten') or contains(text(), 'freie Schicht') or contains(text(), 'free shifts') or contains(text(), 'free shift')]")
            if i >= len(freie_buttons):
                break
                
            btn = freie_buttons[i]
            
            # Datum aus der Kalenderzelle holen
            datum = ""
            try:
                zelle = btn.find_element(By.XPATH, "./ancestor::td")
                zellen_text = zelle.text.strip().split("\n")
                # Erste Zeile ist meist die Zahl (z.B. "30.")
                datum = zellen_text[0].strip()
                datum = f"{datum} {monat_name}"
            except:
                datum = monat_name

            driver.execute_script("arguments[0].scrollIntoView();", btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(3)

            # Warten bis Popup offen
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Schicht direkt besetzen')]"))
                )
            except:
                pass

            # Nur FRÜH Schichten im Popup – ohne "Vorläufige Planung"
            alle_elemente = driver.find_elements(By.XPATH, "//*[contains(text(), 'FRÜH')]")
            for e in alle_elemente:
                try:
                    zeile = e.text.strip()
                    eltern = e.find_element(By.XPATH, "..").text
                    # Vorläufige Planung überspringen
                    if "Vorläufige" in eltern or "Preliminary" in eltern:
                        continue
                    if "FRÜH" in zeile and len(zeile) > 5:
                        eintrag = f"{datum} – {zeile}"
                        frueh_schichten.add(eintrag)
                        print(f"✅ {eintrag}")
                except:
                    continue

            # Popup schließen
            close = driver.find_elements(By.XPATH, "//button[contains(text(), 'SCHLIESSEN')]")
            if close:
                driver.execute_script("arguments[0].click();", close[0])
            else:
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            time.sleep(2)

        except Exception as e:
            print(f"Fehler Tag {i+1}: {e}")
            try:
                close = driver.find_elements(By.XPATH, "//button[contains(text(), 'SCHLIESSEN')]")
                if close:
                    driver.execute_script("arguments[0].click();", close[0])
                else:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except:
                pass
            time.sleep(2)
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
        id_feld = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "[formcontrolname='employeeId'] input, input[formcontrolname='employeeId']")
        ))
        id_feld.send_keys(USERNAME)
        pw_feld = driver.find_element(By.CSS_SELECTOR, "[formcontrolname='password'] input, input[formcontrolname='password']")
        pw_feld.send_keys(PASSWORD)
        time.sleep(2)
        buttons = driver.find_elements(By.XPATH, "//button[@type='submit']")
        if buttons:
            driver.execute_script("arguments[0].click();", buttons[0])
        time.sleep(5)

        # Kalender laden
        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        # Aktuellen Monat auslesen
        monat_elem = driver.find_elements(By.XPATH, "//*[contains(@class,'month') or contains(@class,'titel') or //input[@type='text']]")
        aktueller_monat = "Aktueller Monat"
        try:
            monat_input = driver.find_element(By.XPATH, "//input[@type='text']")
            aktueller_monat = monat_input.get_attribute("value") or "Aktueller Monat"
        except:
            pass

        # Aktuellen Monat scannen
        monat_scannen(driver, frueh_schichten, aktueller_monat)

        # Nächsten Monat
        next_btn = driver.find_elements(By.XPATH, "//button[contains(@class,'next') or contains(@class,'arrow-right') or contains(@class,'forward')]")
        if not next_btn:
            # Gelber Pfeil Button
            next_btn = driver.find_elements(By.CSS_SELECTOR, "button.btn-warning, button[class*='next'], button[class*='forward']")
        
        if next_btn:
            driver.execute_script("arguments[0].click();", next_btn[-1])
            time.sleep(3)
            
            naechster_monat = "Nächster Monat"
            try:
                monat_input = driver.find_element(By.XPATH, "//input[@type='text']")
                naechster_monat = monat_input.get_attribute("value") or "Nächster Monat"
            except:
                pass
            
            monat_scannen(driver, frueh_schichten, naechster_monat)
        else:
            print("Kein Weiter-Button gefunden")

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
    for s in sorted(neu):
        nachricht += f"• {s}\n"
    telegram_senden(nachricht)
    print(f"✅ {len(neu)} neue Schicht(en) – Telegram gesendet!")
else:
    print("Keine neuen Frühschichten.")

speichern(aktuell)
