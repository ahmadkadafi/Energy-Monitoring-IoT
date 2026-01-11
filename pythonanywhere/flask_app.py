from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta
import mysql.connector
import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX


# ============================
# DATABASE CONFIG
# ============================
db_config = {
    'user': 'AhmadKadafiHS',
    'password': 'Bilal2018!',
    'host': 'AhmadKadafiHS.mysql.pythonanywhere-services.com',
    'database': 'AhmadKadafiHS$db_monitoring'
}

def get_db():
    return mysql.connector.connect(**db_config)

def load_energy_data(device):
    conn = get_db()
    query = """
        SELECT created_at, energy
        FROM monitoring
        WHERE device = %s
        ORDER BY created_at ASC
    """
    df = pd.read_sql(query, conn, params=(device,))
    conn.close()

    df["datetime"] = pd.to_datetime(df["created_at"])
    df = df.set_index("datetime")
    return df

# ============================
# FLASK APP
# ============================
app = Flask(__name__)

# ============================
# HELPER
# ============================
def clean(val):
    if val in ["", "nan", "null", None]:
        return None
    return val

# ============================
# ROOT TEST
# ============================
@app.route("/")
def home():
    return "FLASK OK"

# ============================
# API — TIME (GMT+7)
# ============================
@app.route("/api/time")
def api_time():
    now = datetime.utcnow() + timedelta(hours=7)
    return jsonify({
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": "GMT+7"
    })

# ============================
# API — POST DATA (NodeMCU)
# ============================
@app.route("/api/post/data", methods=["POST"])
def api_post_data():
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    query = """
        INSERT INTO monitoring
        (device, voltage, current, power, energy, frequency, pf, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """

    cursor.execute(query, (
        clean(data.get("device")),
        clean(data.get("voltage")),
        clean(data.get("current")),
        clean(data.get("power")),
        clean(data.get("energy")),
        clean(data.get("frequency")),
        clean(data.get("pf")),
        clean(data.get("created_at"))
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"status": "OK", "message": "Data inserted"})

# ============================
# API — LATEST VALUE (TOP ROW)
# ============================
@app.route("/api/latest/<device>")
def api_latest(device):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT voltage, current, power, energy, frequency, pf, created_at
        FROM monitoring
        WHERE device = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (device,))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return jsonify({"error": "No data"}), 404

    return jsonify({
        "voltage": row[0],
        "current": row[1],
        "power": row[2],
        "energy": row[3],
        "frequency": row[4],
        "pf": row[5],
        "time": row[6].strftime("%Y-%m-%d %H:%M:%S")
    })
# ============================
# API — PREDICT ENERGY
# ============================
@app.route("/api/predict/energy/<device>")
def api_predict_energy(device):

    df = load_energy_data(device)

    if len(df) < 24:
        return jsonify({"error": "Data tidak cukup untuk prediksi"}), 400

    # Resample per jam (ambil nilai terakhir)
    energy_hourly = df["energy"].resample("1H").last().dropna()

    # Model SARIMA sederhana
    model = SARIMAX(
        energy_hourly,
        order=(1,1,1),
        seasonal_order=(0,0,0,0),
        enforce_stationarity=False,
        enforce_invertibility=False
    )

    model_fit = model.fit(disp=False)

    # Prediksi 24 jam ke depan
    forecast = model_fit.forecast(steps=24)

    future_index = pd.date_range(
        start=energy_hourly.index[-1] + timedelta(hours=1),
        periods=24,
        freq="H"
    )

    forecast_series = pd.Series(forecast.values, index=future_index)

    # Ambil hanya jam 00:00
    forecast_00 = forecast_series[forecast_series.index.hour == 0]

    return jsonify({
        "device": device,
        "last_actual_time": energy_hourly.index[-1].strftime("%Y-%m-%d %H:%M:%S"),
        "prediction": [
            {
                "datetime": idx.strftime("%Y-%m-%d %H:%M:%S"),
                "energy_kwh": float(val)
            }
            for idx, val in forecast_00.items()
        ]
    })

# ============================
# API — EVALUATION ENERGY
# ============================
@app.route("/api/predict/evaluation/<device>")
def api_predict_evaluation(device):
    import pandas as pd
    from statsmodels.tsa.statespace.sarimax import SARIMAX

    conn = get_db()
    df = pd.read_sql("""
        SELECT created_at, energy
        FROM monitoring
        WHERE device = %s
        ORDER BY created_at ASC
    """, conn, params=(device,))
    conn.close()

    if df.empty or len(df) < 48:
        return jsonify([])

    df["datetime"] = pd.to_datetime(df["created_at"])
    df = df.set_index("datetime")

    # hourly energy
    energy_hourly = df["energy"].resample("1H").last().dropna()
    energy_00 = energy_hourly[energy_hourly.index.hour == 0]

    results = []
    MIN_TRAIN = 3

    for i in range(MIN_TRAIN, len(energy_00)):
        train = energy_00.iloc[:i]
        actual = energy_00.iloc[i]
        date_pred = energy_00.index[i]

        try:
            model = SARIMAX(
                train,
                order=(1,1,1),
                seasonal_order=(0,0,0,0),
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            fit = model.fit(disp=False)
            pred = float(fit.forecast(1).iloc[0])

            results.append({
                "date": date_pred.strftime("%Y-%m-%d"),
                "predicted": round(pred, 3),
                "actual": round(float(actual), 3),
                "error": round(float(actual - pred), 3)
            })
        except:
            continue

    return jsonify(results[-7:])  # tampilkan 7 hari terakhir
# ============================
# API — DATA FOR 6 CHARTS
# ============================
@app.route("/api/chart/<device>")
def api_chart(device):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT created_at, voltage, current, power, energy, frequency, pf
        FROM monitoring
        WHERE device = %s
        ORDER BY created_at DESC
        LIMIT 120
    """, (device,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return jsonify({"error": "No data"}), 404

    rows.reverse()

    return jsonify({
        "time": [r[0].strftime("%H:%M:%S") for r in rows],
        "voltage": [r[1] for r in rows],
        "current": [r[2] for r in rows],
        "power": [r[3] for r in rows],
        "energy": [r[4] for r in rows],
        "frequency": [r[5] for r in rows],
        "pf": [r[6] for r in rows]
    })
# ============================
# API — DATA FOR REPORT MAX MIN AVERAGE
# ============================
@app.route("/api/report/event/<device>")
def report_event(device):
    page = int(request.args.get("page", 1))
    size = int(request.args.get("size", 10))
    offset = (page - 1) * size

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT created_at, voltage, pf,
        CASE
            WHEN voltage < 180 THEN 'Voltage Alarm'
            WHEN voltage < 190 THEN 'Voltage Warning'
            WHEN pf < 0.35 THEN 'PF Alarm'
            WHEN pf < 0.40 THEN 'PF Warning'
        END AS event_type
        FROM monitoring
        WHERE device=%s
        AND (
            voltage < 190 OR pf < 0.40
        )
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (device, size, offset))

    rows = cur.fetchall()

    cur.execute("""
        SELECT COUNT(*) total
        FROM monitoring
        WHERE device=%s
        AND (voltage < 190 OR pf < 0.40)
    """, (device,))
    total = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return jsonify({
        "data": rows,
        "total": total
    })
# ============================
# API — DATA FOR REPORT STATS
# ============================
@app.route("/api/report/stats/<device>")
def report_stats(device):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    queries = {
        "daily": """
            SELECT
                MAX(voltage) v_max, MIN(voltage) v_min, AVG(voltage) v_avg,
                MAX(current) c_max, MIN(current) c_min, AVG(current) c_avg,
                MAX(power) p_max, MIN(power) p_min, AVG(power) p_avg,
                MAX(energy) e_max, MIN(energy) e_min, AVG(energy) e_avg,
                MAX(frequency) f_max, MIN(frequency) f_min, AVG(frequency) f_avg,
                MAX(pf) pf_max, MIN(pf) pf_min, AVG(pf) pf_avg
            FROM monitoring
            WHERE device=%s
            AND DATE(created_at)=CURDATE()
        """,
        "weekly": """
            SELECT
                MAX(voltage), MIN(voltage), AVG(voltage),
                MAX(current), MIN(current), AVG(current),
                MAX(power), MIN(power), AVG(power),
                MAX(energy), MIN(energy), AVG(energy),
                MAX(frequency), MIN(frequency), AVG(frequency),
                MAX(pf), MIN(pf), AVG(pf)
            FROM monitoring
            WHERE device=%s
            AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """,
        "monthly": """
            SELECT
                MAX(voltage), MIN(voltage), AVG(voltage),
                MAX(current), MIN(current), AVG(current),
                MAX(power), MIN(power), AVG(power),
                MAX(energy), MIN(energy), AVG(energy),
                MAX(frequency), MIN(frequency), AVG(frequency),
                MAX(pf), MIN(pf), AVG(pf)
            FROM monitoring
            WHERE device=%s
            AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
    }

    result = {}
    for k, q in queries.items():
        cur.execute(q, (device,))
        r = cur.fetchone()
        result[k] = r

    cur.close()
    conn.close()
    return jsonify(result)

# ============================
# API — DATA FOR TABLE LOG
# ============================
@app.route("/api/log/<device>")
def api_log(device):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            created_at,
            voltage, current, power, energy, frequency, pf
        FROM monitoring
        WHERE device = %s
        ORDER BY created_at DESC
        LIMIT 500
    """, (device,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    data = []
    for i, r in enumerate(rows, start=1):
        data.append({
            "no": i,
            "date": r["created_at"].strftime("%Y-%m-%d"),
            "time": r["created_at"].strftime("%H:%M:%S"),
            "voltage": r["voltage"],
            "current": r["current"],
            "power": r["power"],
            "energy": r["energy"],
            "frequency": r["frequency"],
            "pf": r["pf"]
        })

    return jsonify(data)
# ============================
# DASHBOARD PAGE
# ============================
@app.route("/dashboard/<device>")
def dashboard(device):
    return render_template("dashboard.html", device=device)
# ============================
# AI PREDICTION PAGE
# ============================
@app.route("/ai-prediction/<device>")
def ai_prediction_page(device):
    return render_template("ai_prediction.html", device=device)
# ============================
# LOG PAGE
# ============================
@app.route("/log/<device>")
def log_page(device):
    return render_template("log.html", device=device)
# ============================
# DEVICE PAGE
# ============================
@app.route("/device/<device>")
def device_page(device):
    return render_template("device.html", device=device)
# ============================
# REPORT PAGE
# ============================
@app.route("/report/<device>")
def report_page(device):
    return render_template("report.html", device=device)
# ============================
# INFO PAGE
# ============================
@app.route("/info/<device>")
def info_page(device):
    return render_template("info.html", device=device)
# ============================
# LOCAL RUN (DEBUG)
# ============================
if __name__ == "__main__":
    app.run(debug=True)
