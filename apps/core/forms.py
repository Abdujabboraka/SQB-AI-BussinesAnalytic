"""
BiznesAI — Analysis Forms (4-step wizard).
Each step is a separate ModelForm; all submitted in a single POST.
"""
from django import forms
from .models import BusinessAnalysisRequest


# ─────────────────────────────────────────────────────────────
# Step 1 — Business Description & Identity
# ─────────────────────────────────────────────────────────────

class Step1Form(forms.ModelForm):
    target_customer = forms.MultipleChoiceField(
        choices=BusinessAnalysisRequest.TARGET_CUSTOMER_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'tomselect-multi',
            'placeholder': 'Mijoz turlarini tanlang…',
            'title': "Bir nechtasini tanlash mumkin",
        }),
        label='Maqsadli mijozlar'
    )
    zalog_id = forms.CharField(
        required=False,
        max_length=50,
        label='Zalog ID',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'id': 'id_zalog_id',
            'placeholder': 'Masalan: ZAL-12345 (ixtiyoriy)',
            'title': 'Garov (zalog) identifikatori',
        }),
    )

    class Meta:
        model = BusinessAnalysisRequest
        # NOTE: `business_category` was dropped from the wizard — `business_category_type`
        # (top-level radio cards) + `mcc_code` (bank Soha) cover the same ground.
        # The model field stays for backward compat with existing rows.
        fields = [
            'business_category_type',
            'business_name',
            'business_description',
            'business_type',
            'mcc_code',
            'target_customer',
            'zalog_id',
        ]
        widgets = {
            'business_category_type': forms.RadioSelect(attrs={
                'class': 'category-type-radio',
            }),
            'business_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 7,
                'id': 'id_business_description',
                'title': "Biznesingizni o'z so'zlaringiz bilan tasvirlang",
                'placeholder': (
                    "Nima qilmoqchisiz, kim uchun, nimasi bilan ajralib turadi?\n"
                    "Masalan: Yunusobod metro yonida 6 stolli osh markazi, "
                    "talabalar va ofis xodimlari uchun, lunch-set 25k so'm…"
                ),
            }),
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'title': "Biznesingiz nomi",
                'placeholder': "Masalan: 'Osh Markazi' yoki 'Yulduz Kafe'",
            }),
            'business_type': forms.TextInput(attrs={
                'class': 'form-control',
                'title': "Qanday faoliyat?",
                'placeholder': "Kafe, Apteka, Kiyim do'koni…",
            }),
            'mcc_code': forms.Select(attrs={
                'class': 'form-select',
                'title': "Bank uchun MCC kodi"
            }),
        }
        labels = {
            'business_name': 'Biznes nomi',
            'business_description': 'Biznes tavsifi',
            'business_type': 'Biznes turi',
            'mcc_code': 'Soha (MCC)',
            'target_customer': 'Maqsadli mijozlar',
            'zalog_id': 'Zalog ID',
        }


# ─────────────────────────────────────────────────────────────
# Step 2 — Demand & Schedule
# ─────────────────────────────────────────────────────────────

class Step2Form(forms.ModelForm):
    class Meta:
        model = BusinessAnalysisRequest
        fields = [
            'planned_opening_date',
            'is_24_7',
            'operating_hours_start',
            'operating_hours_end',
            'working_days_per_week',
            'expected_daily_customers',
            'average_check_uzs',
            'has_seasonal_dependency',
            'seasonal_notes',
        ]
        widgets = {
            'planned_opening_date': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
                'title': 'Biznes faoliyatini boshlashi kutilayotgan sana.',
            }),
            'is_24_7': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'id_is_24_7',
                'title': 'Biznes sutka davomida, 24/7 rejimida ishlasa belgilang.',
            }),
            'operating_hours_start': forms.TimeInput(attrs={
                'class': 'form-control', 'type': 'time', 'id': 'id_op_start',
                'title': 'Ochilish vaqti.',
            }),
            'operating_hours_end': forms.TimeInput(attrs={
                'class': 'form-control', 'type': 'time', 'id': 'id_op_end',
                'title': 'Yopilish vaqti.',
            }),
            'working_days_per_week': forms.Select(attrs={
                'class': 'form-select',
                'title': 'Haftasiga necha kun ishlaysiz?',
            }),
            'expected_daily_customers': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'placeholder': '50',
                'title': "Kunlik mijoz soni",
            }),
            'average_check_uzs': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1000', 'placeholder': '50 000',
                'title': "Bir mijoz o'rtacha qancha xarajat qiladi (so'm)",
            }),
            'has_seasonal_dependency': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': 'Mavsumga qarab daromad o\'zgaradimi?',
            }),
            'seasonal_notes': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'title': 'Qaysi oylarda nima o\'zgaradi?',
                'placeholder': "Ramazon +30%, yozda terrasa…",
            }),
        }
        labels = {
            'planned_opening_date': 'Ochilish sanasi',
            'is_24_7': '24/7 (Sutka davomida)',
            'operating_hours_start': 'Ish boshlanadi',
            'operating_hours_end': 'Ish tugaydi',
            'working_days_per_week': 'Haftalik ish kunlari',
            'expected_daily_customers': 'Kunlik kutilgan mijozlar soni',
            'average_check_uzs': "O'rtacha chek (UZS)",
            'has_seasonal_dependency': 'Mavsumiylik ta\'siri bor',
            'seasonal_notes': 'Mavsumiylik izohi (ixtiyoriy)',
        }


# ─────────────────────────────────────────────────────────────
# Step 3 — Location & Premises
# ─────────────────────────────────────────────────────────────

class Step3Form(forms.ModelForm):
    latitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    longitude = forms.FloatField(required=False, widget=forms.HiddenInput())
    district = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = BusinessAnalysisRequest
        fields = [
            'district',
            'address_detail',
            'location_type',
            'foot_traffic',
            'floor_area_sqm',
            'nearby_landmarks',
            'parking_available',
            'public_transport_nearby',
            'latitude',
            'longitude',
        ]
        widgets = {
            'district': forms.Select(attrs={
                'class': 'form-select',
                'title': "Xaritadan tanlangan joy bo'yicha avtomatik to'ldiriladi",
            }),
            'address_detail': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Ko'cha, bino, mo'ljal",
                'title': "Aniq manzil yoki mo'ljal nomini kiriting",
            }),
            'location_type': forms.Select(attrs={
                'class': 'form-select',
                'title': "Lokatsiya turini tanlang",
            }),
            'foot_traffic': forms.Select(attrs={
                'class': 'form-select',
                'title': "Kunlik taxminiy o'tuvchilar oqimi",
            }),
            'floor_area_sqm': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '5', 'step': '5', 'placeholder': '50',
                'title': "Ijaraga olinadigan maydon (kv.m)",
            }),
            'nearby_landmarks': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': "Metro Yunusobod, Hamza bozori…"
            }),
            'parking_available': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': "Mijozlar uchun parking mavjud bo'lsa belgilang",
            }),
            'public_transport_nearby': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'title': "Jamoat transporti bekatlari yaqin bo'lsa belgilang",
            }),
        }
        labels = {
            'district': 'Toshkent tumani',
            'address_detail': "Batafsil manzil",
            'location_type': 'Lokatsiya turi',
            'foot_traffic': "Kunlik piyoda o'tuvchilar",
            'floor_area_sqm': 'Ijara maydoni (kv.m)',
            'nearby_landmarks': "Yaqin mo'ljallar",
            'parking_available': 'Avtoturargoh mavjud',
            'public_transport_nearby': 'Jamoat transporti yaqin',
        }


# ─────────────────────────────────────────────────────────────
# Step 4 — Financial & Competition
# ─────────────────────────────────────────────────────────────

class Step4Form(forms.ModelForm):
    monthly_marketing_uzs = forms.DecimalField(
        required=False, min_value=0, initial=0, label='Oylik marketing va reklama',
        widget=forms.NumberInput(attrs={'class': 'form-control extra-cost', 'min': '0', 'placeholder': '0'})
    )
    monthly_logistics_uzs = forms.DecimalField(
        required=False, min_value=0, initial=0, label='Oylik logistika / yetkazib berish',
        widget=forms.NumberInput(attrs={'class': 'form-control extra-cost', 'min': '0', 'placeholder': '0'})
    )
    monthly_maintenance_uzs = forms.DecimalField(
        required=False, min_value=0, initial=0, label="Uskuna va ta'mirlash xarajati",
        widget=forms.NumberInput(attrs={'class': 'form-control extra-cost', 'min': '0', 'placeholder': '0'})
    )
    monthly_software_uzs = forms.DecimalField(
        required=False, min_value=0, initial=0, label='Kassa, litsenziya va dasturlar',
        widget=forms.NumberInput(attrs={'class': 'form-control extra-cost', 'min': '0', 'placeholder': '0'})
    )
    monthly_security_uzs = forms.DecimalField(
        required=False, min_value=0, initial=0, label="Qo'riqlash / sanitariya / servis",
        widget=forms.NumberInput(attrs={'class': 'form-control extra-cost', 'min': '0', 'placeholder': '0'})
    )
    monthly_other_costs_uzs = forms.DecimalField(
        required=False, min_value=0, initial=0, label='Boshqa doimiy xarajatlar',
        widget=forms.NumberInput(attrs={'class': 'form-control extra-cost', 'min': '0', 'placeholder': '0'})
    )

    # Hidden JSON field to hold dynamically-added extra cost rows
    extra_costs_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_extra_costs_json'}),
    )

    class Meta:
        model = BusinessAnalysisRequest
        fields = [
            'sqb_credit_product',
            'investment_amount',
            'target_monthly_revenue',
            'loan_amount',
            'monthly_rent_uzs',
            'monthly_salary_budget',
            'num_employees',
            'monthly_utilities',
            'monthly_marketing_uzs',
            'monthly_logistics_uzs',
            'monthly_maintenance_uzs',
            'monthly_software_uzs',
            'monthly_security_uzs',
            'monthly_other_costs_uzs',
            'cogs_percentage',
            'desired_payback_months',
            'known_competitors',
            'competitor_advantage',
            'zalog_id',
        ]
        widgets = {
            'sqb_credit_product': forms.Select(attrs={
                'class': 'form-select',
                'title': "SQB bankining biznes uchun ajratilgan maxsus kredit turlari",
            }),
            'investment_amount': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1000000', 'placeholder': '50 000 000',
                'title': "Loyihani ochish uchun kerakli jami sarmoya (UZS). Kredit + o'z mablag'ingiz yig'indisi.",
            }),
            'target_monthly_revenue': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'placeholder': '30 000 000',
                'title': "Siz kutilayotgan oylik sof tushum (oborot). AI buni bozor realiyalari bilan solishtiradi.",
            }),
            'loan_amount': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'placeholder': '20 000 000',
                'title': "SQB bankdan so'ralayotgan kredit miqdori (UZS). Jami sarmoyadan oshmasligi kerak.",
            }),
            'monthly_rent_uzs': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'placeholder': '3 000 000',
                'title': "Ijaraga to'lanadigan oylik to'lov (UZS). Kommunal xarajatlar alohida ko'rsatiladi.",
            }),
            'monthly_salary_budget': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'placeholder': '5 000 000',
                'title': "Barcha xodimlar uchun oylik ish haqi fondi jami (UZS). Soliqlar va MHBF shu summaga kiritilgan.",
            }),
            'num_employees': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'placeholder': '3',
                'title': "Doimiy xodimlar soni. Qisman bandlar 0.5 sifatida hisoblanadi.",
            }),
            'monthly_utilities': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'placeholder': '500 000',
                'title': "Elektr, gaz, suv — oylik kommunal xarajatlar jami (UZS).",
            }),
            'cogs_percentage': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'max': '99', 'step': '0.5', 'placeholder': '35',
                'title': "Tovar yoki xizmat tannarxi ulushi (%)",
            }),
            'desired_payback_months': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'max': '60', 'placeholder': '24',
                'title': "Investitsiyani to'liq qaytarish uchun kutilgan muddat (oylar). CBU standarti: 60 oygacha.",
            }),
            'known_competitors': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': "Dono Cafe — 100m, Yana 1 kafe — 200m",
                'title': "Yaqin atrofdagi ma'lum raqobatchilar. Xaritadan joy tanlanganda avtomatik to'ldiriladi.",
            }),
            'competitor_advantage': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 2,
                'placeholder': "Arzonroq narx, sifatli, 24/7…",
                'title': "Raqobatchilardan ustun tomonlaringiz — narx, sifat, xizmat tezligi, joy, brendlash.",
            }),
            'zalog_id': forms.TextInput(attrs={
                'class': 'form-control', 'id': 'id_zalog_id', 'placeholder': 'ZAL-123456',
                'title': "Garov (zalog) obyekti ID raqami. Mavjud bo'lmasa bo'sh qoldiring.",
            }),
        }
        labels = {
            'sqb_credit_product': "SQB Kredit Maxsuloti",
            'investment_amount': "Loyihaga kerakli jami mablag' (UZS)",
            'loan_amount': "So'ralayotgan kredit miqdori (UZS)",
            'monthly_rent_uzs': 'Oylik ijara (UZS)',
            'monthly_salary_budget': 'Oylik ish haqi fondi (UZS)',
            'num_employees': 'Xodimlar soni',
            'monthly_utilities': 'Kommunal xarajatlar (UZS/oy)',
            'cogs_percentage': 'Tovar tannarxi (%)',
            'desired_payback_months': "Investitsiyani qaytarish muddati (oy)",
            'known_competitors': "Ma'lum raqobatchilar (ixtiyoriy)",
            'competitor_advantage': 'Raqobat ustunligingiz (ixtiyoriy)',
            'zalog_id': "Zalog ID (ixtiyoriy)",
        }


# ─────────────────────────────────────────────────────────────
# Registration Form (unchanged)
# ─────────────────────────────────────────────────────────────

class UserRegisterForm(forms.Form):
    first_name = forms.CharField(
        max_length=50, label='Ism',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ismingiz'})
    )
    last_name = forms.CharField(
        max_length=50, label='Familiya',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Familiyangiz'})
    )
    username = forms.CharField(
        max_length=30, label='Login',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'login_name'})
    )
    password1 = forms.CharField(
        label='Parol', min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )
    password2 = forms.CharField(
        label='Parolni tasdiqlang',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'})
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise forms.ValidationError("Parollar mos kelmaydi.")
        return cleaned


# ─────────────────────────────────────────────────────────────
# Category-Specific Detail Forms
# Submitted with the main wizard; saved to *Detail models
# ─────────────────────────────────────────────────────────────

class HotelDetailForm(forms.Form):
    hotel_name = forms.CharField(
        max_length=200, required=False, label='Mehmonxona nomi',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Registon Boutique Hotel',
            'title': "Mehmonxona brendi yoki nomi",
        })
    )
    hotel_category = forms.ChoiceField(
        choices=[
            ('1_star','1 yulduz'), ('2_star','2 yulduz'), ('3_star','3 yulduz'),
            ('4_star','4 yulduz'), ('5_star','5 yulduz'), ('boutique','Butik'),
            ('hostel','Hostel'), ('apart_hotel','Apart-hotel'), ('eco_lodge','Eko-turar joy'),
        ],
        label='Mehmonxona toifasi',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'title': "Yulduz darajasi yoki formatni tanlang",
        })
    )
    total_rooms = forms.IntegerField(
        min_value=1, initial=20, label='Xonalar soni',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '20',
            'title': "Umumiy sotiladigan xonalar soni",
        })
    )
    city = forms.ChoiceField(
        choices=[('tashkent','Toshkent'), ('samarkand','Samarqand'), ('bukhara','Buxoro'),
                 ('khiva','Xiva'), ('namangan','Namangan'), ('andijan','Andijon'), ('other','Boshqa')],
        label='Shahar', widget=forms.Select(attrs={
            'class': 'form-select',
            'title': "Mehmonxona joylashgan shahar",
        })
    )

    room_rate_low_usd = forms.DecimalField(
        min_value=1, initial=40, label='Quyi sezon narxi (USD/kecha)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '40',
            'title': "Past sezon uchun bazaviy tarif",
        })
    )
    room_rate_high_usd = forms.DecimalField(
        min_value=1, initial=80, label='Yuqori sezon narxi (USD/kecha)',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '80',
            'title': "Yuqori sezon uchun bazaviy tarif",
        })
    )
    tariff_system = forms.ChoiceField(
        choices=[
            ('seasonal', 'Mavsumiy tarif'),
            ('fixed', 'Yagona tarif'),
            ('segmented', "Segment bo'yicha tarif"),
        ],
        initial='seasonal',
        label='Tarif tizimi',
        widget=forms.Select(attrs={
            'class': 'form-select',
            'title': "Narx siyosatini tanlang",
        })
    )
    extra_tariff_label = forms.CharField(
        max_length=120,
        required=False,
        label="Qo'shimcha tarif nomi",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Masalan: Airport transfer',
            'title': "Qo'shimcha xizmat nomi",
        })
    )
    extra_tariff_value_usd = forms.DecimalField(
        required=False,
        min_value=0,
        initial=0,
        label="Qo'shimcha tarif qiymati (USD)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '1',
            'placeholder': '15',
            'title': "Qo'shimcha xizmat narxi (USD)",
        })
    )
    target_occupancy_pct = forms.FloatField(
        min_value=10, max_value=100, initial=65.0, label="Maqsad to'liqlik %",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '5',
            'placeholder': '65',
            'title': "Yillik o'rtacha bandlik maqsadi (%)",
        })
    )
    applying_for_subsidy = forms.BooleanField(required=False, label='VM 550/2024 subsidiyasi',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'title': "Subsidiya dasturi bo'yicha ariza topshirilgan bo'lsa belgilang",
        }))
    franchise_agreement = forms.BooleanField(required=False, label='Xalqaro brend franchayzi',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'title': "Xalqaro brend bilan hamkorlik shartnomasi bo'lsa belgilang",
        }))
    
    # Bank-specific fields
    booking_profile = forms.ChoiceField(
        choices=[('yes','Ha, mavjud'), ('planned','Reja bor'), ('no','Yo\'q')],
        required=False, label='Booking/Airbnb profili'
    )
    advance_booking_pct = forms.IntegerField(min_value=0, max_value=100, initial=30, required=False)
    collateral_type = forms.ChoiceField(
        choices=[('property','Ko\'chmas mulk'), ('equipment','Jihozlar'), ('guarantee','Kafillik'), ('mixed','Aralash')],
        required=False, label='Garov turi'
    )


class ConstructionDetailForm(forms.Form):
    has_license = forms.BooleanField(required=False, label='Qurilish litsenziyasi mavjud',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'title': "Amaldagi litsenziya bo'lsa belgilang",
        }))
    license_category = forms.ChoiceField(
        choices=[('1',"1-toifa"), ('2',"2-toifa"), ('3',"3-toifa"), ('none',"Yo'q")],
        label='Litsenziya toifasi', widget=forms.Select(attrs={'class': 'form-select'})
    )
    months_to_get_license = forms.IntegerField(
        min_value=0, initial=3, label='Litsenziya olishga (oy)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '3'})
    )
    months_to_first_income = forms.IntegerField(
        min_value=1, initial=6, label='Birinchi daromadgacha (oy)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '6'})
    )
    expected_first_contract_size_uzs = forms.DecimalField(
        min_value=0, initial=50_000_000, label='Birinchi shartnoma hajmi (UZS)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '50000000'})
    )
    average_project_duration_months = forms.IntegerField(
        min_value=1, initial=6, label="O'rtacha loyiha muddati (oy)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '6'})
    )
    num_engineers = forms.IntegerField(min_value=0, initial=2, label='Muhandislar soni',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '2'}))
    num_workers = forms.IntegerField(min_value=0, initial=10, label='Ishchilar soni',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '10'}))
    average_margin_pct = forms.FloatField(
        min_value=1, max_value=99, initial=18.0, label="O'rtacha foyda marjasi %",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'placeholder': '18'})
    )
    current_contracts = forms.CharField(required=False, label='Mavjud shartnomalar',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
            'placeholder': 'Yangiobod MFY renovatsiya — 200 mln so\'m, 3 oy...'}))
    subcontractor_network = forms.BooleanField(required=False, label="Subpudratchilar tarmog'i bor",
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'title': "Doimiy subpudratchilar bazasi bo'lsa belgilang",
        }))

    # Bank-specific fields
    project_type = forms.ChoiceField(
        choices=[('government','Davlat tenderi'), ('private','Xususiy buyurtma'), ('mixed','Aralash')],
        required=False
    )
    equipment_pct = forms.IntegerField(min_value=0, max_value=100, initial=50, required=False)
    license_valid = forms.BooleanField(required=False, initial=True)


class TextileDetailForm(forms.Form):
    UNIT_CHOICES = [('meters','Metr'), ('kg','Kilogramm'), ('pieces','Dona')]
    production_capacity_monthly = forms.IntegerField(
        min_value=1, initial=1000, label='Oylik ishlab chiqarish hajmi',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '1000'})
    )
    unit_of_measure = forms.ChoiceField(choices=UNIT_CHOICES, label="O'lchov birligi",
        widget=forms.Select(attrs={'class': 'form-select'}))
    raw_material_monthly_uzs = forms.DecimalField(
        min_value=0, initial=0, label='Oylik xomashyo xarajati (UZS)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '15000000'})
    )
    export_experience = forms.BooleanField(required=False, label='Eksport tajribasi bor',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'title': "Oldingi eksport shartnomalari bo'lgan bo'lsa belgilang",
        }))
    existing_buyers = forms.CharField(required=False, label='Mavjud yoki muzokaradagi xaridorlar',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
            'placeholder': 'H&M Rossiya — 500,000 metr/yil muzokarada...'}))
    months_to_get_cert = forms.IntegerField(
        min_value=0, initial=6, label='Sertifikat olishga (oy)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '6'})
    )
    machinery_age_years = forms.IntegerField(min_value=0, initial=5, label="Uskunalar o'rtacha yoshi (yil)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '5'}))
    num_workers_skilled = forms.IntegerField(min_value=0, initial=10, label='Malakali ishchilar',
        widget=forms.NumberInput(attrs={'class': 'form-control'}))
    electricity_monthly = forms.DecimalField(
        min_value=0, initial=2_000_000, label='Oylik elektr xarajati (UZS)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '2000000'})
    )
    
    # Bank-specific fields
    export_pct = forms.IntegerField(min_value=0, max_value=100, initial=30, required=False)
    market_type = forms.ChoiceField(
        choices=[('domestic','Ichki'), ('cis','MDH'), ('europe','Yevropa'), ('mixed','Aralash')],
        required=False
    )
    cert_type = forms.ChoiceField(
        choices=[('gost','GOST'), ('iso','ISO'), ('oeko_tex','Oeko-Tex'), ('none','Yo\'q')],
        required=False
    )
    factory_sqm = forms.IntegerField(min_value=0, initial=500, required=False)


class TradeDetailForm(forms.Form):
    trade_type = forms.ChoiceField(
        choices=[('grocery',"Oziq-ovqat do'koni"), ('clothing','Kiyim-kechak'),
                 ('electronics','Elektronika va texnika'), ('pharmacy','Dorixona'),
                 ('building_materials','Qurilish materiallari'), ('cosmetics', 'Kosmetika va Parfyumeriya'),
                 ('auto_parts', 'Avto ehtiyot qismlari'), ('stationery', 'Kanselyariya va kitoblar'),
                 ('household', "Uy ro'zg'or buyumlari"), ('wholesale',"Ulgurji savdo"),
                 ('online',"Internet do'kon"), ('mixed','Aralash savdo')],
        label="Do'kon turi", widget=forms.Select(attrs={'class': 'form-select'})
    )
    store_format = forms.ChoiceField(
        choices=[('street_shop',"Ko'cha do'koni"), ('mall_shop','Savdo markaz'),
                 ('market_stall','Bozor rastasi'), ('supermarket','Mini-supermarket'),
                 ('warehouse_store',"Omborxona-do'kon")],
        label="Do'kon formati", widget=forms.Select(attrs={'class': 'form-select'})
    )
    avg_monthly_stock_uzs = forms.DecimalField(
        min_value=0, initial=10_000_000, label='Oylik tovar zaxirasi (UZS)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '10000000'})
    )
    avg_markup_pct = forms.FloatField(
        min_value=1, max_value=500, initial=25.0, label="O'rtacha ustama %",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'placeholder': '25'})
    )
    inventory_turnover_days = forms.IntegerField(
        min_value=1, initial=30, label='Tovar aylanma (kun)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '30'})
    )
    supplier_credit_days = forms.IntegerField(
        min_value=0, initial=14, label='Yetkazib beruvchi muhlati (kun)',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '14'})
    )
    direct_competitors_300m = forms.IntegerField(
        min_value=0, initial=2, label="300m'da to'g'ridan-to'g'ri raqobatchilar",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '2'})
    )
    price_strategy = forms.ChoiceField(
        choices=[('budget','Arzon narx'), ('mid',"O'rta narx"), ('premium','Premium narx')],
        label='Narx strategiyasi', widget=forms.Select(attrs={'class': 'form-select'})
    )

    # Bank-specific fields
    suppliers_count = forms.IntegerField(min_value=1, initial=3, required=False)
    credit_line_needed = forms.DecimalField(min_value=0, initial=0, required=False)
    stock_turnover = forms.IntegerField(min_value=1, initial=30, required=False)


class ServiceDetailForm(forms.Form):
    provider_type = forms.ChoiceField(
        choices=[('individual','Yakka tartibda'), ('agency','Agentlik'), ('mixed','Aralash')],
        required=False
    )
    equipment_uzs = forms.DecimalField(min_value=0, initial=0, required=False)
    repeat_pct = forms.IntegerField(min_value=0, max_value=100, initial=40, required=False)
    service_avg_price = forms.DecimalField(min_value=0, initial=150000, required=False)
