from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

PROD_AUTH_TOKEN = os.environ.get("PROD_AUTH_TOKEN", "")

@app.route("/generate-link", methods=["POST"])
def generate_link():
    data = request.json
    product_id = data.get("product_id", "").strip()
    
    if not product_id:
        return jsonify({"error": "No product_id"}), 400

    product_url = f"https://www.hacoo.pl/en-DE/detail/{product_id}"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            
            # Inyectar la cookie de sesion
            context.add_cookies([{
                "name": "PROD_AUTH_TOKEN",
                "value": PROD_AUTH_TOKEN,
                "domain": "affiliate.hacoo.app",
                "path": "/"
            }, {
                "name": "has_token",
                "value": "1",
                "domain": "affiliate.hacoo.app",
                "path": "/"
            }])
            
            page = context.new_page()
            
            # Ir a Link Customizer
            page.goto("https://affiliate.hacoo.app/es-DE/promotion/link")
            page.wait_for_load_state("networkidle")
            
            # Pegar el link del producto
            page.fill('textarea', product_url)
            
            # Hacer clic en Create Link
            page.locator('button:has-text("Create Link")').click()
            
            # Esperar que aparezca el link generado
            page.wait_for_selector('text=onlyaff.app', timeout=15000)
            
            # Extraer el link
            affiliate_link = page.locator('input[readonly]').first.input_value()
            if not affiliate_link:
                affiliate_link = page.locator('text=https://c.onlyaff.app').first.inner_text()
            
            browser.close()
            return jsonify({"link": affiliate_link.strip()})
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
