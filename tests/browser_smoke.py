"""Run both placement variants against a real desktop browser.

Chromium-based browsers need Playwright; Firefox needs Selenium and geckodriver.
"""
import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time


@contextmanager
def chromium(binary):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=binary)
        page = browser.new_page(viewport={"width": 1100, "height": 680})
        errors = []
        page.on("pageerror", lambda error: errors.append(error))
        try:
            yield (
                page.goto, lambda script: page.evaluate(f"() => {{ {script} }}"),
                lambda selector: page.locator(selector).first.click(),
                lambda: page.set_viewport_size({"width": 760, "height": 530}),
            )
            assert not errors, errors
        finally:
            browser.close()


@contextmanager
def firefox(binary, driver_path):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.actions.action_builder import ActionBuilder
    from selenium.webdriver.firefox.service import Service

    options = webdriver.FirefoxOptions()
    options.binary_location = binary
    options.add_argument("-headless")
    with webdriver.Firefox(options=options, service=Service(executable_path=driver_path)) as browser:
        browser.set_window_size(1100, 680)

        def click(selector):
            element = browser.find_element(By.CSS_SELECTOR, selector)
            if element.tag_name == "g":
                x, y = browser.execute_script("""
                    const box = arguments[0].getBoundingClientRect();
                    return [Math.round(box.x + box.width / 2), Math.round(box.y + box.height / 2)];
                """, element)
                pointer = ActionBuilder(browser)
                pointer.pointer_action.move_to_location(x, y)
                pointer.pointer_action.click()
                pointer.perform()
            else:
                element.click()

        yield (
            browser.get, browser.execute_script,
            click,
            lambda: browser.set_window_size(760, 530),
        )


ALIGNMENT = """
const marker = document.querySelector('.bw-slide:not([hidden]) [data-web-widget]');
const host = document.querySelector('.bw-slide:not([hidden]) .bw-widget');
if (!marker || !host) return false;
const expected = marker.getBoundingClientRect(), actual = host.getBoundingClientRect();
return ['x', 'y', 'width', 'height'].every(key => Math.abs(expected[key] - actual[key]) < 1.5)
  && actual.width > 0 && actual.height > 0;
"""


def wait_for(evaluate, script, seconds=4):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if evaluate(script):
            return
        time.sleep(.05)
    raise AssertionError(script)


def check(operations, url):
    open_url, evaluate, click, resize = operations
    open_url(url)
    wait_for(evaluate, "return document.querySelector('#bw-counter').value === '1 / 5';")
    click("#bw-next")
    wait_for(evaluate, ALIGNMENT)
    evaluate("""
      window.key = (target, key) => target.dispatchEvent(new KeyboardEvent('keydown', {
        key, bubbles: true, cancelable: true
      }));
      const input = document.querySelector('input');
      input.focus();
      input.value = '.75';
      input.dispatchEvent(new Event('input', {bubbles: true}));
      window.key(input, 'ArrowRight');
    """)
    assert evaluate("return document.querySelector('#bw-counter').value === '2 / 5';")
    assert evaluate("return +document.querySelector('[data-web-id=formula]').style.opacity > .75;")
    evaluate("""
      const text = document.createElement('input');
      document.querySelector('.bw-widget').append(text);
      text.focus();
      text.value = 'slide notes';
      key(text, ' ');
    """)
    assert evaluate("return document.activeElement.value === 'slide notes' && location.hash === '#/2';")
    resize()
    wait_for(evaluate, ALIGNMENT)
    click("#bw-fullscreen")
    wait_for(evaluate, "return Boolean(document.fullscreenElement);")
    wait_for(evaluate, ALIGNMENT)
    click("#bw-fullscreen")
    wait_for(evaluate, "return !document.fullscreenElement;")
    evaluate("""
      const marker = document.querySelector('.bw-slide:nth-child(3) [data-web-widget]');
      marker.setAttribute('transform', 'rotate(8 ' + marker.getAttribute('x') + ' ' +
        marker.getAttribute('y') + ')');
      window.key(document.body, 'ArrowRight');
    """)
    wait_for(evaluate, "return location.hash === '#/3' && document.querySelector('input').value === '0.75';")
    wait_for(evaluate, ALIGNMENT)
    evaluate("window.key(document.body, 'PageUp');")
    wait_for(evaluate, "return location.hash === '#/2';")
    open_url(url + "#/4")
    wait_for(evaluate, ALIGNMENT)
    click('[data-web-id="vertex-v"]')
    assert evaluate("""
      return document.querySelector('[data-web-id=edge-sv]').classList.contains('highlight') &&
        document.querySelector('.bw-widget').textContent.includes('vertex: v');
    """)
    click("#bw-next")
    wait_for(evaluate, "return location.hash === '#/5';")
    wait_for(evaluate, ALIGNMENT)
    evaluate("""
      const canvas = document.querySelector('canvas');
      window.canvasImage = () => canvas.toDataURL();
      window.initialImage = canvasImage();
    """)
    click(".bw-widget button")
    wait_for(evaluate, "return canvasImage() !== initialImage;")
    click(".bw-widget button:nth-child(2)")
    evaluate("window.stoppedImage = canvasImage();")
    time.sleep(.15)
    assert evaluate("return canvasImage() === stoppedImage;")
    click(".bw-widget button:nth-child(3)")
    assert evaluate("return canvasImage() === initialImage;")
    click(".bw-widget button")
    click("#bw-prev")
    wait_for(evaluate, "return !document.querySelector('canvas');")
    evaluate("window.leftImage = canvasImage();")
    time.sleep(.15)
    assert evaluate("return leftImage === canvasImage();")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("browser", choices=["chromium", "firefox"])
    parser.add_argument("binary")
    parser.add_argument("--driver", default=os.environ.get("GECKODRIVER"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    build_dir = root / "_build"
    build_dir.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=build_dir) as temp:
        for placement in ("overlay", "foreign-object"):
            dist = Path(temp) / placement
            subprocess.run([sys.executable, "-m", "beamerweb", "build",
                            "examples/demo.tex", "--placement", placement, "-o", str(dist)],
                           cwd=root, check=True)
            driver = (chromium(args.binary) if args.browser == "chromium"
                      else firefox(args.binary, args.driver))
            with driver as operations:
                check(operations, (dist / "index.html").as_uri())
            print(f"{args.binary}: {placement} passed", flush=True)


if __name__ == "__main__":
    main()
