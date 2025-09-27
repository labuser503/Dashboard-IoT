# Alertas incluídas
import eventlet
eventlet.monkey_patch()

import os
import json
import io
import csv
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, send_file, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import paho.mqtt.client as mqtt
from flask_cors import CORS
import requests

# --- CONFIGURACIÓN ---
MQTT_BROKER = 'broker.hivemq.com'
MQTT_PORT = 1883
MQTT_TOPIC = 'iot/dashboard/data'
colombia_tz = timezone(timedelta(hours=-5))
# El canal de notificación está fijo en el backend, como solicitaste
NTFY_TOPIC = 'alertas-iot-monitor-9876'

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')
CORS(app)

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle': 280, 'pool_pre_ping': True}
db = SQLAlchemy(app)

# --- MODELOS DE LA BASE DE DATOS ---
class Lectura(db.Model):
    __tablename__ = 'lecturas'
    id = db.Column(db.Integer, primary_key=True)
    volt = db.Column(db.Float, nullable=False)
    amp = db.Column(db.Float, nullable=False)
    temp = db.Column(db.Float, nullable=False)
    temp1 = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id, 'volt': self.volt, 'amp': self.amp,
            'temp': self.temp, 'temp1': self.temp1,
            'timestamp': self.timestamp.astimezone(colombia_tz).isoformat()
        }

# Modelo para guardar los ajustes de las alertas
class Ajustes(db.Model):
    __tablename__ = 'ajustes'
    id = db.Column(db.Integer, primary_key=True) # Solo habrá una fila con id=1
    volt_max = db.Column(db.Float, nullable=False, default=100.0)
    amp_max = db.Column(db.Float, nullable=False, default=1.0)

# --- LÓGICA DE ALERTAS Y MQTT ---
def enviar_notificacion(mensaje):
    try:
        requests.post(f"https://ntfy.sh/{NTFY_TOPIC}", data=mensaje.encode('utf-8'))
        print(f"Notificación enviada: {mensaje}")
    except Exception as e:
        print(f"Error al enviar notificación: {e}")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado exitosamente al Broker MQTT!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Fallo al conectar, código de retorno {rc}\n")

def on_message(client, userdata, msg):
    with app.app_context():
        try:
            data = json.loads(msg.payload.decode())
            nueva_lectura = Lectura(
                volt=data['volt'], amp=data['amp'],
                temp=data['temp'], temp1=data['temp1']
            )
            db.session.add(nueva_lectura)
            db.session.commit()
            print(f"Dato de MQTT guardado en la BD: ID {nueva_lectura.id}")

            # Comprobar si hay que enviar alertas
            ajustes = Ajustes.query.first()
            if ajustes:
                if nueva_lectura.volt > ajustes.volt_max:
                    mensaje = f"¡Alerta de Voltaje! Valor actual: {nueva_lectura.volt:.2f}V (Umbral: {ajustes.volt_max}V)"
                    enviar_notificacion(mensaje)
                
                if nueva_lectura.amp > ajustes.amp_max:
                    mensaje = f"¡Alerta de Corriente! Valor actual: {nueva_lectura.amp:.2f}A (Umbral: {ajustes.amp_max}A)"
                    enviar_notificacion(mensaje)
        except Exception as e:
            print(f"Error al procesar el mensaje MQTT: {e}")

# --- RUTAS HTTP ---
@app.route('/')
def index():
    return render_template('index.html')

# Rutas para gestionar los ajustes de las alertas
@app.route('/api/ajustes', methods=['GET'])
def get_ajustes():
    ajustes = Ajustes.query.first()
    if not ajustes:
        ajustes = Ajustes(id=1) # Crear la primera fila de ajustes
        db.session.add(ajustes)
        db.session.commit()
    return jsonify({'volt_max': ajustes.volt_max, 'amp_max': ajustes.amp_max})

@app.route('/api/ajustes', methods=['POST'])
def set_ajustes():
    data = request.get_json()
    ajustes = Ajustes.query.first()
    
    # **CAMBIO: Validar la entrada para evitar errores si los campos están vacíos**
    try:
        new_volt_max = data.get('volt_max')
        if new_volt_max is not None and str(new_volt_max).strip() != '':
            ajustes.volt_max = float(new_volt_max)
    except (ValueError, TypeError):
        print("Valor de voltaje inválido recibido. Se ignora.")

    try:
        new_amp_max = data.get('amp_max')
        if new_amp_max is not None and str(new_amp_max).strip() != '':
            ajustes.amp_max = float(new_amp_max)
    except (ValueError, TypeError):
        print("Valor de amperaje inválido recibido. Se ignora.")

    db.session.commit()
    return jsonify(status="ok", message="Ajustes guardados correctamente.")

@app.route('/api/initial-data')
def initial_data():
    lecturas = Lectura.query.order_by(Lectura.id.desc()).limit(3600).all()
    lecturas.reverse()
    return jsonify([lectura.to_dict() for lectura in lecturas])

@app.route('/api/ultima-lectura')
def ultima_lectura():
    lectura = Lectura.query.order_by(Lectura.id.desc()).first()
    if lectura:
        return jsonify(lectura.to_dict())
    return jsonify({})

@app.route('/download/csv')
def download_csv():
    with app.app_context():
        todas_las_lecturas = Lectura.query.all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Timestamp (Hora Colombia)', 'Voltaje (V)', 'Corriente (A)', 'Temperatura (°C)', 'Temperatura 1 (°C)'])
        for lectura in todas_las_lecturas:
            colombia_timestamp = lectura.timestamp.astimezone(colombia_tz)
            writer.writerow([lectura.id, colombia_timestamp.strftime('%Y-%m-%d %H:%M:%S'), lectura.volt, lectura.amp, lectura.temp, lectura.temp1])
        memoria_csv = io.BytesIO()
        memoria_csv.write(output.getvalue().encode('utf-8'))
        memoria_csv.seek(0)
        output.close()
        return send_file(memoria_csv, as_attachment=True, download_name='datos_iot_colombia.csv', mimetype='text/csv')

@app.route('/api/delete-all', methods=['POST'])
def delete_all_data():
    try:
        db.session.execute(text('TRUNCATE TABLE lecturas RESTART IDENTITY;'))
        db.session.commit()
        return jsonify(status="ok", message="Todos los registros han sido eliminados."), 200
    except Exception as e:
        db.session.rollback()
        return jsonify(status="error", message=str(e)), 500

# --- INICIALIZACIÓN DE SERVICIOS ---
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

with app.app_context():
    db.create_all()

# --- EJECUCIÓN DE LA APLICACIÓN ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
