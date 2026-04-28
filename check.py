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
            return json.load(f)
    except:
        return []

def speichern(daten):
    with open(BEKANNTE_FILE, "w") as f:
        json.dump(list(daten), f)

def monat_lesen(driver):
    try:
        feld = driver.find_element(By.CSS_SELECTOR, "input.k-input-inner")
        wert = feld.get_attribute("value") or feld.get_attribute("title")
        if wert and len(wert) > 2:
            return wert.strip()
    except:
        pass
    try:
        feld = driver.find_element(By.CSS_SELECTOR, "kendo-datepicker input")
        wert = feld.get_attribute("title")
        if wert and len(wert) > 2:
            return wert.strip()
    except:
        pass
    return "Unbekannt"

def tag_anklicken_und_pruefen(driver, tag_element):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tag_element)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", tag_element)
        time.sleep(2)

        wait = WebDriverWait(driver, 5)
        popup = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, ".modal-content, mat-dialog-container, [role='dialog'], .k-dialog"
        )))

        popup_text = popup.text.upper()
        hat_frueh = "FRÜH" in popup_text or "FRUH" in popup_text

        try:
            schliessen = driver.find_element(By.XPATH,
                "//button[contains(text(),'SCHLIESSEN') or contains(text(),'CLOSE')]")
            driver.execute_script("arguments[0].click();", schliessen)
        except:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(1)

        return hat_frueh

    except Exception as e:
        print(f"    Klick-Fehler: {e}")
        return False

def freie_schichten_lesen(driver, monat_name):
    frueh_tage = []

    tage = driver.find_elements(By.CSS_SELECTOR, "div.row.cursor-pointer.fw-bold")
    print(f"Gefundene Tage: {len(tage)}")

    for i in range(len(tage)):
        tage = driver.find_elements(By.CSS_SELECTOR, "div.row.cursor-pointer.fw-bold")
        if i >= len(tage):
            break

        tag = tage[i]

        datum = "?"
        try:
            container = tag.find_element(By.XPATH,
                "./ancestor::div[contains(@class,'day-content')]/..")
            headline = container.find_element(By.CSS_SELECTOR, "div.day-headline")
            alle_divs = headline.find_elements(By.XPATH, "./div")
            for div in alle_divs:
                t = div.text.strip()
                if t and t.replace(".", "").isdigit():
                    datum = f"{t.replace('.','').strip()}. {monat_name}"
                    break
        except:
            pass

        print(f"  Prüfe {datum}: {tag.text.strip()}")

        hat_frueh = tag_anklicken_und_pruefen(driver, tag)
        if hat_frueh:
            frueh_tage.append(datum)
            print(f"    -> FRÜH gefunden!")
        else:
            print(f"    -> Keine FRÜH-Schicht")

    return frueh_tage

def kalender_abrufen():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=de-DE")

    driver = webdriver.Chrome(options=options)
    alle_frueh_tage = set()

    try:
        driver.get("https://pep.karls.de/login")
        time.sleep(5)
        wait = WebDriverWait(driver, 20)
        id_feld = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "[formcontrolname='employeeId'] input"
        )))
        id_feld.send_keys(USERNAME)
        pw_feld = driver.find_element(By.CSS_SELECTOR, "[formcontrolname='password'] input")
        pw_feld.send_keys(PASSWORD)
        time.sleep(1)
        submit = driver.find_elements(By.XPATH, "//button[@type='submit']")
        if submit:
            driver.execute_script("arguments[0].click();", submit[0])
        time.sleep(5)

        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        monat_1 = monat_lesen(driver)
        print(f"\n=== {monat_1} ===")
        frueh_1 = freie_schichten_lesen(driver, monat_1)
        alle_frueh_tage.update(frueh_1)

        next_btn = driver.find_elements(By.CSS_SELECTOR,
            "div[title='Nächster Monat'], div[title='Next month']")
        if next_btn:
            driver.execute_script("arguments[0].click();", next_btn[-1])
            time.sleep(3)
            monat_2 = monat_lesen(driver)
            print(f"\n=== {monat_2} ===")
            frueh_2 = freie_schichten_lesen(driver, monat_2)
            alle_frueh_tage.update(frueh_2)

    except Exception as e:
        print(f"Fehler: {e}")
        telegram_senden(f"⚠️ Bot Fehler: {e}")
    finally:
        driver.quit()

    return alle_frueh_tage

# Start
print("Prüfe auf FRÜH-Schichten...")
aktuell = set(kalender_abrufen())
bekannt = set(laden())

neu = aktuell - bekannt

if neu:
    nachricht = "🍓 Neue FRÜH-Schichten bei Karls!\n\n"
    for tag in sorted(neu):
        nachricht += f"• {tag}\n"
    telegram_senden(nachricht)
    print(f"Telegram gesendet: {neu}")
else:
    print("Keine neuen FRÜH-Schichten.")

speichern(aktuell)
