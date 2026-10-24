from flask import Flask, request, jsonify, render_template_string, send_file
import sqlite3
from datetime import datetime
import qrcode
import io
import socket

app = Flask(__name__)
DB = "locations.db"

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS locations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  lat REAL, lon REAL, accuracy REAL, speed REAL,
                  timestamp TEXT, device TEXT)''')
    conn.commit()
    conn.close()

init_db()

MAP_HTML = '''
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitoramento</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * { box-sizing: border-box; }
        body { margin: 0; font-family: system-ui, sans-serif; background: #0a0a0a; color: #eee; }
        #header {
            padding: 16px 20px; background: #111; border-bottom: 1px solid #222;
            display: flex; justify-content: space-between; align-items: center;
        }
        h1 { margin: 0; font-size: 18px; font-weight: 500; }
        #status { margin-top: 6px; font-size: 13px; color: #aaa; }
        #map { height: calc(100vh - 90px); }
        #qrbox {
            text-align: center; background: #111; padding: 12px 20px;
            border-radius: 12px; border: 1px solid #222;
        }
        #qrbox img { width: 140px; height: 140px; background: #fff; padding: 6px; border-radius: 8px; }
        #qrbox p { margin: 6px 0 0 0; font-size: 12px; color: #888; }
    </style>
</head>
<body>
    <div id="header">
        <div>
            <h1>Monitoramento do Celular</h1>
            <div id="status">Aguardando dados...</div>
        </div>
        <div id="qrbox">
            <img src="/qrcode" alt="QR Code">
            <p>Escaneie no celular<br>para enviar localização</p>
        </div>
    </div>
    <div id="map"></div>
    <script>
        const map = L.map('map').setView([-5.526, -47.491], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);

        let marker = null;
        let path = L.polyline([], {color: '#3EF0DC', weight: 4, opacity: 0.8}).addTo(map);
        const points = [];

        async function update() {
            try {
                const res = await fetch('/locations?limit=30');
                const data = await res.json();
                if (!data.length) return;

                const latest = data[0];
                const latlng = [latest.lat, latest.lon];

                if (!marker) {
                    marker = L.marker(latlng).addTo(map).bindPopup('Posição atual').openPopup();
                } else {
                    marker.setLatLng(latlng);
                }

                points.push(latlng);
                if (points.length > 80) points.shift();
                path.setLatLngs(points);
                map.setView(latlng, Math.max(map.getZoom(), 15));

                const speed = latest.speed ? (latest.speed * 3.6).toFixed(1) + ' km/h' : '—';
                document.getElementById('status').innerHTML =
                    `${latest.lat.toFixed(6)}, ${latest.lon.toFixed(6)} · ` +
                    `Precisão ${latest.accuracy ? latest.accuracy.toFixed(0) + ' m' : '—'} · ` +
                    `Vel. ${speed} · ${latest.timestamp.replace('T',' ').slice(0,19)}`;
            } catch (e) { console.error(e); }
        }

        setInterval(update, 3000);
        update();
    </script>
</body>
</html>
'''

TRACK_HTML = '''
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
    <title>Rastreando</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0; padding: 24px; min-height: 100vh;
            font-family: system-ui, sans-serif;
            background: #0a0a0a; color: #eee;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
        }
        h1 { font-size: 22px; font-weight: 500; margin: 0 0 8px 0; }
        #status { font-size: 15px; color: #aaa; margin: 16px 0; text-align: center; }
        button {
            background: #3EF0DC; color: #000; border: none;
            padding: 14px 32px; border-radius: 12px;
            font-size: 16px; font-weight: 600; cursor: pointer;
        }
        button:disabled { opacity: 0.5; }
        #log { margin-top: 24px; font-size: 12px; color: #666; max-width: 320px; word-break: break-all; text-align: center; }
    </style>
</head>
<body>
    <h1>Rastreador</h1>
    <div id="status">Toque para iniciar</div>
    <button id="btn" onclick="toggle()">Iniciar</button>
    <div id="log"></div>

    <script>
        let watchId = null;
        let sending = false;
        const btn = document.getElementById('btn');
        const status = document.getElementById('status');
        const log = document.getElementById('log');

        function toggle() {
            if (sending) stop(); else start();
        }

        function start() {
            if (!navigator.geolocation) {
                status.textContent = 'Geolocalização não suportada';
                return;
            }
            sending = true;
            btn.textContent = 'Parar';
            status.textContent = 'Obtendo posição...';

            watchId = navigator.geolocation.watchPosition(
                pos => send(pos),
                err => {
                    status.textContent = 'Erro: ' + err.message;
                    console.error(err);
                },
                { enableHighAccuracy: true, maximumAge: 2000, timeout: 10000 }
            );
        }

        function stop() {
            if (watchId !== null) navigator.geolocation.clearWatch(watchId);
            sending = false;
            btn.textContent = 'Iniciar';
            status.textContent = 'Parado';
        }

        async function send(pos) {
            const data = {
                lat: pos.coords.latitude,
                lon: pos.coords.longitude,
                accuracy: pos.coords.accuracy,
                speed: pos.coords.speed || 0,
                device: 'web-android'
            };

            try {
                const res = await fetch('/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (res.ok) {
                    status.textContent = `Enviando · ${data.lat.toFixed(5)}, ${data.lon.toFixed(5)}`;
                    log.textContent = new Date().toLocaleTimeString() + ' ok';
                } else {
                    status.textContent = 'Erro no servidor';
                }
            } catch (e) {
                status.textContent = 'Sem conexão com o servidor';
                log.textContent = e.message;
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(MAP_HTML)

@app.route('/track')
def track():
    return render_template_string(TRACK_HTML)

@app.route('/qrcode')
def qrcode_img():
    base = request.host_url.rstrip('/')
    track_url = f"{base}/track"
    
    img = qrcode.make(track_url)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/update', methods=['POST'])
def update_location():
    data = request.get_json(force=True)
    lat = data.get('lat')
    lon = data.get('lon')
    if lat is None or lon is None:
        return jsonify({"error": "lat/lon required"}), 400

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO locations (lat, lon, accuracy, speed, timestamp, device) VALUES (?,?,?,?,?,?)",
              (lat, lon, data.get('accuracy'), data.get('speed'),
               datetime.utcnow().isoformat() + 'Z', data.get('device', 'web')))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/locations')
def get_locations():
    limit = int(request.args.get('limit', 30))
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT lat, lon, accuracy, speed, timestamp, device FROM locations ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    result = [{"lat": r[0], "lon": r[1], "accuracy": r[2], "speed": r[3], "timestamp": r[4], "device": r[5]} for r in rows]
    return jsonify(result)

if __name__ == '__main__':
    print("\\n=== Rastreador Web ===")
    print("Monitoramento : http://0.0.0.0:5000")
    print("Celular       : http://0.0.0.0:5000/track")
    print("========================\\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
