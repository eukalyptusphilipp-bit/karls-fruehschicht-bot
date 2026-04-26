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

def telegram_senden(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text[:4000]})

options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 20)

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
    driver.get("https://pep.karls.de/dashboard/personal")
    time.sleep(5)

    # Ganzen Seitentext schicken
    seite = driver.find_element(By.TAG_NAME, "body").text
    telegram_senden(f"📄 Seite:\n{seite[:3000]}")

except Exception as e:
    telegram_senden(f"❌ Fehler: {e}")
finally:
    driver.quit()
