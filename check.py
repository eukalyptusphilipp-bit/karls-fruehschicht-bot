```python
import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
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


def banner_schliessen(driver):
    try:
        btn = driver.find_element(By.XPATH,
            "//button[contains(text(),'BESTÄTIGEN') or contains(text(),'CONFIRM') or contains(text(),'Bestätigen')]"
        )
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
    except:
        pass


def get_dialog(driver):
    selektoren = [
        "mat-dialog-container",
        "ngb-modal-window",
        ".modal-dialog",
        ".modal-content",
        "[role='dialog']",
        "kendo-dialog",
        ".k-dialog",
        ".cdk-overlay-pane",
    ]
    for sel in selektoren:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        for e in elems:
            try:
                if e.is_displayed() and e.text.strip():
                    return e
            except:
                pass
    return None


def popup_ist_offen(driver):
    return get_dialog(driver) is not None


def popup_warten(driver, sekunden=10):
    ende = time.time() + sekunden
    while time.time() < ende:
        if popup_ist_offen(driver):
            return True
        time.sleep(0.5)
    return False


def popup_schliessen(driver):
    for text in ["SCHLIESSEN", "CLOSE", "Schließen", "Close"]:
        btns = driver.find_elements(By.XPATH, f"//button[contains(.,'{text}')]")
        for btn in btns:
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    return
            except:
                pass

    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except:
        pass
    time.sleep(2)


def freie_tage_finden(driver):
    tage = driver.find_elements(By.CSS_SELECTOR, "td")

    result = []
    for t in tage:
        try:
            text = t.text.lower()
            if any(x in text for x in ["freie", "free"]):
                result.append(t)
        except:
            pass

    return result


def stabil_klicken(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.8)

    for attempt in range(3):
        try:
            driver.execute_script("arguments[0].click();", element)
            time.sleep(2)

            if popup_ist_offen(driver):
                return True

            driver.execute_script("""
                var r = arguments[0].getBoundingClientRect();
                var x = r.left + r.width/2;
                var y = r.top + r.height/2;
                document.elementFromPoint(x, y).click();
            """, element)

            time.sleep(2)

            if popup_ist_offen(driver):
                return True

        except Exception as e:
            print(f"Klick-Versuch {attempt+1} fehlgeschlagen: {e}")

        time.sleep(1)

    return False


def monatsnamen_lesen(driver):
    try:
        feld = driver.find_element(By.XPATH, "//input[@type='text']")
        return feld.get_attribute("value")
    except:
        return "Unbekannter Monat"


def naechsten_monat_klicken(driver, monat_vorher):
    elems = driver.find_elements(By.CSS_SELECTOR, "div[title='Nächster Monat'], div[title='Next month']")
    if elems:
        driver.execute_script("arguments[0].click();", elems[-1])
        time.sleep(3)
        return True
    return False


def monat_scannen(driver, frueh_schichten, monat_name):
    time.sleep(3)
    banner_schliessen(driver)

    tage = freie_tage_finden(driver)
    print(f"\n{monat_name}: {len(tage)} Tage mit freien Schichten")

    tage_texte = [t.text for t in tage]

    for idx, text in enumerate(tage_texte):
        print(f"\n[{idx+1}/{len(tage_texte)}] Prüfe Tag...")

        tage = freie_tage_finden(driver)
        tag = next((t for t in tage if t.text == text), None)

        if not tag:
            print("Tag nicht gefunden (DOM geändert)")
            continue

        datum = monat_name
        try:
            zeilen = tag.text.strip().split("\n")
            if zeilen and zeilen[0].isdigit():
                datum = f"{zeilen[0]}. {monat_name}"
        except:
            pass

        print(f"-> {datum}")

        try:
            if not stabil_klicken(driver, tag):
                print("Klick fehlgeschlagen")
                continue

            if not popup_warten(driver, 8):
                print("Kein Popup")
                continue

            dialog = get_dialog(driver)
            if not dialog:
                continue

            lines = dialog.text.split("\n")
            for i, line in enumerate(lines):
                if "früh" in line.lower():
                    context = " ".join(lines[max(0, i-2):i+3])
                    if "vorläufig" in context.lower():
                        continue

                    eintrag = f"{datum} – {line.strip()}"
                    if eintrag not in frueh_schichten:
                        frueh_schichten.add(eintrag)
                        print("NEU:", eintrag)

            popup_schliessen(driver)

        except Exception as e:
            print("Fehler:", e)
            try:
                popup_schliessen(driver)
            except:
                pass


def schichten_abrufen():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    frueh_schichten = set()

    try:
        driver.get("https://pep.karls.de/login")
        time.sleep(5)

        driver.find_element(By.CSS_SELECTOR, "input[formcontrolname='employeeId']").send_keys(USERNAME)
        driver.find_element(By.CSS_SELECTOR, "input[formcontrolname='password']").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()

        time.sleep(5)

        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        monat_1 = monatsnamen_lesen(driver)
        monat_scannen(driver, frueh_schichten, monat_1)

        if naechsten_monat_klicken(driver, monat_1):
            monat_2 = monatsnamen_lesen(driver)
            monat_scannen(driver, frueh_schichten, monat_2)

    except Exception as e:
        telegram_senden(f"Bot Fehler: {e}")
    finally:
        driver.quit()

    return frueh_schichten


print("Pruefe auf neue Fruehschichten...")
aktuell = schichten_abrufen()
bekannt = laden()
neu = aktuell - bekannt

if neu:
    msg = "NEUE FRUEHSCHICHT:\n\n"
    for s in sorted(neu):
        msg += f"- {s}\n"
    telegram_senden(msg)
else:
    print("Keine neuen Schichten")

speichern(aktuell)
```
