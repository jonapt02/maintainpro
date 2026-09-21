from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

db = SQLAlchemy()

# ==================== CONSTANTES ====================

TIPOS_MAQUINA = {
    'TAL': 'Taladro', 'ING': 'Ingleteadora', 'DES': 'Destornillador',
    'SOL': 'Soldadora', 'SOP': 'Sopladora', 'PUL': 'Pulidora',
    'COR': 'Cortadora', 'LII': 'Lijadora', 'ROT': 'Rotomartillo',
    'TOR': 'Torno', 'FRE': 'Fresadora', 'CNC': 'CNC', 'DOB': 'Dobladora',
    'COM': 'Compresor', 'GEN': 'Generador', 'ARG': 'Tanque de Argón',
    'OXI': 'Tanque de Oxígeno', 'GAS': 'Tanque de Gas', 'OTR': 'Otro'
}

FRECUENCIAS = {
    'semanal': {'nombre': 'Semanal', 'dias': 7},
    'mensual': {'nombre': 'Mensual', 'dias': 30},
    'trimestral': {'nombre': 'Trimestral', 'dias': 90},
    'semestral': {'nombre': 'Semestral', 'dias': 180},
    'anual': {'nombre': 'Anual', 'dias': 365},
    'trianual': {'nombre': 'Trianual (3 años)', 'dias': 1095},
    'cuatrienal': {'nombre': 'Cuatrienal (4 años)', 'dias': 1460},
    'personalizada': {'nombre': 'Personalizada', 'dias': 0}
}

CRITICIDAD = {
    'critico': {'nombre': 'Crítico', 'color': '#d32f2f', 'icono': 'exclamation-triangle-fill'},
    'medianamente_critico': {'nombre': 'Medianamente Crítico', 'color': '#ffab00', 'icono': 'exclamation-circle-fill'},
    'nada_critico': {'nombre': 'No Crítico', 'color': '#00c853', 'icono': 'check-circle-fill'}
}


# ==================== MAQUINA ====================

class Maquina(db.Model):
    __tablename__ = 'maquinas'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    tipo_codigo = db.Column(db.String(10))
    serial = db.Column(db.String(50))
    modelo = db.Column(db.String(100))
    marca = db.Column(db.String(100))
    ubicacion = db.Column(db.String(200))
    fecha_compra = db.Column(db.Date, nullable=True)
    fecha_instalacion = db.Column(db.Date, nullable=True)
    proveedor = db.Column(db.String(100))
    estado = db.Column(db.String(20), default='Operativa')
    observaciones = db.Column(db.Text)

    frecuencia = db.Column(db.String(20), default='mensual')
    frecuencia_dias = db.Column(db.Integer, default=30)
    criticidad = db.Column(db.String(30), default='nada_critico')
    fecha_ultimo_mantenimiento = db.Column(db.Date, nullable=True)
    fecha_proximo_mantenimiento = db.Column(db.Date, nullable=True)

    notificar_mantenimiento = db.Column(db.Boolean, default=True)

    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    mantenimientos = db.relationship('Mantenimiento', backref='maquina', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Maquina {self.nombre}>'

    @property
    def tipo_nombre(self):
        return TIPOS_MAQUINA.get(self.tipo_codigo, 'Desconocido')

    @property
    def frecuencia_nombre(self):
        if self.frecuencia == 'personalizada':
            return f'Cada {self.frecuencia_dias} días'
        return FRECUENCIAS.get(self.frecuencia, {}).get('nombre', 'Sin definir')

    @property
    def criticidad_info(self):
        return CRITICIDAD.get(self.criticidad, CRITICIDAD['nada_critico'])

    @property
    def dias_frecuencia(self):
        if self.frecuencia == 'personalizada':
            return self.frecuencia_dias or 30
        return FRECUENCIAS.get(self.frecuencia, {}).get('dias', 30)

    @property
    def debe_notificar(self):
        if self.notificar_mantenimiento is False:
            return False
        if self.criticidad in ['critico', 'medianamente_critico']:
            return True
        return False

    @property
    def fecha_inicio_cronograma(self):
        ultimo = self.ultimo_mantenimiento
        if ultimo and ultimo.fecha:
            return ultimo.fecha.date()
        if self.fecha_instalacion:
            return self.fecha_instalacion
        if self.fecha_compra:
            return self.fecha_compra
        return datetime.utcnow().date()

    @property
    def ultimo_mantenimiento(self):
        return Mantenimiento.query.filter_by(maquina_id=self.id).order_by(Mantenimiento.fecha.desc()).first()

    @property
    def ultimo_preventivo(self):
        return Mantenimiento.query.filter_by(maquina_id=self.id, tipo='Preventivo').order_by(Mantenimiento.fecha.desc()).first()

    @property
    def total_mantenimientos(self):
        return Mantenimiento.query.filter_by(maquina_id=self.id).count()

    @property
    def total_preventivos(self):
        return Mantenimiento.query.filter_by(maquina_id=self.id, tipo='Preventivo').count()

    @property
    def total_correctivos(self):
        return Mantenimiento.query.filter_by(maquina_id=self.id, tipo='Correctivo').count()

    @property
    def dias_sin_mantenimiento(self):
        ultimo = self.ultimo_mantenimiento
        if ultimo and ultimo.fecha:
            return (datetime.utcnow() - ultimo.fecha).days
        return None

    @property
    def proxima_fecha_calculada(self):
        ultimo = self.ultimo_preventivo
        if ultimo and ultimo.fecha:
            return ultimo.fecha.date() + timedelta(days=self.dias_frecuencia)
        elif self.fecha_instalacion:
            return self.fecha_instalacion + timedelta(days=self.dias_frecuencia)
        elif self.fecha_compra:
            return self.fecha_compra + timedelta(days=self.dias_frecuencia)
        return None

    @property
    def dias_para_proximo(self):
        proxima = self.fecha_proximo_mantenimiento or self.proxima_fecha_calculada
        if proxima:
            return (proxima - datetime.utcnow().date()).days
        return None

    @property
    def estado_mantenimiento(self):
        dias = self.dias_para_proximo
        if dias is None:
            return 'sin_programar'
        if dias < 0:
            return 'vencido'
        if dias <= 7:
            return 'proximo'
        return 'al_dia'

    @property
    def correctivos_recientes(self):
        hace_90 = datetime.utcnow() - timedelta(days=90)
        return Mantenimiento.query.filter(
            Mantenimiento.maquina_id == self.id,
            Mantenimiento.tipo == 'Correctivo',
            Mantenimiento.fecha >= hace_90
        ).count()

    @property
    def sugerir_correctivo(self):
        return self.correctivos_recientes >= 2

    @staticmethod
    def generar_codigo(tipo_codigo):
        ultima = Maquina.query.filter(Maquina.codigo.like(f'{tipo_codigo}-%')).order_by(Maquina.codigo.desc()).first()
        if ultima:
            try:
                numero = int(ultima.codigo.split('-')[-1]) + 1
            except (IndexError, ValueError):
                numero = 1
        else:
            numero = 1
        if numero > 999:
            raise ValueError(f"Límite alcanzado para {tipo_codigo}")
        return f'{tipo_codigo}-{numero:03d}'

    @staticmethod
    def generar_serial(tipo_codigo):
        seriales = Maquina.query.filter(
            Maquina.tipo_codigo == tipo_codigo,
            Maquina.serial.like(f'{tipo_codigo}-%')
        ).all()
        if not seriales:
            return f'{tipo_codigo}-00000'
        numeros = []
        for m in seriales:
            if m.serial:
                try:
                    numeros.append(int(m.serial.split('-')[-1]))
                except (IndexError, ValueError):
                    continue
        if not numeros:
            return f'{tipo_codigo}-00000'
        siguiente = max(numeros) + 1
        if siguiente > 99999:
            raise ValueError(f"Límite alcanzado para {tipo_codigo}")
        return f'{tipo_codigo}-{siguiente:05d}'


# ==================== MANTENIMIENTO ====================

class Mantenimiento(db.Model):
    __tablename__ = 'mantenimientos'

    id = db.Column(db.Integer, primary_key=True)
    maquina_id = db.Column(db.Integer, db.ForeignKey('maquinas.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tecnico = db.Column(db.String(100), nullable=False)
    departamento = db.Column(db.String(100))
    descripcion = db.Column(db.Text, nullable=False)
    repuestos = db.Column(db.Text)
    observaciones = db.Column(db.Text)
    duracion = db.Column(db.Float, default=0.0)
    prioridad = db.Column(db.String(20), default='Normal')
    estado = db.Column(db.String(20), default='Completado')
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    fecha_programada = db.Column(db.Date, nullable=True)
    dias_desviacion = db.Column(db.Integer, default=0)
    origen = db.Column(db.String(20), default='manual')

    def __repr__(self):
        return f'<Mantenimiento {self.tipo} - {self.maquina.nombre}>'

    @property
    def fecha_segura(self):
        return self.fecha if self.fecha else datetime.utcnow()

    @property
    def estado_cumplimiento(self):
        if self.tipo == 'Correctivo':
            return 'correctivo'
        if self.dias_desviacion is None:
            return 'sin_dato'
        if self.dias_desviacion == 0:
            return 'a_tiempo'
        if self.dias_desviacion > 0:
            return 'retrasado'
        return 'adelantado'

    @property
    def etiqueta_cumplimiento(self):
        if self.estado_cumplimiento == 'correctivo':
            return 'Correctivo'
        if self.estado_cumplimiento == 'a_tiempo':
            return 'A tiempo'
        if self.estado_cumplimiento == 'retrasado':
            return f'{abs(self.dias_desviacion)} día(s) de retraso'
        if self.estado_cumplimiento == 'adelantado':
            return f'{abs(self.dias_desviacion)} día(s) adelantado'
        return 'Sin dato'


# ==================== DESTINATARIO ====================

class Destinatario(db.Model):
    __tablename__ = 'destinatarios'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    area = db.Column(db.String(100))
    activo = db.Column(db.Boolean, default=True)
    recibe_preventivos = db.Column(db.Boolean, default=True)
    recibe_correctivos = db.Column(db.Boolean, default=True)
    recibe_vencidos = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Destinatario {self.email}>'