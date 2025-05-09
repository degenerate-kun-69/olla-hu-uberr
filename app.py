import os
import requests
from flask import Flask, jsonify, redirect, request, session, url_for, render_template, flash
from dotenv import load_dotenv

# ─── Load .env ───────────────────────────────────────────────
load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24)

# ─── Configuration ───────────────────────────────────────────
UBER_CLIENT_ID = os.getenv("UBER_CLIENT_ID")
UBER_CLIENT_SECRET = os.getenv("UBER_CLIENT_SECRET")
UBER_REDIRECT_URI = os.getenv("UBER_REDIRECT_URI")
OLA_PARTNER_TOKEN = os.getenv("OLA_PARTNER_SOURCE")
MAPSCO_API_KEY = os.getenv("GEOCODE_API_KEY")

# ─── OAuth URLs ──────────────────────────────────────────────
UBER_AUTH_URL = "https://login.uber.com/oauth/v2/authorize"
UBER_TOKEN_URL = "https://login.uber.com/oauth/v2/token"

# ─── Helper Functions ────────────────────────────────────────
"""
def geocode_address(address: str):
    """"""
    url = "https://geocode.maps.co/search"
    resp = requests.get(url, params={
        "q": address,
        "api_key": MAPSCO_API_KEY})
   
    if resp.status_code != 200:
        raise Exception(f"Geocoding API error: HTTP {resp.status_code} - {resp.text}")

    try:
        data = resp.json()
    except ValueError:
        raise Exception("Geocoding error: Invalid JSON response")

    if isinstance(data, list) and len(data) > 0:
        lat = float(data[0]['lat'])
        lon = float(data[0]['lon'])
        return lat, lon
    else:
        raise Exception("Geocoding failed: No results found.")
        """
print("Geocoding API Key:", MAPSCO_API_KEY)
def geocode_address(address):
    """Convert address into latitude and longitude using Maps.co API."""
    url = "https://geocode.maps.co/search"
    params = {
        "q": address,
        "api_key": MAPSCO_API_KEY
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(f"Geocoding API error: HTTP {response.status_code} - {response.text}")

    try:
        data = response.json()
    except ValueError:
        raise Exception("Geocoding error: Invalid JSON response")

    if isinstance(data, list) and len(data) > 0:
        lat = float(data[0]['lat'])
        lon = float(data[0]['lon'])
        return lat, lon
    else:
        raise Exception("Geocoding failed: No results found.")

def index():
    if request.method == 'POST':
        pickup_address = request.form['pickup_address']
        drop_address = request.form['drop_address']

        try:
            pickup_lat, pickup_lng = geocode_address(pickup_address)
            drop_lat, drop_lng = geocode_address(drop_address)
        except Exception as e:
            return f"Error in geocoding: {e}"

def fetch_uber_prices(pickup, dropoff):
    token = session.get("uber_access_token")
    if not token:
        raise RuntimeError("No Uber token found. Login required.")
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "start_latitude": pickup[0],
        "start_longitude": pickup[1],
        "end_latitude": dropoff[0],
        "end_longitude": dropoff[1],
    }
    resp = requests.get("https://api.uber.com/v1.2/estimates/price", headers=headers, params=params)
    resp.raise_for_status()
    out = []
    for p in resp.json().get("prices", []):
        out.append({
            "service": f"Uber {p.get('display_name')}",
            "price_min": p.get("low_estimate", 0),
            "price_max": p.get("high_estimate", 0),
            "duration": f"{round(p.get('duration', 0)/60)} min",
            "distance": f"{p.get('distance', 0)} km",
            "deeplink": (
                "https://m.uber.com/ul/?action=setPickup"
                f"&client_id={UBER_CLIENT_ID}"
                f"&pickup[latitude]={pickup[0]}&pickup[longitude]={pickup[1]}"
                f"&dropoff[latitude]={dropoff[0]}&dropoff[longitude]={dropoff[1]}"
                f"&product_id={p.get('product_id')}"
            )
        })
    return out


def fetch_ola_prices(pickup, dropoff):
    headers = {"Authorization": f"Bearer {OLA_PARTNER_TOKEN}"}
    params = {"pickup_lat": pickup[0], "pickup_lng": pickup[1]}
    resp = requests.get("https://devapi.olacabs.com/v1/products", headers=headers, params=params)
    resp.raise_for_status()
    out = []
    for r in resp.json().get("ride_estimate", []):
        out.append({
            "service": f"Ola {r.get('category')}",
            "price_min": r.get("amount_min", 0),
            "price_max": r.get("amount_max", 0),
            "duration": "-",
            "distance": "-",
            "deeplink": (
                "olacabs://app/launch?"
                f"lat={pickup[0]}&lng={pickup[1]}"
                f"&drop_lat={dropoff[0]}&drop_lng={dropoff[1]}"
                f"&category={r.get('category')}"
            )
        })
    return out

# ─── Routes ──────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html", is_connected=session.get("uber_access_token") is not None)

@app.route('/autocomplete')
def autocomplete():
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    try:
        response = requests.get(
            "https://geocode.maps.co/search",
            params={
                "q": query,
                "api_key": MAPSCO_API_KEY  # From environment
            }
        )
        response.raise_for_status()
        return jsonify(response.json()[:5])  # Return first 5 results
    except Exception as e:
        print(f"Geocoding error: {e}")
        return jsonify([])
    
@app.route("/login")
def login():
    return redirect(
        f"{UBER_AUTH_URL}?client_id={UBER_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={UBER_REDIRECT_URI}"
        f"&scope=request"
    )


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        flash("Uber login failed.")
        return redirect(url_for("home"))
    data = {
        "client_id": UBER_CLIENT_ID,
        "client_secret": UBER_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": UBER_REDIRECT_URI,
        "code": code
    }
    resp = requests.post(UBER_TOKEN_URL, data=data)
    if resp.status_code != 200:
        flash("Failed to get Uber token.")
        return redirect(url_for("home"))
    session["uber_access_token"] = resp.json()["access_token"]
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.pop("uber_access_token", None)
    flash("Logged out of Uber.")
    return redirect(url_for("home"))


@app.route("/results", methods=["POST"])
def results():
    pickup_address = request.form["pickup"]
    dropoff_address = request.form["drop"]

    try:
        pickup_coords = geocode_address(pickup_address)
        dropoff_coords = geocode_address(dropoff_address)
    except Exception as e:
        flash(f"Geocoding error: {e}")
        return redirect(url_for("home"))

    prices = []
    try:
        if session.get("uber_access_token"):
            prices += fetch_uber_prices(pickup_coords, dropoff_coords)
    except Exception as e:
        flash(f"Uber API error: {e}")

    try:
        prices += fetch_ola_prices(pickup_coords, dropoff_coords)
    except Exception as e:
        flash(f"Ola API error: {e}")

    prices.sort(key=lambda x: x["price_min"])
    return render_template("results.html", prices=prices)

@app.route("/ai-prediction")
def ai_prediction():
    return render_template("ai_prediction.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/sample-rides")
def sample_rides():
    return render_template("sample_rides.html")

# ─── Run ─────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)
