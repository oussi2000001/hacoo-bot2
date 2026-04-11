from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import os
import re

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
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
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
            page.goto("https://affiliate.hacoo.app/es-DE/promotion/link", wait_until="networkidle")
            page.wait_for_timeout(3000)
            
            # Intentar diferentes selectores
            selectors = ["textarea", "input[type='text']", "[placeholder*='http']", "[class*='textarea']"]
            filled = False
            for selector in selectors:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=2000):
                        el.fill(product_url)
                        filled = True
                        break
                except:
                    continue
            
            if not filled:
                page.evaluate(f"""
                    const inputs = document.querySelectorAll('textarea, input[type="text"]');
                    if (inputs.length > 0) {{
                        inputs[0].value = '{product_url}';
                        inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                """)
            
            # Click Create Link
            btn_selectors = ["button:has-text('Create Link')", "button:has-text('create')", "button[type='submit']"]
            for btn in btn_selectors:
                try:
                    b = page.locator(btn).first
                    if b.is_visible(timeout=2000):
                        b.click()
                        break
                except:
                    continue
            
            page.wait_for_timeout(5000)
            
            # Extraer link
            affiliate_link = None
            content = page.content()
            matches = re.findall(r'https://c\.onlyaff\.app/\w+', content)
            if matches:
                affiliate_link = matches[0]
            
            if not affiliate_link:
                try:
                    inputs = page.locator("input[readonly]").all()
                    for inp in inputs:
                        val = inp.input_value()
                        if 'onlyaff' in val or 'hacoo' in val:
                            affiliate_link = val
                            break
                except:
                    pass
            
            browser.close()
            
            if affiliate_link:
                return jsonify({"link": affiliate_link.strip()})
            else:
                return jsonify({"error": "No se pudo extraer el link"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
