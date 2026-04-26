import os

path = r'd:\PROJECTS\HACKATON\SQB-BANK\templates\core\analysis_form.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '<div class="form-check form-switch mb-2">\n              {{ form2.is_24_7 }}',
    '<div class="form-check form-switch mb-2" data-bs-toggle="tooltip" data-bs-placement="top" title="Belgilangan bo\'lsa, biznes uzluksiz, dam olishsiz ishlaydi deb hisoblanadi.">\n              {{ form2.is_24_7 }}'
)

content = content.replace(
    '<div class="form-check form-switch mt-2">\n              {{ form2.has_seasonal_dependency }}',
    '<div class="form-check form-switch mt-2" data-bs-toggle="tooltip" data-bs-placement="right" title="Ba\'zi oylarda savdo sezilarli tushib yoki oshib ketadigan bizneslar uchun.">\n              {{ form2.has_seasonal_dependency }}'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done.')
