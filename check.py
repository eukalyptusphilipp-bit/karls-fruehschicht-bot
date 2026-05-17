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

IGNORIERTE_TAGE = [
    "18. Mai 2026",
    "19. Mai 2026",
    "22. Mai 2026",
    "29. Mai 2026",
    "30. Mai 2026",
    "1. Juni 2026",
    "2. Juni 2026",
    "3. Juni 2026",
    "4. Juni 2026",
    "5. Juni 2026",
    "6. Juni 2026",
    "9. Juni 2026",
    "12. Juni 2026",
    "13. Juni 2026",
    "16. Juni 2026",
    "18. Juni 2026",
    "23. Juni 2026",
    "25. Juni 2026",
    "30. Juni 2026",
    "03. Juli 2026",
    "04. Juli 2026",
]

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
    try:
        picker = driver.find_element(By.CSS_SELECTOR, "kendo-datepicker")
        wert = picker.text.strip()
        if wert:
            return wert
    except:
        pass
    return "Unbekannt"

def freie_schichten_lesen(driver):
    ergebnis = {}
    
    tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
    for tag in tage:
        text = tag.text.strip()
        if "freie Schicht" in text or "free shift" in text.lower():
            try:
                zahl = int(text.split()[0])
                datum = "?"
                try:
                    day_content = tag.find_element(By.XPATH, "./ancestor::div[contains(@class,'day-content')]")
                    parent = day_content.find_element(By.XPATH, "..")
                    day_headline = parent.find_element(By.CSS_SELECTOR, "div.day-headline")
                    datum_div = day_headline.find_element(By.CSS_SELECTOR, "div.col-4.fw-bold")
                    datum = datum_div.text.strip().replace(".", "").strip()
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
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-software-rasterizer")

    driver = webdriver.Chrome(options=options)
    alle_schichten = {}

    try:
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

        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        monat_1 = monat_lesen(driver)
        daten_1 = freie_schichten_lesen(driver)
        print(f"{monat_1}: {daten_1}")
        for tag, anzahl in daten_1.items():
            alle_schichten[f"{tag}. {monat_1}"] = anzahl

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
        fehler = str(e).split("\n")[0]
        print(f"Fehler: {fehler}")
        telegram_senden(f"⚠️ Bot Fehler: {fehler}")
    finally:
        driver.quit()

    return alle_schichten

# Start
print("Prüfe freie Schichten...")
aktuell = kalender_abrufen()
bekannt = laden()

nachricht = ""
for datum, anzahl in aktuell.items():
    if any(tag in datum for tag in IGNORIERTE_TAGE):
        print(f"Ignoriert: {datum}")
        continue

    alte_anzahl = bekannt.get(datum, 0)
    
    if datum not in bekannt:
        nachricht += f"🆕 {datum}: {anzahl} freie Schichten (neu!)\n"
        print(f"NEU TAG: {datum} mit {anzahl} Schichten")
    elif anzahl > alte_anzahl:
        mehr = anzahl - alte_anzahl
        nachricht += f"📈 {datum}: +{mehr} Schichten ({alte_anzahl} → {anzahl})\n"
        print(f"MEHR: {datum}: {alte_anzahl} -> {anzahl}")

if nachricht:
    telegram_senden(f"🍓 Neue freie Schichten bei Karls!\n\n{nachricht}")
    print("Telegram gesendet!")
else:
    print("Keine Änderungen.")

speichern(aktuell)
