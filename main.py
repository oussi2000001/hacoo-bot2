from flask import Flask, request, jsonify
import os
import requests
import hashlib
import time
import json

app = Flask(__name__)

PROD_AUTH_TOKEN = os.environ.get("PROD_AUTH_TOKEN", "")
GW_TOKEN = os.environ.get("GW_TOKEN", "")

def generate_sign(sid, data, gw_ver, ct, plat, appname):
    sign_str = "1" + str(sid) + data + str(gw_ver) + str(ct) + plat + appname
    return hashlib.md5(sign_str.encode()).hexdigest()

@app.route("/generate-link", methods=["POST"])
def generate_link():
    req_data = request.json
    product_id = req_data.get("product_id", "").strip()
    
    if not product_id:
        return jsonify({"error": "No product_id"}), 400

    product_url = f"https://www.hacoo.pl/en-DE/detail/{product_id}"
    
    # Probar diferentes sid values
    for sid in [9, 12, 26]:
        try:
            data = json.dumps({"link": product_url}, separators=(',', ':'))
            gw_ver = "1"
            ct = str(int(time.time() * 1000))
            plat = "pc"
            appname = "saramart"
            
            sign = generate_sign(sid, data, gw_ver, ct, plat, appname)
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Cookie": f"PROD_AUTH_TOKEN={PROD_AUTH_TOKEN}; has_token=1; gw-token={GW_TOKEN}; system=pc; lan=en; cur=EUR",
                "Origin": "https://affiliate.hacoo.app",
                "Referer": "https://affiliate.hacoo.app/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            }
            
            payload = {
                "data": data,
                "gw_ver": gw_ver,
                "ct": ct,
                "plat": plat,
                "appname": appname,
                "sign": sign
            }
            
            response = requests.post(
                f"https://gw.hacoo.app/gw/dwp.aff-home-core.promoLink/1?sid={sid}",
                data=payload,
                headers=headers,
                timeout=15
            )
            
            result = response.json()
            print(f"sid={sid}, sign={sign}, result={result}")
            
            if result.get("code") == 1001:
                # Buscar el link en la respuesta
                link = None
                if result.get("data"):
                    d = result["data"]
                    if isinstance(d, dict):
                        link = d.get("link") or d.get("promote_link") or d.get("url")
                    elif isinstance(d, str):
                        link = d
                
                if link:
                    return jsonify({"link": link})
                    
        except Exception as e:
            print(f"Error con sid={sid}: {e}")
            continue
    
    return jsonify({"error": "No se pudo generar el link", "sign_issue": True}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
