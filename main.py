from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os
import re
import requests

app = Flask(__name__)

PROD_AUTH_TOKEN = os.environ.get("PROD_AUTH_TOKEN", "")
GW_TOKEN = os.environ.get("GW_TOKEN", "")
HACOO_COOKIE = os.environ.get("HACOO_COOKIE", "")

def get_cookies_affiliate():
    return [
        {"name": "PROD_AUTH_TOKEN", "value": PROD_AUTH_TOKEN, "domain": "affiliate.hacoo.app", "path": "/"},
        {"name": "has_token", "value": "1", "domain": "affiliate.hacoo.app", "path": "/"},
        {"name": "gw-token", "value": GW_TOKEN, "domain": ".hacoo.app", "path": "/"},
        {"name": "gw-did", "value": "web_b8709a2bdd17479a8b2e570d38c46761", "domain": ".hacoo.app", "path": "/"},
        {"name": "system", "value": "pc", "domain": "affiliate.hacoo.app", "path": "/"},
        {"name": "lan", "value": "en", "domain": "affiliate.hacoo.app", "path": "/"},
        {"name": "cur", "value": "EUR", "domain": ".hacoo.app", "path": "/"},
        {"name": "region", "value": "DE", "domain": ".hacoo.app", "path": "/"},
        {"name": "has_uuid", "value": "true", "domain": ".hacoo.app", "path": "/"},
        {"name": "uuid", "value": "ios_804eeed6700943cf90f7540f23f596dc_sara", "domain": ".hacoo.app", "path": "/"},
    ]

def get_cookies_hacoo():
    return [
        {"name": "Authorization", "value": HACOO_COOKIE, "domain": ".hacoo.pl", "path": "/"},
        {"name": "cur", "value": "EUR", "domain": ".hacoo.pl", "path": "/"},
        {"name": "region", "value": "DE", "domain": ".hacoo.pl", "path": "/"},
        {"name": "lan", "value": "es", "domain": ".hacoo.pl", "path": "/"},
    ]

@app.route("/generate-link", methods=["POST"])
def generate_link():
    auth = request.headers.get("X-Auth-Token", "")
    if auth != "oslinks2026":
        return jsonify({"error": "Unauthorized"}), 401

    req_data = request.json
    product_id = req_data.get("product_id", "").strip()

    if not product_id:
        return jsonify({"error": "No product_id"}), 400

    product_url = f"https://www.hacoo.pl/en-DE/detail/{product_id}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            )
            context.add_cookies(get_cookies_affiliate())

            affiliate_link = None
            api_responses = []

            def handle_response(response):
                nonlocal affiliate_link
                if "promoLink" in response.url:
                    try:
                        body = response.json()
                        api_responses.append({"url": response.url, "body": body})
                        if body.get("code") == 1001:
                            d = body.get("data", {})
                            if isinstance(d, dict):
                                link = d.get("promoLink") or d.get("link") or d.get("promote_link") or d.get("url")
                                if link:
                                    affiliate_link = link
                    except:
                        pass

            page = context.new_page()
            page.on("response", handle_response)

            page.goto("https://affiliate.hacoo.app/es-DE/promotion/link", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            if "join" in page.url or "sign" in page.url:
                browser.close()
                return jsonify({"error": "Cookie expirada"}), 401

            page.evaluate("""() => {
                const portal = document.getElementById('headlessui-portal-root');
                if (portal) portal.remove();
            }""")
            page.wait_for_timeout(300)

            page.evaluate(f"""() => {{
                const textarea = document.querySelector('.f-text-field__input.f-textarea__input');
                if (textarea) {{
                    textarea.value = '{product_url}';
                    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}""")
            page.wait_for_timeout(500)

            page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.toLowerCase().includes('create')) {
                        btn.click();
                        break;
                    }
                }
            }""")

            page.wait_for_timeout(8000)
            browser.close()

            if affiliate_link:
                return jsonify({"link": affiliate_link})
            else:
                return jsonify({"error": "No se generó el link", "api_responses": api_responses}), 500

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-300:]}), 500


@app.route("/resolve-publication", methods=["POST"])
def resolve_publication():
    auth = request.headers.get("X-Auth-Token", "")
    if auth != "oslinks2026":
        return jsonify({"error": "Unauthorized"}), 401

    req_data = request.json
    pub_url = req_data.get("url", "").strip()

    if not pub_url:
        return jsonify({"error": "No url"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                viewport={"width": 390, "height": 844}
            )
            context.add_cookies(get_cookies_hacoo())

            product_ids = []

            def handle_api(response):
                try:
                    if any(x in response.url for x in ["product", "item", "goods", "detail", "post", "feed"]):
                        body = response.json()
                        body_str = str(body)
                        # Buscar IDs de 7-10 digitos
                        ids = re.findall(r'"product_id"\s*:\s*"?(\d{7,10})"?', body_str)
                        for pid in ids:
                            if pid not in product_ids:
                                product_ids.append(pid)
                except:
                    pass

            page = context.new_page()
            page.on("response", handle_api)

            # Navegar al link
            page.goto(pub_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # Intentar click en boton de descuento/canjear
            try:
                page.evaluate("""() => {
                    const elements = document.querySelectorAll('button, a, div, span');
                    for (const el of elements) {
                        const txt = (el.textContent || '').toLowerCase();
                        if (txt.includes('canjear') || txt.includes('claim') ||
                            txt.includes('get deal') || txt.includes('ver oferta') ||
                            txt.includes('shop now') || txt.includes('dto')) {
                            el.click();
                            break;
                        }
                    }
                }""")
                page.wait_for_timeout(4000)
            except:
                pass

            # Scroll para cargar productos lazy
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(3000)

            # Si no tenemos IDs via API, buscar en HTML y links
            if not product_ids:
                html = page.content()
                # Buscar en links
                try:
                    links = page.evaluate("() => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)")
                    for link in links:
                        m = re.search(r'hacoo\.pl/(?:p|detail)/(\d+)', link)
                        if m and m.group(1) not in product_ids:
                            product_ids.append(m.group(1))
                except:
                    pass
                # Buscar en HTML
                matches = re.findall(r'hacoo\.pl/(?:p|detail)/(\d+)', html)
                for pid in matches:
                    if pid not in product_ids:
                        product_ids.append(pid)
                # Buscar product_id en JSON
                matches2 = re.findall(r'"product_id"\s*:\s*"?(\d{7,10})"?', html)
                for pid in matches2:
                    if pid not in product_ids:
                        product_ids.append(pid)

            final_url = page.url
            browser.close()

            product_ids = list(dict.fromkeys(product_ids))[:10]
            return jsonify({"product_ids": product_ids, "count": len(product_ids), "source_url": final_url})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-300:]}), 500


@app.route("/publish-hacoo", methods=["POST"])
def publish_hacoo():
    auth = request.headers.get("X-Auth-Token", "")
    if auth != "oslinks2026":
        return jsonify({"error": "Unauthorized"}), 401

    req_data = request.json
    product_id = req_data.get("product_id", "").strip()
    affiliate_link = req_data.get("affiliate_link", "").strip()
    product_name = req_data.get("product_name", "").strip()

    if not product_id or not affiliate_link:
        return jsonify({"error": "Faltan datos"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
                viewport={"width": 390, "height": 844}
            )
            context.add_cookies(get_cookies_hacoo())
            page = context.new_page()
            page.goto(f"https://www.hacoo.pl/p/{product_id}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)
            browser.close()
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=True)
