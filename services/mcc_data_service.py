"""
MCC Data Service — provides synthetic but realistic transaction and competitor data.
In production: replace _get_synthetic_* methods with real bank MCC query calls.
"""
import math
import random
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# MCC to business category mapping (for OSM queries)
MCC_TO_OSM = {
    '5812': ['restaurant', 'cafe', 'fast_food'],
    '5411': ['supermarket', 'convenience', 'grocery'],
    '5912': ['pharmacy'],
    '5661': ['clothes', 'boutique'],
    '7011': ['hotel', 'hostel'],
    '5571': ['car_parts', 'tyres'],
    '5251': ['hardware', 'doityourself'],
    '8099': ['clinic', 'doctors'],
    '7299': ['hairdresser', 'beauty'],
    '5999': ['shop'],
}

# District population estimates (Tashkent, 2024)
DISTRICT_POPULATION = {
    'Yunusobod': 310000,
    'Chilonzor': 345000,
    'Mirzo Ulugbek': 275000,
    'Shayxontohur': 190000,
    'Olmazor': 220000,
    'Mirobod': 165000,
    'Yakkasaroy': 145000,
    'Bektemir': 95000,
    'Sergeli': 180000,
    'Uchtepa': 205000,
    'Yashnobod': 250000,
    'Zangiota': 130000,
}


class MCCDataService:
    OSM_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def get_population(self, district: str) -> int:
        return DISTRICT_POPULATION.get(district, 200000)

    def get_transaction_history(self, mcc_code: str, district: str, months: int = 24) -> list:
        """
        Returns monthly transaction volume data for the given MCC + district.
        Synthetic data with realistic Uzbekistan patterns.
        """
        population = self.get_population(district)
        base_monthly = self._base_revenue_for_mcc(mcc_code, population)
        history = []
        start_date = datetime.now() - timedelta(days=months * 30)
        rng = random.Random(hash(f"{mcc_code}{district}"))

        for i in range(months):
            month_date = start_date + timedelta(days=i * 30)
            month_num = month_date.month
            # Trend: 3% monthly growth
            trend_factor = 1 + 0.03 * (i / months)
            # Seasonality
            seasonal = self._monthly_seasonal_factor(month_num, mcc_code)
            # Noise ±15%
            noise = rng.gauss(1.0, 0.10)
            volume = int(base_monthly * trend_factor * seasonal * noise)
            history.append({
                'month': month_date.strftime('%Y-%m'),
                'transaction_count': max(50, int(volume / 150000)),
                'total_revenue_uzs': max(1_000_000, volume),
                'avg_ticket_uzs': 150000,
            })
        return history

    def _base_revenue_for_mcc(self, mcc_code: str, population: int) -> int:
        """Estimated monthly revenue for a typical business of this MCC type."""
        base_map = {
            '5812': 45_000_000,
            '5411': 80_000_000,
            '5912': 35_000_000,
            '5661': 25_000_000,
            '7011': 60_000_000,
            '5571': 30_000_000,
            '5251': 40_000_000,
            '8099': 28_000_000,
            '7299': 15_000_000,
            '5999': 20_000_000,
        }
        base = base_map.get(mcc_code, 30_000_000)
        # Scale slightly with population
        scale = math.log10(population / 100000 + 1)
        return int(base * scale)

    def _monthly_seasonal_factor(self, month: int, mcc_code: str) -> float:
        """Ramazon (March-April) and Navro'z (March 21) boosts for food/retail."""
        food_mccs = {'5812', '5411', '5999'}
        retail_mccs = {'5661', '5251'}
        # Navro'z — March peak for most
        navro_boost = {3: 1.35, 4: 1.20}
        # Ramazon boost (shifts annually, approximate month 3-4)
        if mcc_code in food_mccs:
            seasonal = {1: 0.85, 2: 0.90, 3: 1.30, 4: 1.15, 5: 1.10,
                        6: 0.95, 7: 0.90, 8: 1.00, 9: 1.05, 10: 1.10,
                        11: 1.05, 12: 1.20}
        elif mcc_code in retail_mccs:
            seasonal = {1: 0.80, 2: 0.85, 3: 1.40, 4: 1.20, 5: 1.00,
                        6: 0.95, 7: 0.90, 8: 0.95, 9: 1.00, 10: 1.05,
                        11: 1.10, 12: 1.25}
        else:
            seasonal = {m: 1.0 for m in range(1, 13)}
        return seasonal.get(month, 1.0)

    def get_competitors_from_osm(self, lat: float, lng: float,
                                  mcc_code: str, radius_m: int = 1000) -> list:
        """Fetch real competitors from OpenStreetMap Overpass API."""
        amenity_types = MCC_TO_OSM.get(mcc_code, ['shop'])
        amenity_filter = '|'.join(amenity_types)
        query = f"""
[out:json][timeout:15];
(
  node["amenity"~"{amenity_filter}"](around:{radius_m},{lat},{lng});
  way["amenity"~"{amenity_filter}"](around:{radius_m},{lat},{lng});
);
out center;
"""
        try:
            resp = requests.post(
                self.OSM_OVERPASS_URL,
                data={'data': query},
                timeout=20
            )
            if resp.status_code == 200:
                elements = resp.json().get('elements', [])
                competitors = []
                for el in elements[:20]:
                    c_lat = el.get('lat') or el.get('center', {}).get('lat', lat)
                    c_lng = el.get('lon') or el.get('center', {}).get('lon', lng)
                    dist = self._haversine(lat, lng, c_lat, c_lng)
                    rng = random.Random(hash(str(el.get('id', 0))))
                    competitors.append({
                        'id': el.get('id'),
                        'name': el.get('tags', {}).get('name', 'Noma\'lum'),
                        'type': el.get('tags', {}).get('amenity', 'shop'),
                        'lat': c_lat,
                        'lng': c_lng,
                        'distance_m': int(dist),
                        'age_years': rng.randint(1, 15),
                        'opening_hours': el.get('tags', {}).get('opening_hours', ''),
                        'closure_probability': 0.0,  # filled by Block E
                    })
                return sorted(competitors, key=lambda x: x['distance_m'])
        except Exception as e:
            logger.error(f"OSM Overpass failed: {e}")

        # Fallback: synthetic competitors
        return self._synthetic_competitors(lat, lng, mcc_code, radius_m)

    def _synthetic_competitors(self, lat: float, lng: float,
                                mcc_code: str, radius_m: int) -> list:
        business_names_by_mcc = {
            '5812': ["Cafe Milano", "Osh Markazi", "Choyxona Bahor", "Fast Lunch Restoran", "Grand Cafe Toshkent", "Milliy Taomlar", "Pizza House UZ"],
            '5411': ["Mini Market Yunusobod", "Fresh Store", "Narxi Arzon Savdo", "Do'kon Plus", "Mahalla Market", "Oziq-Ovqat Plus"],
            '5912': ["Apteka 24", "Sog'lom Apteka", "MedFarm Dorixona", "Green Pharmacy", "Birinchi Apteka"],
            '5661': ["Fashion House Toshkent", "Style Boutique", "Kiyim Dunyosi", "Mode Shop", "Trend Clothes"],
            '7011': ["Toshkent City Hotel", "Registon Inn", "Grand Plaza Hotel", "Silk Road Suites", "Business Hotel UZ"],
            '7012': ["Apart-Hotel Samarqand", "Vaqtinchalik Uy", "City Apart", "Comfort Inn Toshkent"],
            '4722': ["Uzbekistan Travel", "Silk Road Tour", "Asia Tour Group", "Grand Tour UZ", "Discovery Travel"],
            '7991': ["Bobur Bog'i", "Toshkent Aquapark", "Navruz Park", "Safari Adventure"],
            '5251': ["Mega Qurilish Market", "BuildPro Materiallari", "Usta Qurilish", "Temir Beton Savdo", "Master Stroy"],
            '5065': ["Elektro Market", "Voltaj Elektr Jihozlari", "Power Supply UZ", "Elektr Uskunalar"],
            '5039': ["Qum va Sement Savdo", "Xom Ashyo Markazi", "Qurilish Materiallar", "Stone & Sand UZ"],
            '7389': ["Usta Qurilish Pudrat", "Pro Remont", "Master Build", "Qurilish Xizmatlari"],
            '5131': ["To'qimachilik Ulgurji", "Matolar Savdosi", "Textile Hub UZ", "Ip va Mato Markazi"],
            '5137': ["Forma Kiyimlar", "Maxsus Kiyim Savdo", "Work Wear UZ", "Professional Forma"],
            '5661': ["Kiyim Dunyosi", "Fashion Park", "Moda Markazi", "Trend Clothes"],
            '5699': ["Kiyim Bozori", "Clothes & More", "Libos Savdo", "Fashion Factory"],
            '8099': ["MedLine Klinikasi", "Shifo Medical Center", "Sog'liq Markazi", "Health Point", "Oilaviy Klinika"],
            '8011': ["Dr. Karimov Klinikasi", "Tibbiy Markaz", "Salomatlik Klinikasi", "Yurak-Tomir Markazi"],
            '7372': ["IT Solutions UZ", "TechPro Dasturlar", "SoftLine Toshkent", "Digital Hub"],
            '8049': ["Sof Stomatologiya", "Oq Tish Klinikasi", "Dental Plus", "Tibbiy Stomatologiya"],
            '7299': ["Beauty & Spa Toshkent", "Sartaroshxona Fayz", "Glamour Studio", "Style Salon", "Nafis Go'zallik"],
            '5411': ["Korzinka Mini Market", "Makro Do'koni", "Metro Supermarket", "Arzon Bozor"],
            '5912': ["Apteka Plus", "Sog'lom Dorixona", "MedFarm", "Green Farm Apteka"],
            '5200': ["Mebel Dunyosi", "Uy Jihozlari Savdo", "Home & Comfort", "Comfort Mebel"],
            '5310': ["Universal Do'kon", "Chegirma Markazi", "Discount Mall", "Economy Store"],
            '5945': ["O'yinchoq Olami", "Kids World", "Hobby Shop UZ", "Fun Store"],
            '5999': ["Savdo Markazi", "Universal Shop", "Market Plus", "Mahalla Savdo", "Umumiy Do'kon"],
        }
        names = business_names_by_mcc.get(mcc_code, [
            "Mahalla Savdo Markazi", "Do'kon & Xizmat", "Yaqin Raqobatchi",
            "Soha Korxona", "Biznes Plus UZ", "Tadbirkor Savdosi",
        ])
        rng = random.Random(hash(f"{lat}{lng}{mcc_code}"))
        result = []
        count = rng.randint(3, min(8, len(names) + 3))
        for i in range(count):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(50, radius_m)
            dlat = dist * math.cos(angle) / 111000
            dlng = dist * math.sin(angle) / (111000 * math.cos(math.radians(lat)))
            name = names[i % len(names)] if i < len(names) else f"Raqobatchi {i+1}"
            result.append({
                'id': i + 1,
                'name': name,
                'type': MCC_TO_OSM.get(mcc_code, ['shop'])[0],
                'lat': lat + dlat,
                'lng': lng + dlng,
                'distance_m': int(dist),
                'age_years': rng.randint(1, 12),
                'opening_hours': '09:00-21:00',
                'closure_probability': 0.0,
            })
        return sorted(result, key=lambda x: x['distance_m'])

    def get_district_churn_rate(self, district: str, mcc_code: str) -> float:
        """Typical annual business closure rate (%) by district and type."""
        base_churn = {
            'Bektemir': 22.0, 'Sergeli': 20.0, 'Zangiota': 18.0,
            'Yakkasaroy': 15.0, 'Yashnobod': 16.0, 'Uchtepa': 17.0,
            'Shayxontohur': 14.0, 'Mirobod': 13.0, 'Olmazor': 14.0,
            'Chilonzor': 12.0, 'Mirzo Ulugbek': 11.0, 'Yunusobod': 10.0,
        }
        return base_churn.get(district, 15.0)

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
