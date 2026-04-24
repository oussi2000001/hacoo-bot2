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


@app.route("/get-product-info", methods=["POST"])
def get_product_info():
    auth = request.headers.get("X-Auth-Token", "")
    if auth != "oslinks2026":
        return jsonify({"error": "Unauthorized"}), 401

    req_data = request.json
    product_id = req_data.get("product_id", "").strip()

    if not product_id:
        return jsonify({"error": "No product_id"}), 400

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            )
            context.add_cookies(get_cookies_hacoo())

            page = context.new_page()
            page.goto(f"https://www.hacoo.pl/p/{product_id}", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            name = None
            try:
                name = page.locator("h1").first.inner_text(timeout=5000)
            except:
                pass
            if not name:
                try:
                    name = page.title()
                except:
                    name = f"Producto {product_id}"

            image_url = None
            try:
                img = page.locator("img").first
                image_url = img.get_attribute("src", timeout=5000)
            except:
                pass

            browser.close()

            return jsonify({
                "name": name.strip() if name else f"Producto {product_id}",
                "image_url": image_url or ""
            })

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

            try:
                page.locator("[data-testid='more-options'], button.more, .more-btn").first.click(timeout=5000)
            except:
                page.evaluate("""() => {
                    const btns = document.querySelectorAll('button, [role="button"]');
                    for (const b of btns) {
                        if (b.innerHTML.includes('ellipsis') || b.innerHTML.includes('more') || b.textContent.trim() === '···' || b.textContent.trim() === '...') {
                            b.click();
                            break;
                        }
                    }
                }""")
            page.wait_for_timeout(1500)

            try:
                page.get_by_text("Publicar con produc", exact=False).first.click(timeout=5000)
            except:
                page.evaluate("""() => {
                    const els = document.querySelectorAll('*');
                    for (const el of els) {
                        if (el.textContent.includes('Publicar con') || el.textContent.includes('Publish with')) {
                            el.click();
                            break;
                        }
                    }
                }""")
            page.wait_for_timeout(1500)

            try:
                page.get_by_text("Editar ahora", exact=False).first.click(timeout=5000)
            except:
                page.get_by_text("Edit now", exact=False).first.click(timeout=5000)
            page.wait_for_timeout(2000)

            try:
                page.get_by_text("Publicar", exact=True).last.click(timeout=5000)
            except:
                page.get_by_text("Publish", exact=True).last.click(timeout=5000)
            page.wait_for_timeout(3000)

            browser.close()
            return jsonify({"success": True, "message": "Publicado en Hacoo"})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-300:]}), 500


@app.route("/resolve-publication", methods=["POST"])
def resolve_publication():
    """Entra a una publicacion de Hacoo con sesion del usuario y extrae IDs de productos"""
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
            
            # Añadir cookies de sesion de Hacoo para acceder a publicaciones restringidas
            context.add_cookies([
                {"name": "Authorization", "value": HACOO_COOKIE, "domain": ".hacoo.pl", "path": "/"},
                {"name": "cur", "value": "EUR", "domain": ".hacoo.pl", "path": "/"},
                {"name": "region", "value": "DE", "domain": ".hacoo.pl", "path": "/"},
                {"name": "lan", "value": "es", "domain": ".hacoo.pl", "path": "/"},
            ])

            page = context.new_page()
            
            # Primero resolver el link corto si es necesario
            page.goto(pub_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            
            final_url = page.url
            product_ids = []
            
            # Buscar IDs en la URL final
            import re
            match_url = re.search(r'hacoo\.pl/p/(\d+)', final_url)
            if match_url:
                product_ids.append(match_url.group(1))
            else:
                # Es una publicacion - buscar productos dentro
                # Buscar en todos los links de la pagina
                try:
                    links = page.evaluate("""() => {
                        const links = document.querySelectorAll('a[href]');
                        return Array.from(links).map(l => l.href);
                    }""")
                    for link in links:
                        m = re.search(r'hacoo\.pl/p/(\d+)', link)
                        if m and m.group(1) not in product_ids:
                            product_ids.append(m.group(1))
                except:
                    pass

                # Buscar en el HTML completo
                html = page.content()
                
                # Patron 1: links directos
                matches = re.findall(r'hacoo\.pl/p/(\d+)', html)
                for pid in matches:
                    if pid not in product_ids:
                        product_ids.append(pid)
                
                # Patron 2: IDs en JSON del codigo fuente
                matches2 = re.findall(r'"product_id"\s*:\s*"?(\d{7,10})"?', html)
                for pid in matches2:
                    if pid not in product_ids:
                        product_ids.append(pid)
                        
                # Patron 3: en atributos data
                matches3 = re.findall(r'data-id="(\d{7,10})"', html)
                for pid in matches3:
                    if pid not in product_ids:
                        product_ids.append(pid)

                # Si aun no encontramos nada, hacer click en el primer producto visible
                if not product_ids:
                    try:
                        # Buscar imagenes de productos clickables
                        page.wait_for_selector('img', timeout=5000)
                        page.evaluate("""() => {
                            const imgs = document.querySelectorAll('img');
                            for (const img of imgs) {
                                const parent = img.closest('a');
                                if (parent && parent.href && parent.href.includes('hacoo')) {
                                    parent.click();
                                    break;
                                }
                            }
                        }""")
                        page.wait_for_timeout(3000)
                        new_url = page.url
                        m = re.search(r'hacoo\.pl/p/(\d+)', new_url)
                        if m:
                            product_ids.append(m.group(1))
                    except:
                        pass

            browser.close()
            
            # Filtrar IDs duplicados y limitar a 10 productos por publicacion
            product_ids = list(dict.fromkeys(product_ids))[:10]
            
            return jsonify({"product_ids": product_ids, "count": len(product_ids), "source_url": final_url})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-300:]}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, threaded=False)
