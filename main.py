from flask import Flask, render_template, request
import requests
import os

app = Flask(__name__)

# Load API keys from environment
UBER_SERVER_TOKEN = os.environ.get('UBER_SERVER_TOKEN')
UBER_CLIENT_ID = os.environ.get('UBER_CLIENT_ID')
OLA_PARTNER_SOURCE = os.environ.get('OLA_PARTNER_SOURCE')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

def geocode_address(address):
    """Convert address into latitude and longitude using Google Maps Geocoding API"""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": GOOGLE_API_KEY
    }
    response = requests.get(url, params=params).json()
    if response['status'] == 'OK':
        location = response['results'][0]['geometry']['location']
        return location['lat'], location['lng']
    else:
        raise Exception(f"Geocoding error: {response['status']}")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        pickup_address = request.form['pickup_address']
        drop_address = request.form['drop_address']

        try:
            pickup_lat, pickup_lng = geocode_address(pickup_address)
            drop_lat, drop_lng = geocode_address(drop_address)
        except Exception as e:
            return f"Error in geocoding: {e}"

        # Fetch Uber prices
        uber_prices = []
        try:
            uber_response = requests.get(
                "https://api.uber.com/v1.2/estimates/price",
                headers={"Authorization": f"Token {UBER_SERVER_TOKEN}"},
                params={
                    "start_latitude": pickup_lat,
                    "start_longitude": pickup_lng,
                    "end_latitude": drop_lat,
                    "end_longitude": drop_lng
                }
            ).json()
            for price in uber_response.get('prices', []):
                uber_prices.append({
                    "service": f"Uber {price['display_name']}",
                    "price_min": price.get('low_estimate', 0),
                    "price_max": price.get('high_estimate', 0),
                    "deeplink": (
                        f"https://m.uber.com/ul/?action=setPickup"
                        f"&client_id={UBER_CLIENT_ID}"
                        f"&pickup[latitude]={pickup_lat}&pickup[longitude]={pickup_lng}"
                        f"&dropoff[latitude]={drop_lat}&dropoff[longitude]={drop_lng}"
                        f"&product_id={price['product_id']}"
                    )
                })
        except Exception as e:
            print("Error fetching Uber data:", e)

        # Fetch Ola prices
        ola_prices = []
        try:
            ola_response = requests.get(
                "https://devapi.olacabs.com/v1/products",
                headers={"Authorization": f"Bearer {OLA_PARTNER_SOURCE}"},
                params={
                    "pickup_lat": pickup_lat,
                    "pickup_lng": pickup_lng
                }
            ).json()

            for ride in ola_response.get('ride_estimate', []):
                ola_prices.append({
                    "service": f"Ola {ride['category']}",
                    "price_min": ride.get('amount_min', 0),
                    "price_max": ride.get('amount_max', 0),
                    "deeplink": (
                        f"olacabs://app/launch?"
                        f"lat={pickup_lat}&lng={pickup_lng}"
                        f"&drop_lat={drop_lat}&drop_lng={drop_lng}"
                        f"&category={ride['category']}"
                    )
                })
        except Exception as e:
            print("Error fetching Ola data:", e)

        # Combine and sort
        all_prices = uber_prices + ola_prices
        all_prices.sort(key=lambda x: x['price_min'])

        return render_template('results.html', prices=all_prices)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
