"""
category_analysis/models.py
Four specialist detail models — each linked OneToOne to BusinessAnalysisRequest.
Only one will exist per analysis depending on business_category_type.
"""
from django.db import models
from apps.core.models import BusinessAnalysisRequest


# ══════════════════════════════════════════════════════════════
# 1. HOTEL / HOSPITALITY
# ══════════════════════════════════════════════════════════════

class HotelDetail(models.Model):
    HOTEL_CATEGORY_CHOICES = [
        ('1_star', '1 yulduz'),
        ('2_star', '2 yulduz'),
        ('3_star', '3 yulduz'),
        ('4_star', '4 yulduz'),
        ('5_star', '5 yulduz'),
        ('boutique', 'Butik mehmonxona'),
        ('hostel', 'Hostel'),
        ('apart_hotel', 'Apart-hotel'),
        ('eco_lodge', 'Eko-turar joy'),
    ]
    CITY_CHOICES = [
        ('tashkent', 'Toshkent'),
        ('samarkand', 'Samarqand'),
        ('bukhara', 'Buxoro'),
        ('khiva', 'Xiva'),
        ('namangan', 'Namangan'),
        ('andijan', 'Andijon'),
        ('other', 'Boshqa'),
    ]
    TRANSPORT_CHOICES = [
        ('walking', "Piyoda (<5 min)"),
        ('close', "Yaqin (5-15 min)"),
        ('moderate', "O'rtacha (15-30 min)"),
        ('far', "Uzoq (>30 min)"),
    ]

    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='hotel_detail'
    )
    hotel_name = models.CharField(max_length=200, blank=True, verbose_name='Mehmonxona nomi')
    hotel_category = models.CharField(max_length=20, choices=HOTEL_CATEGORY_CHOICES, default='3_star')
    total_rooms = models.IntegerField(default=20, verbose_name='Xonalar soni')
    city = models.CharField(max_length=30, choices=CITY_CHOICES, default='tashkent')

    # Location intelligence
    distance_to_city_center_km = models.FloatField(default=5.0, verbose_name="Markazgacha (km)")

    # Transport
    public_transport_access = models.CharField(max_length=20, choices=TRANSPORT_CHOICES, default='close')
    taxi_availability = models.BooleanField(default=True, verbose_name="Taksi mavjud")
    parking_spaces = models.IntegerField(default=10, verbose_name="Avtoturargoh joylari")

    # Booking platforms (comma-separated)
    booking_platforms = models.JSONField(default=list, verbose_name="Booking platformalari")

    # Competition
    competitors_nearby = models.TextField(blank=True, verbose_name="Yaqin raqobatchilar")

    # Financials (USD-based for hotel)
    room_rate_low_usd = models.DecimalField(max_digits=8, decimal_places=2, default=40.0, verbose_name="Quyi sezon narxi (USD/kecha)")
    room_rate_high_usd = models.DecimalField(max_digits=8, decimal_places=2, default=80.0, verbose_name="Yuqori sezon narxi (USD/kecha)")
    target_occupancy_pct = models.FloatField(default=65.0, verbose_name="Maqsad to'liqlik %")

    # Subsidies
    applying_for_subsidy = models.BooleanField(default=False, verbose_name="VM 550/2024 subsidiyasi")
    franchise_agreement = models.BooleanField(default=False, verbose_name="Xalqaro brend franchayzi")

    # New bank fields
    booking_profile = models.CharField(max_length=20, default='no')
    advance_booking_pct = models.IntegerField(default=30)
    collateral_type = models.CharField(max_length=50, default='property')

    class Meta:
        verbose_name = 'Mehmonxona tafsilotlari'

    def __str__(self):
        return f"Hotel: {self.hotel_name or self.request}"

    @property
    def monthly_revpar_usd(self):
        """Revenue Per Available Room × days estimate"""
        avg_rate = (float(self.room_rate_low_usd) + float(self.room_rate_high_usd)) / 2
        return avg_rate * (self.target_occupancy_pct / 100)

    @property
    def monthly_revenue_usd(self):
        return self.monthly_revpar_usd * self.total_rooms * 30


class HotelAnalysisResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='hotel_result'
    )
    # H1 — Location intelligence
    location_score = models.FloatField(default=0.0)
    tourist_flow_monthly = models.JSONField(default=list)   # 12 months
    occupancy_forecast = models.JSONField(default=list)     # 12 months %
    competitor_matrix = models.JSONField(default=dict)
    risk_flags = models.JSONField(default=list)

    # H2 — Revenue forecast
    revpar_forecast = models.JSONField(default=list)        # 12 months USD
    monthly_revenue_forecast = models.JSONField(default=list)
    revenue_p50_usd = models.FloatField(default=0.0)
    seasonality_notes = models.TextField(blank=True)

    # H3 — SQB scoring
    sqb_dsc_ratio = models.FloatField(null=True, blank=True)
    sqb_score = models.FloatField(default=0.0)
    sqb_verdict = models.CharField(max_length=100, blank=True)
    sqb_verdict_color = models.CharField(max_length=20, default='gray')
    subsidy_eligible = models.BooleanField(default=False)
    credit_structure_recommendation = models.TextField(blank=True)

    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Mehmonxona tahlil natijasi'


# ══════════════════════════════════════════════════════════════
# 2. CONSTRUCTION
# ══════════════════════════════════════════════════════════════

class ConstructionDetail(models.Model):
    LICENSE_CATEGORY_CHOICES = [
        ('1', "1-toifa (yirik ob'ektlar)"),
        ('2', "2-toifa (o'rta)"),
        ('3', "3-toifa (kichik)"),
        ('none', 'Litsenziya yo\'q'),
    ]

    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='construction_detail'
    )
    construction_type = models.JSONField(default=list, verbose_name='Qurilish turlari')

    # License
    has_license = models.BooleanField(default=False, verbose_name='Qurilish litsenziyasi bor')
    license_category = models.CharField(max_length=10, choices=LICENSE_CATEGORY_CHOICES, default='none')
    months_to_get_license = models.IntegerField(default=3, verbose_name='Litsenziya olishga oy')

    # Equipment
    equipment_owned = models.TextField(blank=True, verbose_name='Mavjud jihozlar')
    equipment_to_buy = models.TextField(blank=True, verbose_name='Sotib olinadigan jihozlar')

    # Project pipeline
    current_contracts = models.TextField(blank=True, verbose_name='Mavjud shartnomalar')
    pipeline_projects = models.TextField(blank=True, verbose_name="Muzokaradagi loyihalar")

    # Critical timeline
    months_to_first_income = models.IntegerField(default=6, verbose_name="Birinchi daromadgacha (oy)")
    expected_first_contract_size_uzs = models.DecimalField(
        max_digits=15, decimal_places=0, default=50_000_000,
        verbose_name="Birinchi kutilayotgan shartnoma (UZS)"
    )
    average_project_duration_months = models.IntegerField(default=6, verbose_name="O'rtacha loyiha muddati (oy)")

    # Workforce
    num_engineers = models.IntegerField(default=2)
    num_workers = models.IntegerField(default=10)
    subcontractor_network = models.BooleanField(default=False, verbose_name="Subpudratchilar tarmog'i")

    # Financials
    average_margin_pct = models.FloatField(default=18.0, verbose_name="O'rtacha foyda marjasi %")
    loan_term_months = models.IntegerField(default=60, verbose_name="Kredit muddati (oy)")
    
    # New bank fields
    project_type = models.CharField(max_length=20, default='private')
    equipment_pct = models.IntegerField(default=50)
    license_valid = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Qurilish tafsilotlari'


class ConstructionAnalysisResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='construction_result'
    )
    # C1 — Cash flow timeline (60 months)
    cash_flow_timeline = models.JSONField(default=list)     # 60 months net
    cumulative_cash_flow = models.JSONField(default=list)   # cumulative
    monthly_loan_payment = models.FloatField(default=0.0)
    breakeven_month = models.IntegerField(null=True, blank=True)

    # Phase risk scores
    faza_1_risk = models.CharField(max_length=20, default='high')  # XAVFLI/O'RTACHA/YAXSHI
    faza_2_risk = models.CharField(max_length=20, default='medium')
    faza_3_risk = models.CharField(max_length=20, default='low')

    # C2 — Market
    market_size_uzs = models.BigIntegerField(default=0)
    tender_opportunity_score = models.FloatField(default=0.0)
    license_risk_flag = models.BooleanField(default=False)
    contract_pipeline_score = models.FloatField(default=0.0)

    # C3 — SQB
    sqb_score = models.FloatField(default=0.0)
    sqb_verdict = models.CharField(max_length=100, blank=True)
    sqb_verdict_color = models.CharField(max_length=20, default='gray')
    garov_value = models.BigIntegerField(default=0)
    kredit_coverage = models.FloatField(default=0.0)
    recommended_grace_months = models.IntegerField(default=6)

    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Qurilish tahlil natijasi'


# ══════════════════════════════════════════════════════════════
# 3. TEXTILE
# ══════════════════════════════════════════════════════════════

class TextileDetail(models.Model):
    UNIT_CHOICES = [('meters', 'Metr'), ('kg', 'Kilogramm'), ('pieces', 'Dona')]

    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='textile_detail'
    )
    textile_type = models.JSONField(default=list, verbose_name='Ishlab chiqarish turi')
    production_capacity_monthly = models.IntegerField(default=1000, verbose_name='Oylik ishlab chiqarish')
    unit_of_measure = models.CharField(max_length=10, choices=UNIT_CHOICES, default='meters')

    # Raw material
    raw_material_source = models.JSONField(default=list)
    raw_material_monthly_uzs = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name='Oylik xomashyo xarajati (UZS)'
    )

    # Markets
    target_market = models.JSONField(default=list, verbose_name='Maqsadli bozorlar')
    export_experience = models.BooleanField(default=False, verbose_name='Eksport tajribasi')
    existing_buyers = models.TextField(blank=True, verbose_name='Mavjud xaridorlar')

    # Certification (crucial for EU market)
    certifications = models.JSONField(default=list, verbose_name='Sertifikatlar')
    months_to_get_cert = models.IntegerField(default=6, verbose_name='Sertifikat olishga (oy)')

    # Equipment
    machinery_list = models.TextField(blank=True)
    machinery_age_years = models.IntegerField(default=5)

    # Workforce
    num_workers_skilled = models.IntegerField(default=10)
    num_workers_unskilled = models.IntegerField(default=20)
    avg_wage_uzs = models.DecimalField(max_digits=10, decimal_places=0, default=3_000_000)

    # Operational
    electricity_monthly = models.DecimalField(max_digits=12, decimal_places=0, default=2_000_000,
                                               verbose_name='Oylik elektr xarajati (UZS)')
    
    # New bank fields
    export_pct = models.IntegerField(default=30)
    market_type = models.CharField(max_length=20, default='domestic')
    cert_type = models.CharField(max_length=20, default='gost')
    factory_sqm = models.IntegerField(default=500)

    class Meta:
        verbose_name = 'Tekstil tafsilotlari'


class TextileAnalysisResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='textile_result'
    )
    # T1 — Web search results
    market_research_data = models.JSONField(default=dict)   # export stats from web
    export_volume_usd = models.BigIntegerField(default=0)
    key_export_markets = models.JSONField(default=list)
    certification_requirements = models.JSONField(default=dict)

    # T2 — Export readiness
    export_readiness_score = models.FloatField(default=0.0)
    certification_score = models.FloatField(default=0.0)
    buyer_network_score = models.FloatField(default=0.0)
    market_access_score = models.FloatField(default=0.0)
    certification_risk_flag = models.BooleanField(default=False)
    readiness_interpretation = models.CharField(max_length=100, blank=True)

    # T3 — SQB
    sqb_score = models.FloatField(default=0.0)
    sqb_verdict = models.CharField(max_length=100, blank=True)
    sqb_verdict_color = models.CharField(max_length=20, default='gray')
    export_contract_bonus = models.BooleanField(default=False)
    free_zone_eligible = models.BooleanField(default=False)

    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Tekstil tahlil natijasi'


# ══════════════════════════════════════════════════════════════
# 4. TRADE / RETAIL
# ══════════════════════════════════════════════════════════════

class TradeDetail(models.Model):
    TRADE_TYPE_CHOICES = [
        ('grocery', "Oziq-ovqat do'koni"),
        ('clothing', 'Kiyim-kechak'),
        ('electronics', 'Elektronika'),
        ('pharmacy', 'Dorixona'),
        ('building_materials', 'Qurilish materiallari'),
        ('wholesale', 'Ulgurji savdo'),
        ('online', "Internet do'kon"),
        ('mixed', 'Aralash savdo'),
    ]
    STORE_FORMAT_CHOICES = [
        ('street_shop', "Ko'cha do'koni"),
        ('mall_shop', "Savdo markazidagi do'kon"),
        ('market_stall', 'Bozor rastasi'),
        ('supermarket', 'Mini-supermarket'),
        ('warehouse_store', "Omborxona-do'kon"),
    ]
    FOOT_TRAFFIC_CHOICES = [
        ('very_high', "Juda yuqori (>500 kishi/kun)"),
        ('high', 'Yuqori (200-500)'),
        ('medium', "O'rtacha (50-200)"),
        ('low', "Past (<50)"),
    ]
    PRICE_STRATEGY_CHOICES = [
        ('budget', 'Arzon narx strategiyasi'),
        ('mid', "O'rta narx"),
        ('premium', 'Premium narx'),
    ]

    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='trade_detail'
    )
    trade_type = models.CharField(max_length=30, choices=TRADE_TYPE_CHOICES, default='grocery')
    store_format = models.CharField(max_length=20, choices=STORE_FORMAT_CHOICES, default='street_shop')

    # Location-specific
    foot_traffic = models.CharField(max_length=20, choices=FOOT_TRAFFIC_CHOICES, default='medium')

    # Inventory & turnover
    avg_monthly_stock_uzs = models.DecimalField(
        max_digits=15, decimal_places=0, default=10_000_000,
        verbose_name='Oylik tovar zaxirasi (UZS)'
    )
    avg_markup_pct = models.FloatField(default=25.0, verbose_name="O'rtacha ustama %")
    inventory_turnover_days = models.IntegerField(default=30, verbose_name='Tovar aylanma (kun)')
    supplier_credit_days = models.IntegerField(default=14, verbose_name='Yetkazib beruvchi muhlati (kun)')

    # Competition
    direct_competitors_300m = models.IntegerField(default=2, verbose_name="300m'da raqobatchilar")
    price_strategy = models.CharField(max_length=10, choices=PRICE_STRATEGY_CHOICES, default='mid')
    
    # New bank fields
    suppliers_count = models.IntegerField(default=3)
    credit_line_needed = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    stock_turnover = models.IntegerField(default=30)

    class Meta:
        verbose_name = 'Savdo tafsilotlari'

    @property
    def working_capital_needed(self):
        return float(self.avg_monthly_stock_uzs) * (self.inventory_turnover_days / 30)

    @property
    def supplier_float(self):
        return float(self.avg_monthly_stock_uzs) * (self.supplier_credit_days / 30)

    @property
    def net_working_capital_gap(self):
        return self.working_capital_needed - self.supplier_float


class TradeAnalysisResult(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='trade_result'
    )
    # S1 — Working capital analysis
    working_capital_needed = models.BigIntegerField(default=0)
    supplier_float = models.BigIntegerField(default=0)
    net_working_capital_gap = models.BigIntegerField(default=0)
    monthly_revenue_estimate = models.BigIntegerField(default=0)
    gross_profit_monthly = models.BigIntegerField(default=0)

    # S2 — Location scoring
    location_foot_traffic_score = models.FloatField(default=0.0)
    anchor_effect_score = models.FloatField(default=0.0)
    competitor_density_score = models.FloatField(default=0.0)
    overall_location_score = models.FloatField(default=0.0)

    # S3 — SQB
    sqb_score = models.FloatField(default=0.0)
    sqb_verdict = models.CharField(max_length=100, blank=True)
    sqb_verdict_color = models.CharField(max_length=20, default='gray')
    recommended_loan_type = models.CharField(max_length=100, blank=True)
    recommended_term_months = models.IntegerField(default=24)

    ai_commentary = models.TextField(blank=True)
    raw_data = models.JSONField(default=dict)
    is_mock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Savdo tahlil natijasi'


# ══════════════════════════════════════════════════════════════
# 5. SERVICES / SERVICE SECTOR
# ══════════════════════════════════════════════════════════════

class ServiceDetail(models.Model):
    request = models.OneToOneField(
        BusinessAnalysisRequest, on_delete=models.CASCADE, related_name='service_detail'
    )
    provider_type = models.CharField(max_length=50, default='individual')
    equipment_uzs = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    repeat_pct = models.IntegerField(default=40)
    service_avg_price = models.DecimalField(max_digits=15, decimal_places=0, default=150000)

    class Meta:
        verbose_name = 'Xizmat tafsilotlari'
