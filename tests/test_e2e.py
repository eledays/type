from __future__ import annotations

from pathlib import Path
import shutil
from threading import Thread

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server

from app import create_app
from app.extensions import db
from app.models import Action, Category, SpellingExercise


pytestmark = pytest.mark.browser


def test_feed_answer_flow_in_mobile_browser(tmp_path: Path) -> None:
    """Exercise the real feed bundle, HTTP API, and mobile layout together."""
    browser_binary = shutil.which("google-chrome") or shutil.which("chromium")
    if browser_binary is None:
        pytest.skip("Chrome or Chromium is not installed")

    database_path = tmp_path / "browser.sqlite3"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        "SERVER_NAME": None,
        "TRUSTED_HOSTS": ["127.0.0.1", "localhost"],
        "RATELIMIT_STORAGE_URI": "memory://",
        "LEGAL_CONSENT_REQUIRED": False,
    })
    with app.app_context():
        db.create_all()
        category = Category(name="E2E")
        db.session.add(SpellingExercise(
            word="м_локо",
            answers=["о", "а"],
            correct_answer="о",
            task_number=4,
            category=category,
        ))
        db.session.commit()

    server = make_server("127.0.0.1", 0, app, threaded=True)
    server_thread = Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    options = webdriver.ChromeOptions()
    options.binary_location = browser_binary
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    try:
        driver.set_window_size(390, 844)
        driver.get(f"http://127.0.0.1:{server.server_port}/")
        wait = WebDriverWait(driver, 10)
        answer = wait.until(lambda current: current.find_element(
            By.CSS_SELECTOR, '[data-answer="о"]'
        ))
        assert driver.execute_script(
            "return document.documentElement.scrollWidth <= window.innerWidth"
        )
        answer.click()
        wait.until(lambda current: "is-correct" in current.find_element(
            By.ID, "answer-flash"
        ).get_attribute("class"))
        with app.app_context():
            assert Action.query.count() == 1
            assert Action.query.one().action == Action.RIGHT_ANSWER
    finally:
        driver.quit()
        server.shutdown()
        server_thread.join(timeout=5)
        with app.app_context():
            db.session.remove()
            db.drop_all()
