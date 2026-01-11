Buat rekan-rekan yang mau coba implementasi sistem ini,
untuk diperhatian struktur program pada pythonanywhere nya,
folder pythonanywhere semuanya ada didalam folder mysite

folder arduino code : berisi coding untuk arduino 
folder pythonanywhere : berisi coding untuk di implementasi di pythonanywhere
folder datase : berisi dataset monitoring iot dan analisis model sarimax 

Struktur Program

Energy-Monitoring-IoT/
│
├── arduino/
│   └── esp32_pzem.ino
│
├── pythonanywhere/
│   ├── flask_app.py
│   ├── static/
│   |   └── css/
│   |       └── dashboard.css
│   └── templates/
│       ├── dashboard.html
│       ├── ai_prediction.html
│       ├── log.html
│       ├── report.html
│       ├── info.html
|       └── layout
|           ├── footer.html
|           └── header.html           
├── dataset/
│   ├── energy_data.csv
│   └── analisis.ipynb
└── README.md

For discussion and more please contact me
at https://wa.me/6282126418514
