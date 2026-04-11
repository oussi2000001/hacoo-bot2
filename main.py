from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os

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
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
            )
            
            # Añadir TODAS las cookies del cURL real
            context.add_cookies([
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
            ])
            
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
                                link = d.get("link") or d.get("promote_link") or d.get("url")
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
            
            # Eliminar popup bloqueador
            page.evaluate("""() => {
                const portal = document.getElementById('headlessui-portal-root');
                if (portal) portal.remove();
            }""")
            page.wait_for_timeout(300)
            
            # Llenar textarea con JavaScript
            page.evaluate(f"""() => {{
                const textarea = document.querySelector('.f-text-field__input.f-textarea__input');
                if (textarea) {{
                    textarea.value = '{product_url}';
                    textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
            }}""")
            page.wait_for_timeout(500)
            
            # Click botón con JavaScript
            page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.toLowerCase().includes('create')) {
                        btn.click();
                        break;
                    }
                }
            }""")
            
            # Esperar respuesta API
            page.wait_for_timeout(8000)
            
            browser.close()
            
            if affiliate_link:
                return jsonify({"link": affiliate_link})
            else:
                return jsonify({
                    "error": "No se generó el link",
                    "api_responses": api_responses
                }), 500
            
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-300:]}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
