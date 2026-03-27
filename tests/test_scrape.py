import chirp_to_libib.core as c
from unittest.mock import MagicMock
from selenium.webdriver.common.by import By

def test_login_success(mock_build_driver):
    driver = mock_build_driver

    # Mock login page elements
    email_el = MagicMock()
    pwd_el = MagicMock()
    submit_el = MagicMock()

    # Define fake find_element AFTER mocks exist
    def fake_find_element(by, value):
        if by == By.ID and value == "user_email":
            return email_el
        if by == By.ID and value == "user_password":
            return pwd_el
        if by == By.CSS_SELECTOR and value == "button[type='submit']":
            return submit_el
        return MagicMock()

    driver.find_element.side_effect = fake_find_element

    # Mock library link appearing
    driver.find_elements.return_value = [MagicMock()]

    c._login(driver, "test@example.com", "pw")

    email_el.send_keys.assert_called_once()
    pwd_el.send_keys.assert_called_once()
    submit_el.click.assert_called_once()


def test_parse_items_basic():
    item = MagicMock()
    title_el = MagicMock()
    title_el.text = "My Book"

    byline_el = MagicMock()
    byline_el.text = "by Author"

    img_el = MagicMock()
    img_el.get_attribute.return_value = "cover.jpg"

    item.find_element.side_effect = [
        title_el,
        byline_el,
        img_el,
    ]

    out = c._parse_items([item])
    assert out == [("My Book", "Author", "cover.jpg")]
