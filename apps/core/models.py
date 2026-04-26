from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [('CLIENT', 'Mijoz'), ('OFFICER', 'Bank Xodimi'), ('ADMIN', 'Administrator')]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT')
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_officer(self):
        return self.role in ('OFFICER', 'ADMIN')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


class Zalog(models.Model):
    zalog_id = models.CharField(max_length=50, unique=True, verbose_name="Zalog ID")
    first_name = models.CharField(max_length=100, verbose_name="Ism")
    last_name = models.CharField(max_length=100, verbose_name="Familiya")
    property_type = models.CharField(max_length=50, verbose_name="Mulk turi")
    total_value = models.DecimalField(max_digits=15, decimal_places=0, verbose_name="Umumiy qiymat (UZS)")

    class Meta:
        verbose_name = "Garov (Zalog)"
        verbose_name_plural = "Garovlar (Zaloglar)"

    def __str__(self):
        return f"{self.zalog_id} - {self.first_name} {self.last_name} ({self.total_value} UZS)"


class BusinessAnalysisRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Kutilmoqda'),
        ('processing', 'Jarayonda'),
        ('done', 'Tayyor'),
        ('failed', 'Xato'),
    ]
    RECOMMENDATION_CHOICES = [
        ('YES', 'HA'),
        ('NO', "YO'Q"),
        ('CAUTION', 'EHTIYOT'),
    ]
    MCC_CHOICES = [
        # Mehmonxona / Turizm
        ('7011', 'Mehmonxona / Hotel'),
        ('7012', 'Apart-hotel / Vaqtinchalik yashash'),
        ('4722', 'Sayohat agentligi / Tur operator'),
        ('7991', 'Dam olish maskani / Attraktsion'),
        ('5812', 'Restoran / Kafe'),
        # Qurilish
        ('5251', "Qurilish mollari do'koni"),
        ('5065', 'Elektr materiallari va jihozlar'),
        ('5039', "Qurilish xom-ashyo (yog'och, qum, tsement)"),
        ('7389', "Qurilish pudrat va ta'mirlash xizmati"),
        # Tekstil
        ('5661', "Kiyim-kechak do'koni / Chakana"),
        ('5131', "To'qimachilik va mato — ulgurji"),
        ('5137', 'Forma va maxsus kiyimlar'),
        ('5699', 'Kiyim-kechak (boshqa)'),
        # Savdo / Chakana
        ('5411', "Oziq-ovqat do'koni / Supermarket"),
        ('5912', 'Dorixona / Apteka'),
        ('5200', "Uy jihozlari / Mebel do'koni"),
        ('5310', "Chegirmali / Universal do'kon"),
        ('5945', "O'yinchoq / Hobby do'koni"),
        # Xizmat ko'rsatish
        ('7299', "Maishiy xizmatlar (go'zallik, sartaroshxona)"),
        ('8099', 'Tibbiy va sog\'liqni saqlash xizmatlari'),
        ('8011', 'Shifokorlar / Klinikalar'),
        ('7372', 'IT va dasturiy ta\'minot xizmatlari'),
        ('8049', 'Stomatologiya va tibbiy mutaxassis'),
        # Boshqa
        ('5999', 'Boshqa chakana savdo / Umumiy'),
    ]
    DISTRICT_CHOICES = [
        ('Yunusobod', 'Yunusobod tumani'),
        ('Chilonzor', 'Chilonzor tumani'),
        ('Mirzo Ulugbek', "Mirzo Ulug'bek tumani"),
        ('Shayxontohur', 'Shayxontohur tumani'),
        ('Olmazor', 'Olmazor tumani'),
        ('Mirobod', 'Mirobod tumani'),
        ('Yakkasaroy', 'Yakkasaroy tumani'),
        ('Bektemir', 'Bektemir tumani'),
        ('Sergeli', 'Sergeli tumani'),
        ('Uchtepa', 'Uchtepa tumani'),
        ('Yashnobod', 'Yashnobod tumani'),
        ('Zangiota', 'Zangiota tumani'),
    ]
    CATEGORY_CHOICES = [
        ('food_beverage', 'Ovqat va ichimlik'),
        ('retail', 'Chakana savdo'),
        ('health_beauty', "Sog'liq va go'zallik"),
        ('education', "Ta'lim"),
        ('services', 'Xizmatlar'),
        ('entertainment', "Ko'ngil ochar"),
        ('tech', 'Texnologiya'),
        ('other', 'Boshqa'),
    ]
    TARGET_CUSTOMER_CHOICES = [
        # Umumiy / Savdo
        ('all', 'Barcha (Keng ommaga)'),
        ('families', 'Oilalar'),
        ('students', 'Talabalar / Yoshlar'),
        ('office_workers', 'Ofis xodimlari'),
        ('local_residents', 'Mahalliy aholi (Yaqin atrofdagilar)'),
        ('professionals', 'Mutaxassislar / Professionallar'),
        ('busy_households', "Band oilalar va uy xo'jaliklari"),
        ('small_businesses', 'Kichik biznes egalari'),
        
        # Mehmonxona / Turizm
        ('foreign_tourists', 'Xorijiy sayyohlar'),
        ('local_tourists', 'Mahalliy sayyohlar'),
        ('business_travelers', 'Biznes sayohatdagilar'),
        ('pilgrims', 'Ziyoratchilar'),
        
        # Qurilish / B2B
        ('b2b_companies', 'B2B (Tadbirkorlar va Kompaniyalar)'),
        ('gov_contracts', 'Davlat tashkilotlari (Tenderlar)'),
        ('individuals', 'Jismoniy shaxslar (Aholi)'),
        
        # Tekstil / Ulgurji savdo
        ('wholesale_buyers', 'Ulgurji xaridorlar (Optom)'),
        ('retail_shops', 'Chakana savdo do\'konlari'),
        ('foreign_importers', 'Xorijiy importyorlar (Eksport)'),
    ]
    LOCATION_TYPE_CHOICES = [
        ('street_front', "Ko'cha bo'yi"),
        ('mall', 'Savdo markazi ichida'),
        ('market', 'Bozor ichida'),
        ('residential', 'Turar-joy massivi'),
        ('business_center', 'Biznes markaz'),
        ('standalone', 'Alohida bino'),
    ]
    FOOT_TRAFFIC_CHOICES = [
        ('very_high', ">500 kishi/kun"),
        ('high', '200-500'),
        ('medium', '50-200'),
        ('low', "<50"),
    ]
    WORKING_DAYS_CHOICES = [(5, '5 kun'), (6, '6 kun'), (7, '7 kun')]

    CATEGORY_TYPE_CHOICES = [
        ('hotel',        'Mehmonxona'),
        ('tourism',      'Turizm'),
        ('construction', 'Qurilish'),
        ('textile',      'Tekstil sanoati'),
        ('trade',        'Savdo & Chakana'),
        ('services',     "Xizmat ko'rsatish"),
    ]

    CREDIT_PRODUCT_CHOICES = [
        ('business_welcome', "SQB Business Welcome (Onlayn kredit, 500 mln gacha)"),
        ('ishonch', "Ishonch krediti (Aylanma mablag', 28 mlrd gacha)"),
        ('investment', "Investitsion loyihalar (Asosiy vositalar, 28 mlrd gacha)"),
        ('refinance', "Refinans krediti (Boshqa bankdan qayta moliyalash, 2 mlrd gacha)"),
    ]

    # ── Core ──────────────────────────────────────────────────
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    business_category_type = models.CharField(
        max_length=20, choices=CATEGORY_TYPE_CHOICES, default='hotel',
        verbose_name='Biznes kategoriyasi turi'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # ── SQB Credit Scoring outputs ─────────────────────────────
    sqb_composite_score = models.FloatField(null=True, blank=True)
    sqb_recommendation = models.CharField(max_length=100, blank=True)
    sqb_recommendation_color = models.CharField(max_length=20, blank=True, default='gray')
    sqb_dsc_ratio = models.FloatField(null=True, blank=True)
    sqb_collateral_coverage = models.FloatField(null=True, blank=True)
    sqb_debt_burden_pct = models.FloatField(null=True, blank=True)
    sqb_commentary = models.TextField(blank=True)
    progress_pct = models.IntegerField(default=0)
    completed_blocks = models.JSONField(default=list)
    warning_flag = models.BooleanField(default=False)
    warning_message = models.TextField(blank=True)
    is_notified = models.BooleanField(default=False, verbose_name="Foydalanuvchiga xabar berilganmi")
    final_recommendation = models.CharField(
        max_length=10, choices=RECOMMENDATION_CHOICES, null=True, blank=True
    )
    final_score = models.FloatField(null=True, blank=True)
    final_commentary = models.TextField(blank=True)
    external_checks = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Tashqi manbalar bo'yicha tekshiruvlar",
    )
    external_checks_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Tashqi tekshiruv yangilangan vaqti",
    )
    credit_tier = models.CharField(max_length=30, blank=True)
    celery_task_id = models.CharField(max_length=255, blank=True)
    extra_costs_json = models.JSONField(
        blank=True, default=list,
        verbose_name="Qo'shimcha xarajatlar (JSON)",
    )
    form_data_json = models.JSONField(
        blank=True, default=dict,
        verbose_name="Saqlangan forma ma'lumotlari",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── STEP 1: Business Description & Identity ───────────────
    business_description = models.TextField(
        blank=True,
        verbose_name="Biznes tavsifi",
        help_text=(
            "Biznes rejangiz haqida erkin yozing. "
            "Gemini bu matnni barcha bloklarga kontekst sifatida uzatadi."
        ),
    )
    business_name = models.CharField(max_length=255, verbose_name="Biznes nomi", blank=True, null=True)
    business_type = models.CharField(max_length=150, verbose_name='Biznes turi')
    mcc_code = models.CharField(max_length=10, choices=MCC_CHOICES, verbose_name='MCC Kategoriya')
    business_category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, default='other',
        verbose_name='Biznes kategoriyasi'
    )
    target_customer = models.JSONField(
        default=list,
        verbose_name="Maqsadli mijoz"
    )

    # ── STEP 2: Demand & Schedule ─────────────────────────────
    planned_opening_date = models.DateField(
        null=True, blank=True, verbose_name="Ochilish sanasi"
    )
    is_24_7 = models.BooleanField(
        default=False, verbose_name="24/7 ishlaydi"
    )
    operating_hours_start = models.TimeField(
        null=True, blank=True, default='09:00', verbose_name="Ish boshlanish vaqti"
    )
    operating_hours_end = models.TimeField(
        null=True, blank=True, default='21:00', verbose_name="Ish tugash vaqti"
    )
    working_days_per_week = models.IntegerField(
        default=7, choices=WORKING_DAYS_CHOICES,
        verbose_name="Haftalik ish kunlari"
    )
    expected_daily_customers = models.IntegerField(
        default=50, verbose_name="Kunlik kutilgan mijozlar soni"
    )
    average_check_uzs = models.DecimalField(
        max_digits=12, decimal_places=0, default=50000,
        verbose_name="O'rtacha chek (UZS)"
    )
    has_seasonal_dependency = models.BooleanField(
        default=False, verbose_name="Mavsumiylik bor"
    )
    seasonal_notes = models.TextField(
        blank=True, verbose_name="Mavsumiylik izohi"
    )

    # ── STEP 3: Location & Premises ───────────────────────────
    latitude = models.FloatField(default=41.2995, verbose_name='Kenglik')
    longitude = models.FloatField(default=69.2401, verbose_name='Uzunlik')
    district = models.CharField(
        max_length=100, choices=DISTRICT_CHOICES, verbose_name='Tuman'
    )
    address_hint = models.CharField(
        max_length=255, blank=True, verbose_name='Manzil izohi'
    )
    address_detail = models.CharField(
        max_length=255, blank=True,
        verbose_name="Batafsil manzil",
        help_text="Ko'cha, bino, mo'ljal"
    )
    location_type = models.CharField(
        max_length=50, choices=LOCATION_TYPE_CHOICES,
        default='street_front', verbose_name="Lokatsiya turi"
    )
    foot_traffic = models.CharField(
        max_length=20, choices=FOOT_TRAFFIC_CHOICES,
        default='medium', verbose_name="Kunlik piyoda o'tuvchilar"
    )
    floor_area_sqm = models.FloatField(
        default=50.0, verbose_name="Maydon (kv.m)"
    )
    nearby_landmarks = models.TextField(
        blank=True, verbose_name="Yaqin mo'ljallar"
    )
    parking_available = models.BooleanField(
        default=False, verbose_name="Avtoturargoh mavjud"
    )
    public_transport_nearby = models.BooleanField(
        default=True, verbose_name="Jamoat transporti yaqin"
    )

    # ── STEP 4: Financial ─────────────────────────────────────
    sqb_credit_product = models.CharField(
        max_length=50, choices=CREDIT_PRODUCT_CHOICES,
        default='ishonch', verbose_name="SQB Kredit Maxsuloti"
    )
    investment_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=50_000_000,
        verbose_name="Jami investitsiya (so'm)"
    )
    target_monthly_revenue = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name="Kutilayotgan oylik daromad (UZS)"
    )
    own_capital = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name="Shaxsiy kapital (UZS)"
    )
    loan_amount = models.DecimalField(
        max_digits=15, decimal_places=0, default=0,
        verbose_name="Kredit miqdori (UZS)"
    )
    monthly_rent_uzs = models.DecimalField(
        max_digits=12, decimal_places=0, default=3_000_000,
        verbose_name="Oylik ijara (UZS)"
    )
    monthly_salary_budget = models.DecimalField(
        max_digits=12, decimal_places=0, default=5_000_000,
        verbose_name="Oylik ish haqi fondi (UZS)"
    )
    num_employees = models.IntegerField(
        default=3, verbose_name="Xodimlar soni"
    )
    monthly_utilities = models.DecimalField(
        max_digits=12, decimal_places=0, default=500_000,
        verbose_name="Kommunal xarajatlar (UZS/oy)"
    )
    monthly_fixed_costs = models.DecimalField(
        max_digits=15, decimal_places=2, default=0,
        verbose_name="Oylik doimiy xarajatlar (jami)"
    )
    variable_cost_pct = models.FloatField(
        default=35.0, verbose_name="O'zgaruvchi xarajatlar %"
    )
    planned_markup_pct = models.FloatField(
        default=40.0, verbose_name="Belgilangan ustama %"
    )
    cogs_percentage = models.FloatField(default=35.0, verbose_name="Tovar tannarxi %")
    desired_payback_months = models.IntegerField(default=24, verbose_name="Qaytarish muddati")
    known_competitors = models.TextField(blank=True, verbose_name="Ma'lum raqobatchilar")
    competitor_advantage = models.TextField(blank=True, verbose_name="Raqobat ustunligi")
    
    # Zalog
    zalog_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="Zalog ID")

    # ── STEP 5: Experience & Risks ────────────────────────
    market_experience_years = models.IntegerField(
        default=0, verbose_name="Soha tajribasi (yil)"
    )
    previously_failed_business = models.BooleanField(
        default=False, verbose_name="Oldingi muvaffaqiyatsiz urinish"
    )

    # ── AI Output fields ──

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Tahlil so'rovi"
        verbose_name_plural = "Tahlil so'rovlari"

    def __str__(self):
        return f"{self.business_type} — {self.district} ({self.created_at.strftime('%d.%m.%Y')})"

    def get_recommendation_display_uz(self):
        mapping = {'YES': 'HA', 'NO': "YO'Q", 'CAUTION': 'EHTIYOT'}
        return mapping.get(self.final_recommendation, '—')

    def get_recommendation_color(self):
        mapping = {'YES': 'success', 'NO': 'danger', 'CAUTION': 'warning'}
        return mapping.get(self.final_recommendation, 'secondary')

    @property
    def computed_monthly_fixed_costs(self):
        """Sum of all monthly fixed cost components."""
        return (
            float(self.monthly_rent_uzs or 0) +
            float(self.monthly_salary_budget or 0) +
            float(self.monthly_utilities or 0)
        )

class SystemConfiguration(models.Model):
    """
    Singleton model to hold system-wide configurations, such as the active AI provider.
    """
    PROVIDER_CHOICES = [
        ('gemini', 'Google Gemini'),
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('huggingface', 'HuggingFace'),
        ('mock', 'Mock (Testing)'),
    ]

    active_ai_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='gemini',
        verbose_name="Faol AI Provayderi"
    )
    
    gemini_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Gemini API Key")
    openai_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="OpenAI API Key")
    anthropic_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Anthropic API Key")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tizim Sozlamalari"
        verbose_name_plural = "Tizim Sozlamalari"

    def save(self, *args, **kwargs):
        if not self.pk and SystemConfiguration.objects.exists():
            return SystemConfiguration.objects.first()
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return "Asosiy Tizim Sozlamalari"
