'''from flask import Flask, Response, render_template
import time
import random
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream')
def stream():
    def generate():
        while True:
            volt = round(random.uniform(3.0, 5.0), 2)
            amp = round(random.uniform(0.1, 2.0), 2)
            temp = round(random.uniform(20.0, 30.0), 2)
            temp1 = round(random.uniform(0.1, 2.0), 2)
            data = f"{volt},{amp},{temp},{temp1}"
            yield f"data: {data}\n\n"
            time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)'''

# **CAMBIO CRÍTICO: Añadir eventlet.monkey_patch() al inicio**
# Esto debe ser lo PRIMERO que se ejecute para asegurar que todas las
# librerías estándar se vuelvan compatibles con la concurrencia de eventlet.
''' CON BASE DE DATOS, SIN BOTÓN
import eventlet
eventlet.monkey_patch()

import os
import time
import random
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from threading import Lock

# --- 1. Configuración Inicial ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')
socketio = SocketIO(app, async_mode='eventlet')

# --- 2. Configuración de la Base de Datos PostgreSQL ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# --- 3. Modelo de la Base de Datos ---
class Lectura(db.Model):
    __tablename__ = 'lecturas'
    id = db.Column(db.Integer, primary_key=True)
    volt = db.Column(db.Float, nullable=False)
    amp = db.Column(db.Float, nullable=False)
    temp = db.Column(db.Float, nullable=False)
    temp1 = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'volt': self.volt,
            'amp': self.amp,
            'temp': self.temp,
            'temp1': self.temp1,
            'timestamp': self.timestamp.isoformat()
        }

# --- 4. Generador de Datos Aleatorios ---
thread = None
thread_lock = Lock()

def generar_datos_aleatorios_y_emitir():
    """Genera datos, los guarda en la BD y los emite por WebSocket."""
    print("Iniciando generador de datos aleatorios en segundo plano...")
    while True:
        with app.app_context():
            datos_aleatorios = {
                'volt': round(random.uniform(4.5, 5.0), 2),
                'amp': round(random.uniform(0.1, 0.2), 2),
                'temp': round(random.uniform(25.0, 27.0), 2),
                'temp1': round(random.uniform(24.0, 25.0), 2)
            }
            nueva_lectura = Lectura(**datos_aleatorios)
            db.session.add(nueva_lectura)
            db.session.commit()
            socketio.emit('nueva_lectura', nueva_lectura.to_dict())
        socketio.sleep(1)

# --- 5. Rutas de la Aplicación ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data', methods=['POST'])
def receive_data():
    try:
        data = request.get_json()
        nueva_lectura = Lectura(
            volt=data['volt'], amp=data['amp'],
            temp=data['temp'], temp1=data['temp1']
        )
        db.session.add(nueva_lectura)
        db.session.commit()
        socketio.emit('nueva_lectura', nueva_lectura.to_dict())
        return jsonify(status="ok", message="Datos guardados"), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error al recibir datos: {e}")
        return jsonify(status="error", message=str(e)), 400

# --- 6. Lógica de WebSockets ---
@socketio.on('connect')
def handle_connect():
    global thread
    print('¡Cliente web conectado!')
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=generar_datos_aleatorios_y_emitir)

    with app.app_context():
        try:
            lecturas_recientes = Lectura.query.order_by(Lectura.timestamp.desc()).limit(60).all()
            lecturas_recientes.reverse()
            emit('datos_iniciales', [lectura.to_dict() for lectura in lecturas_recientes])
        except Exception as e:
            print(f"Error al cargar datos iniciales: {e}")

# --- 7. Inicialización ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)'''

'''# CON BASE DE DATOS Y BOTÓN DE DESCARGA
import eventlet
eventlet.monkey_patch()

import os
import time
import random
# **Importar librerías necesarias para la descarga de CSV**
import io
import csv
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from threading import Lock

# --- 1. Configuración Inicial ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')
socketio = SocketIO(app, async_mode='eventlet')

# --- 2. Configuración de la Base de Datos PostgreSQL ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# --- 3. Modelo de la Base de Datos ---
class Lectura(db.Model):
    __tablename__ = 'lecturas'
    id = db.Column(db.Integer, primary_key=True)
    volt = db.Column(db.Float, nullable=False)
    amp = db.Column(db.Float, nullable=False)
    temp = db.Column(db.Float, nullable=False)
    temp1 = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'volt': self.volt,
            'amp': self.amp,
            'temp': self.temp,
            'temp1': self.temp1,
            'timestamp': self.timestamp.isoformat()
        }

# --- 4. Generador de Datos Aleatorios ---
thread = None
thread_lock = Lock()

def generar_datos_aleatorios_y_emitir():
    """Genera datos, los guarda en la BD y los emite por WebSocket."""
    print("Iniciando generador de datos aleatorios en segundo plano...")
    while True:
        with app.app_context():
            datos_aleatorios = {
                'volt': round(random.uniform(4.5, 5.0), 2),
                'amp': round(random.uniform(0.1, 0.2), 2),
                'temp': round(random.uniform(25.0, 26.0), 2),
                'temp1': round(random.uniform(24.0, 25.0), 2)
            }
            nueva_lectura = Lectura(**datos_aleatorios)
            db.session.add(nueva_lectura)
            db.session.commit()
            socketio.emit('nueva_lectura', nueva_lectura.to_dict())
        socketio.sleep(1)

# --- 5. Rutas de la Aplicación ---
@app.route('/')
def index():
    return render_template('index.html')

# **Nueva ruta para descargar los datos como un archivo CSV**
@app.route('/download/csv')
def download_csv():
    with app.app_context():
        # 1. Consultar TODOS los registros de la base de datos
        todas_las_lecturas = Lectura.query.all()

        # 2. Crear un archivo CSV en memoria
        output = io.StringIO()
        writer = csv.writer(output)

        # 3. Escribir la fila del encabezado
        writer.writerow(['ID', 'Timestamp', 'Voltaje (V)', 'Corriente (A)', 'Temperatura (°C)', 'Temperatura 1 (°C)'])

        # 4. Escribir cada fila de datos
        for lectura in todas_las_lecturas:
            writer.writerow([
                lectura.id, 
                lectura.timestamp.strftime('%Y-%m-%d %H:%M:%S'), 
                lectura.volt, 
                lectura.amp, 
                lectura.temp, 
                lectura.temp1
            ])
        
        # 5. Preparar el archivo en memoria para ser enviado
        memoria_csv = io.BytesIO()
        memoria_csv.write(output.getvalue().encode('utf-8'))
        memoria_csv.seek(0) # Mover el cursor al inicio del archivo en memoria
        output.close()

        # 6. Enviar el archivo al navegador para que se descargue
        return send_file(
            memoria_csv,
            as_attachment=True,
            download_name='datos_iot.csv',
            mimetype='text/csv'
        )

# --- RUTA PARA EL ESP32 (COMENTADA POR AHORA) ---
# @app.route('/api/data', methods=['POST'])
# def receive_data():
#     # ... código para recibir datos del ESP32 ...

# --- 6. Lógica de WebSockets ---
@socketio.on('connect')
def handle_connect():
    global thread
    print('¡Cliente web conectado!')
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=generar_datos_aleatorios_y_emitir)

    with app.app_context():
        try:
            lecturas_recientes = Lectura.query.order_by(Lectura.timestamp.desc()).limit(60).all()
            lecturas_recientes.reverse()
            emit('datos_iniciales', [lectura.to_dict() for lectura in lecturas_recientes])
        except Exception as e:
            print(f"Error al cargar datos iniciales: {e}")

# --- 7. Inicialización ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)'''

'''# BASE DE DATOS, BOTÓN DE DESCARGA Y BOTÓN DE BORRADO
import eventlet
eventlet.monkey_patch()

import os
import time
import random
# Importar librerías necesarias para la descarga de CSV
import io
import csv
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from threading import Lock

# --- 1. Configuración Inicial ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')
socketio = SocketIO(app, async_mode='eventlet')

# --- 2. Configuración de la Base de Datos PostgreSQL ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# --- 3. Modelo de la Base de Datos ---
class Lectura(db.Model):
    __tablename__ = 'lecturas'
    id = db.Column(db.Integer, primary_key=True)
    volt = db.Column(db.Float, nullable=False)
    amp = db.Column(db.Float, nullable=False)
    temp = db.Column(db.Float, nullable=False)
    temp1 = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'volt': self.volt,
            'amp': self.amp,
            'temp': self.temp,
            'temp1': self.temp1,
            'timestamp': self.timestamp.isoformat()
        }

# --- 4. Generador de Datos Aleatorios ---
thread = None
thread_lock = Lock()

def generar_datos_aleatorios_y_emitir():
    """Genera datos, los guarda en la BD y los emite por WebSocket."""
    print("Iniciando generador de datos aleatorios en segundo plano...")
    while True:
        with app.app_context():
            datos_aleatorios = {
                'volt': round(random.uniform(4.5, 5.0), 2),
                'amp': round(random.uniform(0.1, 0.2), 2),
                'temp': round(random.uniform(25.0, 26.0), 2),
                'temp1': round(random.uniform(24.0, 25.0), 2)
            }
            nueva_lectura = Lectura(**datos_aleatorios)
            db.session.add(nueva_lectura)
            db.session.commit()
            socketio.emit('nueva_lectura', nueva_lectura.to_dict())
        socketio.sleep(1)

# --- 5. Rutas de la Aplicación ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download/csv')
def download_csv():
    with app.app_context():
        todas_las_lecturas = Lectura.query.all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Timestamp', 'Voltaje (V)', 'Corriente (A)', 'Temperatura (°C)', 'Temperatura 1 (°C)'])
        for lectura in todas_las_lecturas:
            writer.writerow([lectura.id, lectura.timestamp.strftime('%Y-%m-%d %H:%M:%S'), lectura.volt, lectura.amp, lectura.temp, lectura.temp1])
        memoria_csv = io.BytesIO()
        memoria_csv.write(output.getvalue().encode('utf-8'))
        memoria_csv.seek(0)
        output.close()
        return send_file(memoria_csv, as_attachment=True, download_name='datos_iot.csv', mimetype='text/csv')

# **NUEVA RUTA PARA BORRAR TODOS LOS DATOS**
@app.route('/api/delete-all', methods=['POST'])
def delete_all_data():
    try:
        # Borra eficientemente todas las filas de la tabla Lectura
        num_rows_deleted = db.session.query(Lectura).delete()
        db.session.commit()
        print(f"Todos los datos ({num_rows_deleted} filas) han sido eliminados.")
        
        # Avisa a todos los clientes que la base de datos ha sido limpiada
        socketio.emit('database_cleared')
        
        return jsonify(status="ok", message=f"{num_rows_deleted} registros eliminados correctamente."), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al eliminar datos: {e}")
        return jsonify(status="error", message=str(e)), 500

# --- RUTA PARA EL ESP32 (COMENTADA POR AHORA) ---
# @app.route('/api/data', methods=['POST'])
# def receive_data():
#     # ... código para recibir datos del ESP32 ...

# --- 6. Lógica de WebSockets ---
@socketio.on('connect')
def handle_connect():
    global thread
    print('¡Cliente web conectado!')
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=generar_datos_aleatorios_y_emitir)

    with app.app_context():
        try:
            lecturas_recientes = Lectura.query.order_by(Lectura.timestamp.desc()).limit(60).all()
            lecturas_recientes.reverse()
            emit('datos_iniciales', [lectura.to_dict() for lectura in lecturas_recientes])
        except Exception as e:
            print(f"Error al cargar datos iniciales: {e}")

# --- 7. Inicialización ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
'''

# DATOS ALEATORIOS RESET COMPLETO BD Y HORA UTC-5
'''import eventlet
eventlet.monkey_patch()

import os
import time
import random
import io
import csv
# **CAMBIO 1: Importar librerías de datetime para manejar zonas horarias**
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from threading import Lock

# **CAMBIO 2: Definir la zona horaria de Colombia (UTC-5)**
colombia_tz = timezone(timedelta(hours=-5))

# --- 1. Configuración Inicial ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')
socketio = SocketIO(app, async_mode='eventlet', ping_timeout=20, ping_interval=10)

# --- 2. Configuración de la Base de Datos PostgreSQL ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_pre_ping': True
}
db = SQLAlchemy(app)

# --- 3. Modelo de la Base de Datos ---
class Lectura(db.Model):
    __tablename__ = 'lecturas'
    id = db.Column(db.Integer, primary_key=True)
    volt = db.Column(db.Float, nullable=False)
    amp = db.Column(db.Float, nullable=False)
    temp = db.Column(db.Float, nullable=False)
    temp1 = db.Column(db.Float, nullable=False)
    # Hacer explícito que la columna de la base de datos es consciente de la zona horaria
    timestamp = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    def to_dict(self):
        # **CAMBIO 3: Convertir el timestamp a la zona horaria de Colombia antes de enviarlo**
        return {
            'id': self.id,
            'volt': self.volt,
            'amp': self.amp,
            'temp': self.temp,
            'temp1': self.temp1,
            'timestamp': self.timestamp.astimezone(colombia_tz).isoformat()
        }

# --- Prueba 4. Generador de Datos Aleatorios ---
thread = None
thread_lock = Lock()

def generar_datos_aleatorios_y_emitir():
    """Genera datos, los guarda en la BD y los emite por WebSocket."""
    print("Iniciando generador de datos aleatorios en segundo plano...")
    while True:
        with app.app_context():
            datos_aleatorios = {
                'volt': round(random.uniform(4.5, 5.0), 2),
                'amp': round(random.uniform(0.1, 0.2), 2),
                'temp': round(random.uniform(25.0, 26.0), 2),
                'temp1': round(random.uniform(24.0, 25.0), 2)
            }
            nueva_lectura = Lectura(**datos_aleatorios)
            db.session.add(nueva_lectura)
            db.session.commit()
            socketio.emit('nueva_lectura', nueva_lectura.to_dict())
        socketio.sleep(1)

# --- 5. Rutas de la Aplicación ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download/csv')
def download_csv():
    with app.app_context():
        todas_las_lecturas = Lectura.query.all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Timestamp (Hora Colombia)', 'Voltaje (V)', 'Corriente (A)', 'Temperatura (°C)', 'Temperatura 1 (°C)'])
        for lectura in todas_las_lecturas:
            # **CAMBIO 4: Convertir el timestamp a la zona horaria de Colombia para el archivo CSV**
            colombia_timestamp = lectura.timestamp.astimezone(colombia_tz)
            writer.writerow([
                lectura.id,
                colombia_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                lectura.volt,
                lectura.amp,
                lectura.temp,
                lectura.temp1
            ])
        memoria_csv = io.BytesIO()
        memoria_csv.write(output.getvalue().encode('utf-8'))
        memoria_csv.seek(0)
        output.close()
        return send_file(
            memoria_csv,
            as_attachment=True,
            download_name='datos_iot.csv',
            mimetype='text/csv'
        )

@app.route('/api/delete-all', methods=['POST'])
def delete_all_data():
    try:
        db.session.execute(text('TRUNCATE TABLE lecturas RESTART IDENTITY;'))
        db.session.commit()
        
        print("Todos los datos han sido eliminados y el ID ha sido reiniciado.")
        
        socketio.emit('database_cleared')
        
        return jsonify(status="ok", message="Todos los registros han sido eliminados y la secuencia de ID reiniciada."), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al truncar la tabla: {e}")
        return jsonify(status="error", message=str(e)), 500

# --- RUTA PARA EL ESP32 (COMENTADA POR AHORA) ---
# @app.route('/api/data', methods=['POST'])
# def receive_data():
#     # ... código para recibir datos del ESP32 ...

# --- 6. Lógica de WebSockets ---
@socketio.on('connect')
def handle_connect():
    global thread
    print('¡Cliente web conectado!')
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=generar_datos_aleatorios_y_emitir)

    with app.app_context():
        try:
            lecturas_recientes = Lectura.query.order_by(Lectura.timestamp.desc()).limit(60).all()
            lecturas_recientes.reverse()
            emit('datos_iniciales', [lectura.to_dict() for lectura in lecturas_recientes])
        except Exception as e:
            print(f"Error al cargar datos iniciales: {e}")

# --- 7. Inicialización ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
'''

'''# DATOS HTTP ESP32 RESET COMPLETO BD Y HORA UTC-5
import eventlet
eventlet.monkey_patch()

import os
import time
import random
import io
import csv
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from threading import Lock

colombia_tz = timezone(timedelta(hours=-5))

# --- 1. Configuración Inicial ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')
socketio = SocketIO(app, async_mode='eventlet', ping_timeout=20, ping_interval=10)

# --- 2. Configuración de la Base de Datos PostgreSQL ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 280,
    'pool_pre_ping': True
}
db = SQLAlchemy(app)

# --- 3. Modelo de la Base de Datos ---
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
            'id': self.id,
            'volt': self.volt,
            'amp': self.amp,
            'temp': self.temp,
            'temp1': self.temp1,
            'timestamp': self.timestamp.astimezone(colombia_tz).isoformat()
        }

# --- 4. Generador de Datos Aleatorios (COMENTADO PARA PRUEBAS FUTURAS) ---
# thread = None
# thread_lock = Lock()
# 
# def generar_datos_aleatorios_y_emitir():
#     """Genera datos, los guarda en la BD y los emite por WebSocket."""
#     print("Iniciando generador de datos aleatorios en segundo plano...")
#     while True:
#         with app.app_context():
#             datos_aleatorios = {
#                 'volt': round(random.uniform(4.5, 5.0), 2),
#                 'amp': round(random.uniform(0.1, 0.2), 2),
#                 'temp': round(random.uniform(25.0, 26.0), 2),
#                 'temp1': round(random.uniform(24.0, 25.0), 2)
#             }
#             nueva_lectura = Lectura(**datos_aleatorios)
#             db.session.add(nueva_lectura)
#             db.session.commit()
#             socketio.emit('nueva_lectura', nueva_lectura.to_dict())
#         socketio.sleep(1)

# --- 5. Rutas de la Aplicación ---
@app.route('/')
def index():
    return render_template('index.html')

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
        print("Todos los datos han sido eliminados y el ID ha sido reiniciado.")
        socketio.emit('database_cleared')
        return jsonify(status="ok", message="Todos los registros han sido eliminados y la secuencia de ID reiniciada."), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al truncar la tabla: {e}")
        return jsonify(status="error", message=str(e)), 500

# **CAMBIO: RUTA PARA EL ESP32 (ACTIVADA)**
@app.route('/api/data', methods=['POST'])
def receive_data():
    try:
        data = request.get_json()
        print(f"Datos recibidos desde ESP32: {data}")
        # Crear y guardar la nueva lectura en la base de datos
        nueva_lectura = Lectura(
            volt=data['volt'],
            amp=data['amp'],
            temp=data['temp'],
            temp1=data['temp1']
        )
        db.session.add(nueva_lectura)
        db.session.commit()
        # Emitir la nueva lectura a todos los clientes conectados
        socketio.emit('nueva_lectura', nueva_lectura.to_dict())
        return jsonify(status="ok", message="Datos guardados"), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error al recibir datos del ESP32: {e}")
        return jsonify(status="error", message=str(e)), 400

# --- 6. Lógica de WebSockets ---
@socketio.on('connect')
def handle_connect():
    print('¡Cliente web conectado!')
    # **CAMBIO: Ya no se inicia el generador de datos aleatorios**
    # with thread_lock:
    #     if thread is None:
    #         thread = socketio.start_background_task(target=generar_datos_aleatorios_y_emitir)

    # Al conectar, se siguen enviando los datos históricos
    with app.app_context():
        try:
            lecturas_recientes = Lectura.query.order_by(Lectura.timestamp.desc()).limit(900).all()
            lecturas_recientes.reverse()
            emit('datos_iniciales', [lectura.to_dict() for lectura in lecturas_recientes])
        except Exception as e:
            print(f"Error al cargar datos iniciales: {e}")

# --- 7. Inicialización ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
'''
'''# DATOS MQTT ESP32 RESET COMPLETO BD Y HORA UTC-5
import eventlet
eventlet.monkey_patch()

import os
import time
import random
import io
import csv
import json # Necesario para procesar los mensajes MQTT
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from threading import Lock
import paho.mqtt.client as mqtt # Importar la librería MQTT

# --- CONFIGURACIÓN MQTT ---
MQTT_BROKER = 'broker.hivemq.com'
MQTT_PORT = 1883
# **IMPORTANTE**: Este es tu canal único. No lo compartas.
# Puedes cambiar 'dayana-monitor' por otra cosa si quieres.
MQTT_TOPIC = 'iot/dayana-monitor/data'

colombia_tz = timezone(timedelta(hours=-5))

# --- 1. Configuración Inicial ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')
socketio = SocketIO(app, async_mode='eventlet', ping_timeout=20, ping_interval=10)

# --- 2. Configuración de la Base de Datos ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle': 280, 'pool_pre_ping': True}
db = SQLAlchemy(app)

# --- 3. Modelo de la Base de Datos ---
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
            'id': self.id,
            'volt': self.volt,
            'amp': self.amp,
            'temp': self.temp,
            'temp1': self.temp1,
            'timestamp': self.timestamp.astimezone(colombia_tz).isoformat()
        }

# --- 4. Lógica MQTT ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado exitosamente al Broker MQTT!")
        client.subscribe(MQTT_TOPIC)
        print(f"Suscrito al tema: {MQTT_TOPIC}")
    else:
        print(f"Fallo al conectar, código de retorno {rc}\n")

def on_message(client, userdata, msg):
    """Esta función se ejecuta cada vez que llega un mensaje del ESP32."""
    print(f"Mensaje recibido en el tema `{msg.topic}`: {msg.payload.decode()}")
    try:
        # Decodificar el mensaje JSON
        data = json.loads(msg.payload.decode())
        
        # Usamos un contexto de aplicación para interactuar con la BD y SocketIO
        with app.app_context():
            # Crear y guardar la nueva lectura en la base de datos
            nueva_lectura = Lectura(
                volt=data['volt'],
                amp=data['amp'],
                temp=data['temp'],
                temp1=data['temp1']
            )
            db.session.add(nueva_lectura)
            db.session.commit()
            
            # Emitir la nueva lectura a todos los clientes del dashboard
            socketio.emit('nueva_lectura', nueva_lectura.to_dict())
            print("Dato guardado en BD y emitido al dashboard.")

    except Exception as e:
        print(f"Error al procesar el mensaje MQTT: {e}")

# Configurar y conectar el cliente MQTT
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
# Iniciar el cliente MQTT en un hilo no bloqueante
mqtt_client.loop_start()

# --- 5. Rutas de la Aplicación (HTTP) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download/csv')
def download_csv():
    # ... (código de descarga sin cambios) ...
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
    # ... (código de borrado sin cambios) ...
    try:
        db.session.execute(text('TRUNCATE TABLE lecturas RESTART IDENTITY;'))
        db.session.commit()
        print("Todos los datos han sido eliminados y el ID ha sido reiniciado.")
        socketio.emit('database_cleared')
        return jsonify(status="ok", message="Todos los registros han sido eliminados y la secuencia de ID reiniciada."), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al truncar la tabla: {e}")
        return jsonify(status="error", message=str(e)), 500

# --- 6. Lógica de WebSockets para el Dashboard ---
@socketio.on('connect')
def handle_connect():
    print('¡Cliente web del dashboard conectado!')
    # Al conectar, se siguen enviando los datos históricos
    with app.app_context():
        try:
            lecturas_recientes = Lectura.query.order_by(Lectura.timestamp.desc()).limit(900).all()
            lecturas_recientes.reverse()
            emit('datos_iniciales', [lectura.to_dict() for lectura in lecturas_recientes])
        except Exception as e:
            print(f"Error al cargar datos iniciales: {e}")

# --- 7. Inicialización ---
with app.app_context():
    db.create_all()
'''
'''# DATOS MQTT ESP32 8va versión
import eventlet
eventlet.monkey_patch()

import os
import json
import io
import csv
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, send_file, jsonify
# Se elimina SocketIO ya que no se usará para el push en tiempo real
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import paho.mqtt.client as mqtt

# --- CONFIGURACIÓN ---
MQTT_BROKER = 'broker.hivemq.com'
MQTT_PORT = 1883
MQTT_TOPIC = 'iot/dayana-monitor/data'
colombia_tz = timezone(timedelta(hours=-5))

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle': 280, 'pool_pre_ping': True}
db = SQLAlchemy(app)

# --- MODELO DE LA BASE DE DATOS ---
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

# --- LÓGICA MQTT ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado exitosamente al Broker MQTT!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Fallo al conectar, código de retorno {rc}\n")

def on_message(client, userdata, msg):
    """Esta función solo guarda el dato en la base de datos."""
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
        except Exception as e:
            print(f"Error al procesar el mensaje MQTT: {e}")

# --- RUTAS HTTP ---
@app.route('/')
def index():
    return render_template('index.html')

# **NUEVA RUTA para que el frontend consulte el último dato**
@app.route('/api/ultima-lectura')
def ultima_lectura():
    # Busca el último registro en la base de datos ordenando por ID descendente
    lectura = Lectura.query.order_by(Lectura.id.desc()).first()
    if lectura:
        return jsonify(lectura.to_dict())
    # Si no hay datos, devuelve un objeto vacío
    return jsonify({})

@app.route('/download/csv')
def download_csv():
    # ... (código de descarga sin cambios) ...
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
    # ... (código de borrado sin cambios, pero ya no emite por SocketIO) ...
    try:
        db.session.execute(text('TRUNCATE TABLE lecturas RESTART IDENTITY;'))
        db.session.commit()
        print("Todos los datos han sido eliminados y el ID ha sido reiniciado.")
        return jsonify(status="ok", message="Todos los registros han sido eliminados."), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al truncar la tabla: {e}")
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
    # Ya no se usa socketio.run, volvemos a app.run
    app.run(host='0.0.0.0', port=port, debug=True)
'''

'''
# MQTT + ESP32 + DASHBOARD CON 60 DATOS 
import eventlet
eventlet.monkey_patch()

import os
import json
import io
import csv
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, send_file, jsonify
# Se elimina SocketIO ya que no se usará para el push en tiempo real
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
import paho.mqtt.client as mqtt

# --- CONFIGURACIÓN ---
MQTT_BROKER = 'broker.hivemq.com'
MQTT_PORT = 1883
MQTT_TOPIC = 'iot/dayana-monitor/data'
colombia_tz = timezone(timedelta(hours=-5))

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una-clave-secreta-muy-fuerte-para-desarrollo')

# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle': 280, 'pool_pre_ping': True}
db = SQLAlchemy(app)

# --- MODELO DE LA BASE DE DATOS ---
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

# --- LÓGICA MQTT ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Conectado exitosamente al Broker MQTT!")
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"Fallo al conectar, código de retorno {rc}\n")

def on_message(client, userdata, msg):
    """Esta función solo guarda el dato en la base de datos."""
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
        except Exception as e:
            print(f"Error al procesar el mensaje MQTT: {e}")

# --- RUTAS HTTP ---
@app.route('/')
def index():
    return render_template('index.html')

# **NUEVA RUTA para que el frontend cargue los datos históricos**
@app.route('/api/initial-data')
def initial_data():
    # Busca los últimos 60 registros en la base de datos
    lecturas = Lectura.query.order_by(Lectura.id.desc()).limit(3600).all()
    # Invierte la lista para que el más antiguo aparezca primero
    lecturas.reverse()
    # Convierte los objetos a diccionarios y los devuelve como JSON
    return jsonify([lectura.to_dict() for lectura in lecturas])

@app.route('/api/ultima-lectura')
def ultima_lectura():
    # Busca el último registro en la base de datos
    lectura = Lectura.query.order_by(Lectura.id.desc()).first()
    if lectura:
        return jsonify(lectura.to_dict())
    return jsonify({})

@app.route('/download/csv')
def download_csv():
    # ... (código de descarga sin cambios) ...
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
    # ... (código de borrado sin cambios) ...
    try:
        db.session.execute(text('TRUNCATE TABLE lecturas RESTART IDENTITY;'))
        db.session.commit()
        print("Todos los datos han sido eliminados y el ID ha sido reiniciado.")
        return jsonify(status="ok", message="Todos los registros han sido eliminados."), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al truncar la tabla: {e}")
        return jsonify(status="error", message=str(e)), 500

# --- INICIALIZACIÓN DE SERVICIOS ---
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

with app.app_context():
    db.create_all()
'''

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
MQTT_TOPIC = 'iot/dayana-monitor/data'
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
# --- EJECUCIÓN DE LA APLICACIÓN ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)


# --- EJECUCIÓN DE LA APLICACIÓN ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
