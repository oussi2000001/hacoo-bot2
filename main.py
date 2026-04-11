from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os
import re
import base64

app = Flask(__name__)

PROD_AUTH_TOKEN = os.environ.get("PROD_AUTH_TOKEN", "")
GW_TOKEN = os.environ.get("GW_TOKEN", "")

@app.route("/generate-link", methods=["POST"])
def generate_link():
    req_data = request.json
    product_id = req_data.get("product_id", "").strip()
    
    if not product_id:
        return jsonify({"error": "No product_id"}), 400

    product_url = f"https://www.hacoo.pl/en-DE/detail/{product_id}"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            context.add_cookies([
                {"name": "PROD_AUTH_TOKEN", "value": PROD_AUTH_TOKEN, "domain": "affiliate.hacoo.app", "path": "/"},
                {"name": "has_token", "value": "1", "domain": "affiliate.hacoo.app", "path": "/"},
                {"name": "gw-token", "value": GW_TOKEN, "domain": ".hacoo.app", "path": "/"},
                {"name": "gw-did", "value": "web_b8709a2bdd17479a8b2e570d38c46761", "domain": ".hacoo.app", "path": "/"},
                {"name": "system", "value": "pc", "domain": "affiliate.hacoo.app", "path": "/"},
                {"name": "lan", "value": "en", "domain": "affiliate.hacoo.app", "path": "/"},
                {"name": "cur", "value": "EUR", "domain": ".hacoo.app", "path": "/"},
                {"name": "region", "value": "DE", "domain": ".hacoo.app", "path": "/"},
            ])
            
            page = context.new_page()
            
            # Interceptar la respuesta de la API
            affiliate_link = None
            
            def handle_response(response):
                nonlocal affiliate_link
                if "promoLink" in response.url:
                    try:
                        body = response.json()
                        if body.get("code") == 1001:
                            d = body.get("data", {})
                            if isinstance(d, dict):
                                link = d.get("link") or d.get("promote_link")
                                if link:
                                    affiliate_link = link
                    except:
                        pass
            
            page.on("response", handle_response)
            
            page.goto("https://affiliate.hacoo.app/es-DE/promotion/link", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            
            if "join" in page.url or "sign" in page.url:
                browser.close()
                return jsonify({"error": "Cookie expirada - necesitas renovarla"}), 401
            
            # Tomar screenshot para debug
            screenshot = base64.b64encode(page.screenshot()).decode()
            
            # Buscar todos los inputs y textareas
            elements_info = page.evaluate("""() => {
                const els = document.querySelectorAll('textarea, input[type="text"], input:not([type])');
                return Array.from(els).map(el => ({
                    tag: el.tagName,
                    type: el.type,
                    placeholder: el.placeholder,
                    class: el.className.slice(0, 50),
                    visible: el.offsetParent !== null
                }));
            }""")
            
            # Intentar llenar
            filled = False
            for selector in ["textarea", "input[type='text']", "input:not([type])", "[placeholder*='http']", "[placeholder*='url']", "[placeholder*='URL']", "[placeholder*='link']"]:
                try:
                    els = page.locator(selector).all()
                    for el in els:
                        if el.is_visible():
                            el.fill(product_url)
                            filled = True
                            break
                    if filled:
                        break
                except:
                    continue
            
            if not filled:
                # JavaScript fallback
                page.evaluate(f"""() => {{
                    const els = document.querySelectorAll('textarea, input');
                    for (const el of els) {{
                        if (el.offsetParent !== null) {{
                            el.value = '{product_url}';
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            break;
                        }}
                    }}
                }}""")
                filled = True
            
            page.wait_for_timeout(500)
            
            # Click Create Link
            for btn in ["button:has-text('Create Link')", "button:has-text('Create')", "button:has-text('create')", "button[type='submit']", "form button"]:
                try:
                    b = page.locator(btn).first
                    if b.is_visible(timeout=1000):
                        b.click()
                        break
                except:
                    continue
            
            # Esperar respuesta de la API
            page.wait_for_timeout(8000)
            
            browser.close()
            
            if affiliate_link:
                return jsonify({"link": affiliate_link})
            else:
                return jsonify({
                    "error": "No se encontró el link",
                    "elements_found": elements_info,
                    "screenshot": screenshot[:500]  # Solo primeros 500 chars para debug
                }), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
