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
from selenium.webdriver.common.action_chains import ActionChains

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
    """Schliesst das Bestaetigen-Banner falls vorhanden."""
    try:
        btn = driver.find_element(By.XPATH,
            "//button[contains(text(),'BESTÄTIGEN') or contains(text(),'CONFIRM') or contains(text(),'Bestätigen')]"
        )
        if btn.is_displayed():
            driver.execute_script("arguments[0].click();", btn)
            print("  Banner geschlossen")
            time.sleep(2)
    except:
        pass


def popup_ist_offen(driver):
    try:
        dialoge = driver.find_elements(By.CSS_SELECTOR, "mat-dialog-container")
        if any(d.is_displayed() for d in dialoge):
            return True
        titel = driver.find_elements(By.XPATH,
            "//*[contains(text(),'Schicht direkt besetzen') or contains(text(),'Assign shift')]"
        )
        return bool(titel)
    except:
        return False


def popup_warten(driver, sekunden=10):
    ende = time.time() + sekunden
    while time.time() < ende:
        if popup_ist_offen(driver):
            time.sleep(0.5)
            return True
        time.sleep(0.5)
    return False


def popup_schliessen(driver):
    for sel in ["button.outlined-button", "button[class*='outlined-button']"]:
        btns = driver.find_elements(By.CSS_SELECTOR, sel)
        for btn in btns:
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    if not popup_ist_offen(driver):
                        return
            except:
                pass

    for text in ["SCHLIESSEN", "CLOSE", "Schließen", "Close"]:
        btns = driver.find_elements(By.XPATH, f"//button[contains(.,'{text}')]")
        for btn in btns:
            try:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    if not popup_ist_offen(driver):
                        return
            except:
                pass

    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except:
        pass
    time.sleep(2)


def angular_klick(driver, element):
    """
    Sendet ein echtes MouseEvent mit bubbles=true.
    Das ist was Angular braucht – normales .click() reicht nicht.
    """
    driver.execute_script("""
        var el = arguments[0];
        el.dispatchEvent(new MouseEvent('mouseover', {bubbles: true, cancelable: true}));
        el.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
        el.dispatchEvent(new MouseEvent('mouseup',   {bubbles: true, cancelable: true}));
        el.dispatchEvent(new MouseEvent('click',     {bubbles: true, cancelable: true}));
    """, element)


def klicke_element(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(1)

    # Methode 1: Angular-nativer MouseEvent (bubbles: true)
    try:
        angular_klick(driver, element)
        time.sleep(3)
        if popup_ist_offen(driver):
            print("    -> Klick via Angular MouseEvent")
            return True
    except Exception as e:
        print(f"    Angular-Klick Fehler: {e}")

    # Methode 2: ActionChains
    try:
        actions = ActionChains(driver)
        actions.move_to_element(element).pause(0.3).click().perform()
        time.sleep(3)
        if popup_ist_offen(driver):
            print("    -> Klick via ActionChains")
            return True
    except Exception as e:
        print(f"    ActionChains Fehler: {e}")

    # Methode 3: Per Koordinaten klicken
    try:
        rect = driver.execute_script("""
            var r = arguments[0].getBoundingClientRect();
            return {x: r.left + r.width/2, y: r.top + r.height/2};
        """, element)
        actions = ActionChains(driver)
        actions.move_by_offset(rect['x'], rect['y']).click().perform()
        time.sleep(3)
        if popup_ist_offen(driver):
            print("    -> Klick via Koordinaten")
            return True
    except Exception as e:
        print(f"    Koordinaten-Klick Fehler: {e}")

    # Methode 4: Angular-Klick auf inneres div
    try:
        inner = element.find_element(By.CSS_SELECTOR, "div.col.text-center")
        angular_klick(driver, inner)
        time.sleep(3)
        if popup_ist_offen(driver):
            print("    -> Klick via inner div Angular")
            return True
    except:
        pass

    return False


def monatsnamen_lesen(driver):
    try:
        feld = driver.find_element(By.XPATH, "//input[@type='text']")
        wert = feld.get_attribute("value")
        if wert and len(wert) > 2:
            return wert.strip()
    except:
        pass

    for sel in ["kendo-datepicker input", ".k-datepicker input"]:
        try:
            elem = driver.find_element(By.CSS_SELECTOR, sel)
            wert = elem.get_attribute("value") or elem.text
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
            ziel = elems[-1]
            print(f"  Weiter-Button: {sel}")
            driver.execute_script("arguments[0].click();", ziel)
            time.sleep(3)
            if monatsnamen_lesen(driver) != monat_vorher:
                return True
    print("  Kein Weiter-Button gefunden!")
    return False


def freie_tage_finden(driver):
    tage = driver.find_elements(By.CSS_SELECTOR, "div.cursor-pointer.fw-bold")
    tage = [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]
    if tage:
        return tage
    tage = driver.find_elements(By.CSS_SELECTOR, "div.col.text-center")
    return [t for t in tage if "freie Schicht" in t.text or "free shift" in t.text.lower()]


def monat_scannen(driver, frueh_schichten, monat_name):
    time.sleep(3)
    banner_schliessen(driver)
    time.sleep(1)

    tage = freie_tage_finden(driver)
    print(f"\n{monat_name}: {len(tage)} Tage mit freien Schichten")

    for i in range(len(tage)):
        tage = freie_tage_finden(driver)
        if i >= len(tage):
            break

        tag = tage[i]

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

        driver.save_screenshot("debug.png")

        try:
            geoeffnet = klicke_element(driver, tag)

            if not geoeffnet:
                geoeffnet = popup_warten(driver, sekunden=5)

            if not geoeffnet:
                print(f"    -> Kein Popup")
                continue

            dialog = driver.find_element(By.CSS_SELECTOR, "mat-dialog-container")
            alle_zeilen = dialog.text.split("\n")

            frueh_gefunden = False
            for idx, zeile in enumerate(alle_zeilen):
                zeile = zeile.strip()
                if not zeile or "FRÜH" not in zeile.upper():
                    continue
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

        driver.get("https://pep.karls.de/profile/116359/kalender")
        time.sleep(5)

        monat_1 = monatsnamen_lesen(driver)
        print(f"\n=== MONAT 1: {monat_1} ===")
        monat_scannen(driver, frueh_schichten, monat_1)

        print(f"\n-> Naechster Monat...")
        if naechsten_monat_klicken(driver, monat_1):
            monat_2 = monatsnamen_lesen(driver)
            print(f"\n=== MONAT 2: {monat_2} ===")
            monat_scannen(driver, frueh_schichten, monat_2)
        else:
            telegram_senden("Weiter-Button nicht gefunden.")

    except Exception as e:
        print(f"Hauptfehler: {e}")
        telegram_senden(f"Bot Fehler: {e}")
    finally:
        driver.quit()

    return frueh_schichten


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
