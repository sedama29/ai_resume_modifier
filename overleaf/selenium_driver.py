"""Persistent-profile Chrome driver for (future) Overleaf browser automation.
Non-headless by design: the point of the persistent profile is that you log in
once by hand (including any 2FA) and every later run reuses that session --
you should be able to see the browser do its thing."""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def get_driver(profile_dir: str, headless: bool = False) -> webdriver.Chrome:
    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    if headless:
        options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)
