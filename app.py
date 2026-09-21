from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import db, Maquina, Mantenimiento, TIPOS_MAQUINA, Destinatario, FRECUENCIAS, CRITICIDAD
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from dotenv import load_dotenv
import json
import os
import threading

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-super-secreta')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(INSTANCE_DIR, 'mantenimiento.db')

if not os.path.exists(INSTANCE_DIR):
    os.makedirs(INSTANCE_DIR)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = os.environ.get('GMAIL_USER')
app.config['MAIL_PASSWORD'] = os.environ.get('GMAIL_APP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('GMAIL_USER')

db.init_app(app)
mail = Mail(app)

APP_NAME = 'MaintainPro'
APP_AUTHOR = os.environ.get('APP_AUTHOR', 'Equipo de Desarrollo')
APP_URL = os.environ.get('APP_URL', 'http://localhost:5500')

with app.app_context():
    if not os.path.exists(DB_PATH):
        db.create_all()
        print("Base de datos creada")


# ==================== HELPERS DE CORREO ====================

def email_wrapper(content_html, title, subtitle=None, accent_color='#1a237e'):
    subtitle_html = f'<p style="margin:6px 0 0 0;font-size:13px;color:rgba(255,255,255,0.75);">{subtitle}</p>' if subtitle else ''
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{title}</title></head>
<body style="margin:0;padding:0;background:#eef1f5;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#2c3e50;line-height:1.6;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef1f5;padding:30px 15px;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">
<tr><td style="background:linear-gradient(135deg,{accent_color} 0%,#0d47a1 100%);padding:32px 40px;">
<div style="font-size:11px;color:rgba(255,255,255,0.7);letter-spacing:2px;font-weight:600;text-transform:uppercase;">{APP_NAME}</div>
<h1 style="margin:8px 0 0 0;font-size:22px;font-weight:700;color:#fff;">{title}</h1>{subtitle_html}
</td></tr>
<tr><td style="padding:35px 40px 25px 40px;">{content_html}</td></tr>
<tr><td style="background:#f7f9fc;padding:24px 40px;border-top:1px solid #e8ecf1;">
<table width="100%"><tr>
<td style="font-size:12px;color:#7a869a;line-height:1.6;">
<div style="font-weight:600;color:#4a5568;margin-bottom:4px;">{APP_NAME}</div>
<div>Sistema de Gestión de Mantenimiento</div>
<div style="margin-top:8px;">Desarrollado por <strong style="color:#4a5568;">{APP_AUTHOR}</strong></div>
</td>
<td align="right" style="font-size:11px;color:#a0aec0;vertical-align:bottom;">
<div>Mensaje automático</div><div style="margin-top:4px;">No responder</div>
</td></tr></table>
</td></tr></table>
<div style="max-width:600px;margin:20px auto 0 auto;text-align:center;font-size:11px;color:#a0aec0;">&copy; {datetime.now().year} {APP_NAME}</div>
</td></tr></table></body></html>"""


def email_kv_row(label, value, alt=False):
    bg = '#f7f9fc' if alt else '#fff'
    return f"""<tr>
<td style="padding:12px 16px;background:{bg};border-bottom:1px solid #edf1f5;font-size:12px;color:#7a869a;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;width:38%;vertical-align:top;">{label}</td>
<td style="padding:12px 16px;background:{bg};border-bottom:1px solid #edf1f5;font-size:14px;color:#2c3e50;vertical-align:top;">{value}</td>
</tr>"""


def email_info_box(title, content, color='#1a237e'):
    return f"""<div style="background:{color}0D;border-left:4px solid {color};padding:16px 20px;border-radius:0 8px 8px 0;margin:18px 0;">
<div style="font-size:11px;color:{color};font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">{title}</div>
<div style="font-size:14px;color:#2c3e50;line-height:1.5;">{content}</div></div>"""


# ==================== FUNCIONES DE CORREO ====================

def enviar_correo_mantenimiento(mantenimiento, maquina):
    """Notificación cuando se registra un mantenimiento pendiente o en progreso."""
    with app.app_context():
        try:
            if not maquina.debe_notificar:
                print(f"Sin notificación: {maquina.codigo}")
                return

            query = Destinatario.query.filter_by(activo=True)
            if mantenimiento.tipo == 'Preventivo':
                query = query.filter_by(recibe_preventivos=True)
            elif mantenimiento.tipo == 'Correctivo':
                query = query.filter_by(recibe_correctivos=True)

            destinatarios = query.all()
            if not destinatarios:
                print("No hay destinatarios")
                return

            emails = [d.email for d in destinatarios]
            crit_color = {'critico': '#d32f2f', 'medianamente_critico': '#e68a00', 'nada_critico': '#2e7d32'}.get(maquina.criticidad, '#7a869a')
            fecha_str = mantenimiento.fecha.strftime('%d/%m/%Y') if mantenimiento.fecha else 'Sin fecha'

            contenido = f"""
                <p style="font-size:15px;color:#2c3e50;margin:0 0 8px 0;">Se ha registrado un nuevo mantenimiento en el sistema.</p>
                <p style="font-size:13px;color:#7a869a;margin:0 0 20px 0;">Detalle del registro y datos del equipo.</p>

                <h2 style="font-size:13px;color:#1a237e;letter-spacing:1px;text-transform:uppercase;margin:25px 0 10px 0;">Equipo</h2>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #edf1f5;border-radius:8px;overflow:hidden;">
                    {email_kv_row('Código', f'<strong>{maquina.codigo}</strong>')}
                    {email_kv_row('Nombre', maquina.nombre, alt=True)}
                    {email_kv_row('Ubicación', maquina.ubicacion or '—')}
                    {email_kv_row('Estado', maquina.estado, alt=True)}
                    {email_kv_row('Criticidad', f'<span style="color:{crit_color};font-weight:600;">{maquina.criticidad_info["nombre"]}</span>')}
                </table>

                <h2 style="font-size:13px;color:#1a237e;letter-spacing:1px;text-transform:uppercase;margin:25px 0 10px 0;">Mantenimiento</h2>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #edf1f5;border-radius:8px;overflow:hidden;">
                    {email_kv_row('Tipo', f'<strong>{mantenimiento.tipo}</strong>')}
                    {email_kv_row('Fecha programada', mantenimiento.fecha_programada.strftime('%d/%m/%Y') if mantenimiento.fecha_programada else '—', alt=True)}
                    {email_kv_row('Estado', mantenimiento.estado)}
                    {email_kv_row('Encargado', mantenimiento.tecnico, alt=True)}
                    {email_kv_row('Descripción', mantenimiento.descripcion)}
                </table>

                {email_info_box('Acción requerida', 'Revise el detalle y confirme el cierre cuando el trabajo esté completado.', '#1a237e')}

                <div style="text-align:center;margin:30px 0 10px 0;">
                    <a href="{APP_URL}/maquina/{maquina.id}" style="display:inline-block;background:#1a237e;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-size:13px;font-weight:600;">Ver hoja de vida del equipo</a>
                </div>"""

            msg = Message(subject=f'Nuevo mantenimiento — {maquina.codigo}', recipients=emails)
            msg.html = email_wrapper(contenido, 'Registro de Mantenimiento', f'{APP_NAME} · Notificación', '#1a237e')
            mail.send(msg)
            print(f"Correo enviado a {len(emails)} destinatario(s)")
        except Exception as e:
            print(f"Error al enviar correo: {e}")


def enviar_correo_confirmacion(mantenimiento, maquina):
    """Confirmación cuando se completa el mantenimiento."""
    with app.app_context():
        try:
            if not maquina.debe_notificar:
                print(f"Sin confirmación: {maquina.codigo}")
                return

            query = Destinatario.query.filter_by(activo=True)
            if mantenimiento.tipo == 'Preventivo':
                query = query.filter_by(recibe_preventivos=True)
            elif mantenimiento.tipo == 'Correctivo':
                query = query.filter_by(recibe_correctivos=True)

            destinatarios = query.all()
            if not destinatarios:
                return

            emails = [d.email for d in destinatarios]
            crit_color = {'critico': '#d32f2f', 'medianamente_critico': '#e68a00', 'nada_critico': '#2e7d32'}.get(maquina.criticidad, '#7a869a')
            fecha_str = mantenimiento.fecha.strftime('%d/%m/%Y') if mantenimiento.fecha else 'Sin fecha'

            if mantenimiento.tipo == 'Correctivo':
                cumplimiento_html = '<span style="color:#e68a00;font-weight:600;">Correctivo (no programado)</span>'
            elif mantenimiento.dias_desviacion > 0:
                cumplimiento_html = f'<span style="color:#d32f2f;font-weight:600;">{mantenimiento.dias_desviacion} día(s) de retraso</span>'
            elif mantenimiento.dias_desviacion < 0:
                cumplimiento_html = f'<span style="color:#0288d1;font-weight:600;">{abs(mantenimiento.dias_desviacion)} día(s) adelantado</span>'
            else:
                cumplimiento_html = '<span style="color:#2e7d32;font-weight:600;">A tiempo</span>'

            proximo_bloque = ''
            if maquina.fecha_proximo_mantenimiento and mantenimiento.tipo == 'Preventivo':
                proximo_bloque = email_info_box(
                    'Próximo mantenimiento programado',
                    f'<strong>{maquina.fecha_proximo_mantenimiento.strftime("%d/%m/%Y")}</strong><br>'
                    f'<span style="font-size:12px;color:#7a869a;">Frecuencia: {maquina.frecuencia_nombre}</span>',
                    '#2e7d32'
                )

            contenido = f"""
                <p style="font-size:15px;color:#2c3e50;margin:0 0 8px 0;">
                    El mantenimiento ha sido marcado como <strong style="color:#2e7d32;">completado</strong>.
                </p>
                <p style="font-size:13px;color:#7a869a;margin:0 0 20px 0;">Resumen del trabajo realizado.</p>

                <h2 style="font-size:13px;color:#1a237e;letter-spacing:1px;text-transform:uppercase;margin:25px 0 10px 0;">Equipo</h2>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #edf1f5;border-radius:8px;overflow:hidden;">
                    {email_kv_row('Código', f'<strong>{maquina.codigo}</strong>')}
                    {email_kv_row('Nombre', maquina.nombre, alt=True)}
                    {email_kv_row('Ubicación', maquina.ubicacion or '—')}
                    {email_kv_row('Estado actual', f'<span style="color:#2e7d32;font-weight:600;">{maquina.estado}</span>', alt=True)}
                    {email_kv_row('Criticidad', f'<span style="color:{crit_color};font-weight:600;">{maquina.criticidad_info["nombre"]}</span>')}
                </table>

                <h2 style="font-size:13px;color:#1a237e;letter-spacing:1px;text-transform:uppercase;margin:25px 0 10px 0;">Trabajo realizado</h2>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #edf1f5;border-radius:8px;overflow:hidden;">
                    {email_kv_row('Tipo', f'<strong>{mantenimiento.tipo}</strong>')}
                    {email_kv_row('Fecha programada', mantenimiento.fecha_programada.strftime('%d/%m/%Y') if mantenimiento.fecha_programada else '—', alt=True)}
                    {email_kv_row('Fecha de ejecución', fecha_str)}
                    {email_kv_row('Cumplimiento', cumplimiento_html, alt=True)}
                    {email_kv_row('Encargado', mantenimiento.tecnico)}
                    {email_kv_row('Duración', f'{mantenimiento.duracion} h' if mantenimiento.duracion else '—', alt=True)}
                    {email_kv_row('Descripción', mantenimiento.descripcion)}
                    {email_kv_row('Repuestos', mantenimiento.repuestos or '—', alt=True)}
                    {email_kv_row('Observaciones', mantenimiento.observaciones or '—')}
                </table>

                {proximo_bloque}

                <div style="text-align:center;margin:30px 0 10px 0;">
                    <a href="{APP_URL}/maquina/{maquina.id}" style="display:inline-block;background:#1a237e;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-size:13px;font-weight:600;">Ver hoja de vida del equipo</a>
                </div>"""

            msg = Message(subject=f'Mantenimiento completado — {maquina.codigo}', recipients=emails)
            msg.html = email_wrapper(contenido, 'Confirmación de Mantenimiento', f'{APP_NAME} · Reporte de cierre', '#2e7d32')
            mail.send(msg)
            print(f"Confirmación enviada a {len(emails)} destinatario(s)")
        except Exception as e:
            print(f"Error al enviar confirmación: {e}")


def enviar_correo_sugerencia_correctivo(maquina, motivo, usuario_sugiere, emails_destino):
    """Envía correo de sugerencia SOLO a los emails indicados (no filtra por debe_notificar)."""
    with app.app_context():
        try:
            if not emails_destino:
                print("Sin destinatarios seleccionados para sugerencia")
                return

            crit_color = {'critico': '#d32f2f', 'medianamente_critico': '#e68a00', 'nada_critico': '#2e7d32'}.get(maquina.criticidad, '#7a869a')
            fecha_str = datetime.utcnow().strftime('%d/%m/%Y — %H:%M')

            contenido = f"""
                <p style="font-size:15px;color:#2c3e50;margin:0 0 8px 0;">
                    Se ha registrado una <strong style="color:#e68a00;">sugerencia de mantenimiento correctivo</strong> para el siguiente equipo.
                </p>
                <p style="font-size:13px;color:#7a869a;margin:0 0 20px 0;">
                    Este es un aviso informativo. El cronograma de mantenimiento preventivo no se ve afectado.
                </p>

                <h2 style="font-size:13px;color:#1a237e;letter-spacing:1px;text-transform:uppercase;margin:25px 0 10px 0;">Equipo</h2>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #edf1f5;border-radius:8px;overflow:hidden;">
                    {email_kv_row('Código', f'<strong>{maquina.codigo}</strong>')}
                    {email_kv_row('Nombre', maquina.nombre, alt=True)}
                    {email_kv_row('Tipo', maquina.tipo_nombre if maquina.tipo_codigo else '—')}
                    {email_kv_row('Ubicación', maquina.ubicacion or '—', alt=True)}
                    {email_kv_row('Estado actual', maquina.estado)}
                    {email_kv_row('Criticidad', f'<span style="color:{crit_color};font-weight:600;">{maquina.criticidad_info["nombre"]}</span>', alt=True)}
                </table>

                <h2 style="font-size:13px;color:#1a237e;letter-spacing:1px;text-transform:uppercase;margin:25px 0 10px 0;">Detalle de la sugerencia</h2>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #edf1f5;border-radius:8px;overflow:hidden;">
                    {email_kv_row('Sugerido por', usuario_sugiere)}
                    {email_kv_row('Fecha de sugerencia', fecha_str, alt=True)}
                    {email_kv_row('Motivo', motivo or 'No especificado')}
                    {email_kv_row('Correctivos últimos 90 días', f'{maquina.correctivos_recientes}', alt=True)}
                </table>

                {email_info_box('Acción requerida', 'Revise el equipo y programe el mantenimiento correctivo correspondiente. Este equipo podría estar presentando fallas recurrentes.', '#e68a00')}

                <div style="text-align:center;margin:30px 0 10px 0;">
                    <a href="{APP_URL}/maquina/{maquina.id}" style="display:inline-block;background:#1a237e;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-size:13px;font-weight:600;">Ver hoja de vida del equipo</a>
                </div>"""

            msg = Message(
                subject=f'Sugerencia de correctivo — {maquina.codigo}',
                recipients=emails_destino
            )
            msg.html = email_wrapper(
                contenido,
                'Sugerencia de Mantenimiento Correctivo',
                f'{APP_NAME} · Aviso informativo',
                '#e68a00'
            )
            mail.send(msg)
            print(f"Sugerencia enviada a {len(emails_destino)} destinatario(s): {', '.join(emails_destino)}")
        except Exception as e:
            print(f"Error al enviar sugerencia: {e}")


def enviar_alerta_vencidos(maquinas_vencidas):
    """Alerta de mantenimientos vencidos."""
    with app.app_context():
        try:
            maquinas_vencidas = [m for m in maquinas_vencidas if m.debe_notificar]
            if not maquinas_vencidas:
                print("Sin máquinas vencidas para notificar")
                return

            destinatarios = Destinatario.query.filter_by(activo=True, recibe_vencidos=True).all()
            if not destinatarios:
                return

            emails = [d.email for d in destinatarios]

            filas = ''
            for i, m in enumerate(maquinas_vencidas):
                dias = abs(m.dias_para_proximo or 0)
                bg = '#f7f9fc' if (i % 2 == 1) else '#fff'
                crit_color = {'critico': '#d32f2f', 'medianamente_critico': '#e68a00', 'nada_critico': '#2e7d32'}.get(m.criticidad, '#7a869a')
                proxima = m.fecha_proximo_mantenimiento or m.proxima_fecha_calculada
                filas += f"""<tr>
                <td style="padding:10px 12px;background:{bg};border-bottom:1px solid #edf1f5;font-size:13px;font-weight:600;color:#1a237e;">{m.codigo}</td>
                <td style="padding:10px 12px;background:{bg};border-bottom:1px solid #edf1f5;font-size:13px;">{m.nombre}</td>
                <td style="padding:10px 12px;background:{bg};border-bottom:1px solid #edf1f5;font-size:13px;color:#7a869a;">{m.ubicacion or '—'}</td>
                <td style="padding:10px 12px;background:{bg};border-bottom:1px solid #edf1f5;font-size:13px;">{proxima.strftime('%d/%m/%Y') if proxima else '—'}</td>
                <td style="padding:10px 12px;background:{bg};border-bottom:1px solid #edf1f5;font-size:13px;">
                    <span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;background:{crit_color}18;color:{crit_color};">{m.criticidad_info['nombre']}</span>
                </td>
                <td style="padding:10px 12px;background:{bg};border-bottom:1px solid #edf1f5;font-size:13px;font-weight:600;color:#d32f2f;">{dias} días</td>
                </tr>"""

            contenido = f"""
                <p style="font-size:15px;color:#2c3e50;margin:0 0 8px 0;">Los siguientes equipos presentan mantenimiento preventivo vencido.</p>
                <p style="font-size:13px;color:#7a869a;margin:0 0 20px 0;">Total: <strong>{len(maquinas_vencidas)}</strong> equipo(s).</p>

                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #edf1f5;border-radius:8px;overflow:hidden;">
                    <thead><tr style="background:#1a237e;">
                        <th style="padding:12px;text-align:left;font-size:11px;color:#fff;letter-spacing:1px;text-transform:uppercase;">Código</th>
                        <th style="padding:12px;text-align:left;font-size:11px;color:#fff;letter-spacing:1px;text-transform:uppercase;">Equipo</th>
                        <th style="padding:12px;text-align:left;font-size:11px;color:#fff;letter-spacing:1px;text-transform:uppercase;">Ubicación</th>
                        <th style="padding:12px;text-align:left;font-size:11px;color:#fff;letter-spacing:1px;text-transform:uppercase;">Programado</th>
                        <th style="padding:12px;text-align:left;font-size:11px;color:#fff;letter-spacing:1px;text-transform:uppercase;">Criticidad</th>
                        <th style="padding:12px;text-align:left;font-size:11px;color:#fff;letter-spacing:1px;text-transform:uppercase;">Vencido</th>
                    </tr></thead>
                    <tbody>{filas}</tbody>
                </table>

                {email_info_box('Acción requerida', 'Se recomienda programar y ejecutar los mantenimientos pendientes.', '#d32f2f')}

                <div style="text-align:center;margin:30px 0 10px 0;">
                    <a href="{APP_URL}/calendario" style="display:inline-block;background:#1a237e;color:#fff;text-decoration:none;padding:12px 28px;border-radius:6px;font-size:13px;font-weight:600;">Ver calendario</a>
                </div>"""

            msg = Message(subject=f'Alerta de vencidos ({len(maquinas_vencidas)})', recipients=emails)
            msg.html = email_wrapper(contenido, 'Alerta de Vencidos', f'{APP_NAME} · Notificación crítica', '#d32f2f')
            mail.send(msg)
            print(f"Alerta enviada a {len(emails)} destinatario(s)")
        except Exception as e:
            print(f"Error al enviar alerta: {e}")


# ==================== DASHBOARD ====================

@app.route('/')
def index():
    total_maquinas = Maquina.query.count()
    maquinas_operativas = Maquina.query.filter_by(estado='Operativa').count()
    maquinas_mantenimiento = Maquina.query.filter_by(estado='En mantenimiento').count()

    ahora = datetime.now()
    inicio_mes = datetime(ahora.year, ahora.month, 1)

    mantenimientos_mes = Mantenimiento.query.filter(Mantenimiento.fecha >= inicio_mes).count()
    preventivos_mes = Mantenimiento.query.filter(Mantenimiento.fecha >= inicio_mes, Mantenimiento.tipo == 'Preventivo').count()
    correctivos_mes = Mantenimiento.query.filter(Mantenimiento.fecha >= inicio_mes, Mantenimiento.tipo == 'Correctivo').count()

    maquinas_todas = Maquina.query.all()
    proximos_vencidos = sum(1 for m in maquinas_todas if m.estado_mantenimiento == 'vencido')
    proximos_semana = sum(1 for m in maquinas_todas if m.estado_mantenimiento == 'proximo')
    al_dia_count = sum(1 for m in maquinas_todas if m.estado_mantenimiento == 'al_dia')

    fecha_limite = datetime.now() - timedelta(days=30)
    maquinas_pendientes = [m for m in Maquina.query.filter_by(estado='Operativa').all()
                           if not m.ultimo_mantenimiento or m.ultimo_mantenimiento.fecha < fecha_limite]

    top_problematicas = db.session.query(
        Maquina.nombre, Maquina.codigo,
        db.func.count(Mantenimiento.id).label('total')
    ).join(Mantenimiento).filter(Mantenimiento.tipo == 'Correctivo')\
     .group_by(Maquina.id).order_by(db.func.count(Mantenimiento.id).desc()).limit(5).all()

    meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    datos_preventivos, datos_correctivos = [], []

    for i in range(1, 13):
        inicio = datetime(ahora.year, i, 1)
        fin = datetime(ahora.year + 1, 1, 1) if i == 12 else datetime(ahora.year, i + 1, 1)
        datos_preventivos.append(Mantenimiento.query.filter(Mantenimiento.fecha >= inicio, Mantenimiento.fecha < fin, Mantenimiento.tipo == 'Preventivo').count())
        datos_correctivos.append(Mantenimiento.query.filter(Mantenimiento.fecha >= inicio, Mantenimiento.fecha < fin, Mantenimiento.tipo == 'Correctivo').count())

    return render_template('index.html',
                           total_maquinas=total_maquinas, maquinas_operativas=maquinas_operativas,
                           maquinas_mantenimiento=maquinas_mantenimiento,
                           mantenimientos_mes=mantenimientos_mes, preventivos_mes=preventivos_mes,
                           correctivos_mes=correctivos_mes,
                           maquinas_pendientes=maquinas_pendientes[:5], top_problematicas=top_problematicas,
                           meses=json.dumps(meses), datos_preventivos=json.dumps(datos_preventivos),
                           datos_correctivos=json.dumps(datos_correctivos),
                           proximos_vencidos=proximos_vencidos, proximos_semana=proximos_semana,
                           al_dia_count=al_dia_count, now=datetime.now())


# ==================== CRUD MAQUINAS ====================

@app.route('/maquinas')
def listar_maquinas():
    filtro_tipo = request.args.get('tipo', '')
    filtro_estado = request.args.get('estado', '')
    filtro_busqueda = request.args.get('busqueda', '')
    filtro_ubicacion = request.args.get('ubicacion', '')
    filtro_criticidad = request.args.get('criticidad', '')

    query = Maquina.query
    if filtro_tipo: query = query.filter(Maquina.tipo_codigo == filtro_tipo)
    if filtro_estado: query = query.filter(Maquina.estado == filtro_estado)
    if filtro_ubicacion: query = query.filter(Maquina.ubicacion.like(f'%{filtro_ubicacion}%'))
    if filtro_criticidad: query = query.filter(Maquina.criticidad == filtro_criticidad)
    if filtro_busqueda:
        query = query.filter(db.or_(
            Maquina.nombre.like(f'%{filtro_busqueda}%'),
            Maquina.codigo.like(f'%{filtro_busqueda}%'),
            Maquina.serial.like(f'%{filtro_busqueda}%'),
            Maquina.marca.like(f'%{filtro_busqueda}%'),
            Maquina.modelo.like(f'%{filtro_busqueda}%')
        ))

    maquinas = query.order_by(Maquina.codigo).all()

    ubicaciones = sorted([u[0] for u in db.session.query(Maquina.ubicacion).filter(
        Maquina.ubicacion.isnot(None), Maquina.ubicacion != ''
    ).distinct().all()])

    stats = {
        'total': Maquina.query.count(),
        'por_tipo': db.session.query(Maquina.tipo_codigo, db.func.count(Maquina.id)).group_by(Maquina.tipo_codigo).order_by(db.func.count(Maquina.id).desc()).all(),
        'por_estado': db.session.query(Maquina.estado, db.func.count(Maquina.id)).group_by(Maquina.estado).all(),
        'por_criticidad': db.session.query(Maquina.criticidad, db.func.count(Maquina.id)).group_by(Maquina.criticidad).all()
    }

    return render_template('maquinas.html', maquinas=maquinas, tipos=TIPOS_MAQUINA,
                           ubicaciones=ubicaciones, stats=stats, criticidades=CRITICIDAD,
                           filtro_tipo=filtro_tipo, filtro_estado=filtro_estado,
                           filtro_busqueda=filtro_busqueda, filtro_ubicacion=filtro_ubicacion,
                           filtro_criticidad=filtro_criticidad)


@app.route('/api/generar-codigo/<tipo>')
def generar_codigo(tipo):
    try:
        if tipo not in TIPOS_MAQUINA:
            return jsonify({'success': False, 'error': f'Tipo {tipo} no válido'}), 400
        codigo = Maquina.generar_codigo(tipo)
        serial = Maquina.generar_serial(tipo)
        return jsonify({'success': True, 'codigo': codigo, 'serial': serial,
                        'tipo': tipo, 'tipo_nombre': TIPOS_MAQUINA[tipo]})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/destinatarios')
def api_destinatarios():
    """API: devuelve los destinatarios activos para seleccionar"""
    destinatarios = Destinatario.query.filter_by(activo=True).order_by(Destinatario.nombre).all()
    return jsonify([{
        'id': d.id,
        'nombre': d.nombre,
        'email': d.email,
        'area': d.area or '',
        'recibe_correctivos': d.recibe_correctivos
    } for d in destinatarios])


@app.route('/maquina/nueva', methods=['GET', 'POST'])
def crear_maquina():
    if request.method == 'POST':
        tipo_codigo = request.form.get('tipo_codigo', '')
        codigo = request.form.get('codigo', '').strip()
        if not codigo and tipo_codigo:
            codigo = Maquina.generar_codigo(tipo_codigo)

        serial = request.form.get('serial', '').strip()
        if not serial and tipo_codigo:
            serial = Maquina.generar_serial(tipo_codigo)
        if serial in ['', 'None', 'null']:
            serial = None

        frecuencia = request.form.get('frecuencia', 'mensual')
        frecuencia_dias = int(request.form.get('frecuencia_dias', 30)) if request.form.get('frecuencia_dias') else 30
        criticidad = request.form.get('criticidad', 'nada_critico')
        notificar = 'notificar_mantenimiento' in request.form

        maquina = Maquina(
            nombre=request.form['nombre'], codigo=codigo, tipo_codigo=tipo_codigo, serial=serial,
            modelo=request.form.get('modelo'), marca=request.form.get('marca'),
            ubicacion=request.form.get('ubicacion'),
            fecha_compra=datetime.strptime(request.form['fecha_compra'], '%Y-%m-%d') if request.form.get('fecha_compra') else None,
            fecha_instalacion=datetime.strptime(request.form['fecha_instalacion'], '%Y-%m-%d') if request.form.get('fecha_instalacion') else None,
            proveedor=request.form.get('proveedor'), estado=request.form['estado'],
            observaciones=request.form.get('observaciones'),
            frecuencia=frecuencia, frecuencia_dias=frecuencia_dias,
            criticidad=criticidad, notificar_mantenimiento=notificar
        )

        if maquina.fecha_instalacion:
            maquina.fecha_proximo_mantenimiento = maquina.fecha_instalacion + timedelta(days=maquina.dias_frecuencia)

        db.session.add(maquina)
        db.session.commit()
        flash(f'Máquina {codigo} creada exitosamente', 'success')
        return redirect(url_for('listar_maquinas'))

    return render_template('maquina_form.html', maquina=None, tipos=TIPOS_MAQUINA,
                           frecuencias=FRECUENCIAS, criticidades=CRITICIDAD)


@app.route('/maquina/editar/<int:id>', methods=['GET', 'POST'])
def editar_maquina(id):
    maquina = Maquina.query.get_or_404(id)
    if request.method == 'POST':
        maquina.nombre = request.form['nombre']
        maquina.codigo = request.form['codigo']
        maquina.tipo_codigo = request.form.get('tipo_codigo', '')
        serial = request.form.get('serial', '').strip()
        maquina.serial = None if serial in ['', 'None', 'null'] else serial
        maquina.modelo = request.form.get('modelo')
        maquina.marca = request.form.get('marca')
        maquina.ubicacion = request.form.get('ubicacion')
        maquina.fecha_compra = datetime.strptime(request.form['fecha_compra'], '%Y-%m-%d') if request.form.get('fecha_compra') else None
        maquina.fecha_instalacion = datetime.strptime(request.form['fecha_instalacion'], '%Y-%m-%d') if request.form.get('fecha_instalacion') else None
        maquina.proveedor = request.form.get('proveedor')
        maquina.estado = request.form['estado']
        maquina.observaciones = request.form.get('observaciones')
        maquina.frecuencia = request.form.get('frecuencia', 'mensual')
        maquina.frecuencia_dias = int(request.form.get('frecuencia_dias', 30)) if request.form.get('frecuencia_dias') else 30
        maquina.criticidad = request.form.get('criticidad', 'nada_critico')
        maquina.notificar_mantenimiento = 'notificar_mantenimiento' in request.form
        maquina.fecha_proximo_mantenimiento = maquina.proxima_fecha_calculada
        db.session.commit()
        flash('Máquina actualizada', 'success')
        return redirect(url_for('listar_maquinas'))
    return render_template('maquina_form.html', maquina=maquina, tipos=TIPOS_MAQUINA,
                           frecuencias=FRECUENCIAS, criticidades=CRITICIDAD)


@app.route('/maquina/eliminar/<int:id>')
def eliminar_maquina(id):
    maquina = Maquina.query.get_or_404(id)
    db.session.delete(maquina)
    db.session.commit()
    flash('Máquina eliminada', 'warning')
    return redirect(url_for('listar_maquinas'))


@app.route('/maquina/<int:id>')
def detalle_maquina(id):
    maquina = Maquina.query.get_or_404(id)
    mantenimientos = Mantenimiento.query.filter_by(maquina_id=id).order_by(Mantenimiento.fecha.desc()).all()

    total_mant = len(mantenimientos)
    preventivos = sum(1 for m in mantenimientos if m.tipo == 'Preventivo')
    correctivos = sum(1 for m in mantenimientos if m.tipo == 'Correctivo')
    promedio_duracion = sum(m.duracion for m in mantenimientos) / total_mant if total_mant > 0 else 0

    return render_template('maquina_detalle.html', maquina=maquina, mantenimientos=mantenimientos,
                           total_mant=total_mant, preventivos=preventivos, correctivos=correctivos,
                           promedio_duracion=promedio_duracion, now=datetime.now())


# ==================== CRUD MANTENIMIENTOS ====================

@app.route('/mantenimiento/nuevo/<int:maquina_id>', methods=['GET', 'POST'])
def crear_mantenimiento(maquina_id):
    maquina = Maquina.query.get_or_404(maquina_id)

    if request.method == 'POST':
        fecha_str = request.form.get('fecha_realizacion')
        fecha_realizacion = datetime.strptime(fecha_str, '%Y-%m-%d') if fecha_str else datetime.utcnow()

        fecha_programada = maquina.fecha_proximo_mantenimiento or maquina.proxima_fecha_calculada
        dias_desviacion = (fecha_realizacion.date() - fecha_programada).days if fecha_programada else 0

        mantenimiento = Mantenimiento(
            maquina_id=maquina_id, tipo=request.form['tipo'], fecha=fecha_realizacion,
            fecha_programada=fecha_programada, dias_desviacion=dias_desviacion,
            tecnico=request.form['tecnico'], departamento=request.form.get('departamento'),
            descripcion=request.form['descripcion'], repuestos=request.form.get('repuestos'),
            observaciones=request.form.get('observaciones'),
            duracion=float(request.form['duracion']) if request.form.get('duracion') else 0.0,
            prioridad=request.form.get('prioridad', 'Normal'),
            estado=request.form.get('estado', 'Completado')
        )

        if mantenimiento.estado == 'Completado':
            maquina.fecha_ultimo_mantenimiento = fecha_realizacion.date()
            maquina.fecha_proximo_mantenimiento = fecha_realizacion.date() + timedelta(days=maquina.dias_frecuencia)
            if mantenimiento.tipo == 'Preventivo' and maquina.estado == 'En mantenimiento':
                maquina.estado = 'Operativa'

        db.session.add(mantenimiento)
        db.session.commit()

        if mantenimiento.estado == 'Completado':
            threading.Thread(target=enviar_correo_confirmacion, args=(mantenimiento, maquina)).start()
            if dias_desviacion > 0:
                flash(f'Registrado con {dias_desviacion} día(s) de retraso. Próximo: {(fecha_realizacion.date() + timedelta(days=maquina.dias_frecuencia)).strftime("%d/%m/%Y")}', 'warning')
            elif dias_desviacion < 0:
                flash(f'Registrado {abs(dias_desviacion)} día(s) adelantado. Próximo: {(fecha_realizacion.date() + timedelta(days=maquina.dias_frecuencia)).strftime("%d/%m/%Y")}', 'info')
            else:
                flash(f'Registrado a tiempo. Próximo: {(fecha_realizacion.date() + timedelta(days=maquina.dias_frecuencia)).strftime("%d/%m/%Y")}', 'success')
        else:
            threading.Thread(target=enviar_correo_mantenimiento, args=(mantenimiento, maquina)).start()
            flash(f'Mantenimiento {request.form["tipo"]} registrado', 'success')

        return redirect(url_for('detalle_maquina', id=maquina_id))

    return render_template('mantenimiento_form.html', maquina=maquina, now=datetime.now())


@app.route('/mantenimiento/editar/<int:id>', methods=['GET', 'POST'])
def editar_mantenimiento(id):
    mantenimiento = Mantenimiento.query.get_or_404(id)
    maquina = mantenimiento.maquina

    if request.method == 'POST':
        estado_anterior = mantenimiento.estado
        fecha_str = request.form.get('fecha_realizacion')
        fecha_realizacion = datetime.strptime(fecha_str, '%Y-%m-%d') if fecha_str else (mantenimiento.fecha or datetime.utcnow())

        fecha_programada = mantenimiento.fecha_programada or maquina.fecha_proximo_mantenimiento or maquina.proxima_fecha_calculada
        dias_desviacion = (fecha_realizacion.date() - fecha_programada).days if fecha_programada else 0

        mantenimiento.tipo = request.form['tipo']
        mantenimiento.fecha = fecha_realizacion
        mantenimiento.fecha_programada = fecha_programada
        mantenimiento.dias_desviacion = dias_desviacion
        mantenimiento.tecnico = request.form['tecnico']
        mantenimiento.departamento = request.form.get('departamento')
        mantenimiento.descripcion = request.form['descripcion']
        mantenimiento.repuestos = request.form.get('repuestos')
        mantenimiento.observaciones = request.form.get('observaciones')
        mantenimiento.duracion = float(request.form['duracion']) if request.form.get('duracion') else 0.0
        mantenimiento.prioridad = request.form.get('prioridad', 'Normal')
        mantenimiento.estado = request.form.get('estado', 'Completado')

        if mantenimiento.estado == 'Completado':
            maquina.fecha_ultimo_mantenimiento = fecha_realizacion.date()
            maquina.fecha_proximo_mantenimiento = fecha_realizacion.date() + timedelta(days=maquina.dias_frecuencia)

        db.session.commit()

        if estado_anterior != 'Completado' and mantenimiento.estado == 'Completado':
            threading.Thread(target=enviar_correo_confirmacion, args=(mantenimiento, maquina)).start()

        flash('Mantenimiento actualizado', 'success')
        return redirect(url_for('detalle_maquina', id=maquina.id))

    return render_template('mantenimiento_form.html', maquina=maquina, mantenimiento=mantenimiento, now=datetime.now())


@app.route('/mantenimiento/eliminar/<int:id>')
def eliminar_mantenimiento(id):
    mantenimiento = Mantenimiento.query.get_or_404(id)
    maquina_id = mantenimiento.maquina_id
    db.session.delete(mantenimiento)
    db.session.commit()
    flash('Mantenimiento eliminado', 'warning')
    return redirect(url_for('detalle_maquina', id=maquina_id))


@app.route('/maquina/<int:id>/sugerir-correctivo', methods=['POST'])
def sugerir_correctivo(id):
    """Registra una sugerencia de correctivo y envía correo a destinatarios SELECCIONADOS."""
    maquina = Maquina.query.get_or_404(id)

    motivo = request.form.get('motivo', '').strip()
    usuario = request.form.get('usuario', '').strip() or 'Sistema'
    destinatarios_ids = request.form.getlist('destinatarios')

    if not destinatarios_ids:
        flash('Debes seleccionar al menos un destinatario', 'warning')
        return redirect(url_for('detalle_maquina', id=maquina.id))

    destinatarios = Destinatario.query.filter(
        Destinatario.id.in_(destinatarios_ids),
        Destinatario.activo == True
    ).all()

    if not destinatarios:
        flash('Los destinatarios seleccionados no están disponibles', 'warning')
        return redirect(url_for('detalle_maquina', id=maquina.id))

    emails_seleccionados = [d.email for d in destinatarios]

    mantenimiento = Mantenimiento(
        maquina_id=maquina.id, tipo='Correctivo', fecha=datetime.utcnow(),
        tecnico=usuario, descripcion=motivo or 'Sugerencia de correctivo sin motivo especificado',
        estado='Pendiente',
        prioridad='Alta' if maquina.criticidad == 'critico' else 'Media',
        origen='sugerido'
    )

    db.session.add(mantenimiento)
    db.session.commit()

    threading.Thread(
        target=enviar_correo_sugerencia_correctivo,
        args=(maquina, motivo, usuario, emails_seleccionados)
    ).start()

    flash(f'Sugerencia registrada. Se notificó a {len(emails_seleccionados)} destinatario(s).', 'success')
    return redirect(url_for('detalle_maquina', id=maquina.id))


# ==================== CALENDARIO ====================

@app.route('/calendario')
def calendario():
    maquinas = Maquina.query.order_by(Maquina.codigo).all()
    stats = {
        'total': len(maquinas),
        'vencidos': sum(1 for m in maquinas if m.estado_mantenimiento == 'vencido'),
        'proximos': sum(1 for m in maquinas if m.estado_mantenimiento == 'proximo'),
        'al_dia': sum(1 for m in maquinas if m.estado_mantenimiento == 'al_dia'),
        'sin_programar': sum(1 for m in maquinas if m.estado_mantenimiento == 'sin_programar')
    }
    return render_template('calendario.html', maquinas=maquinas, stats=stats,
                           frecuencias=FRECUENCIAS, criticidades=CRITICIDAD, now=datetime.now())


@app.route('/api/proximos-mantenimientos')
def api_proximos_mantenimientos():
    eventos = []
    for m in Maquina.query.all():
        proxima = m.fecha_proximo_mantenimiento or m.proxima_fecha_calculada
        if proxima:
            eventos.append({
                'id': m.id, 'title': f'{m.codigo} - {m.nombre}',
                'start': proxima.isoformat(),
                'backgroundColor': m.criticidad_info['color'],
                'borderColor': m.criticidad_info['color'],
                'extendedProps': {
                    'codigo': m.codigo, 'nombre': m.nombre,
                    'ubicacion': m.ubicacion or '-',
                    'frecuencia': m.frecuencia_nombre,
                    'criticidad': m.criticidad_info['nombre'],
                    'estado': m.estado_mantenimiento,
                    'dias': m.dias_para_proximo
                }
            })
    return jsonify(eventos)


# ==================== DESTINATARIOS ====================

@app.route('/configuracion')
def configuracion():
    destinatarios = Destinatario.query.order_by(Destinatario.nombre).all()
    return render_template('configuracion.html', destinatarios=destinatarios)


@app.route('/destinatario/nuevo', methods=['POST'])
def crear_destinatario():
    nombre = request.form.get('nombre', '').strip()
    email = request.form.get('email', '').strip()
    area = request.form.get('area', '').strip()

    if not nombre or not email:
        flash('Nombre y email obligatorios', 'danger')
        return redirect(url_for('configuracion'))

    if Destinatario.query.filter_by(email=email).first():
        flash(f'El correo {email} ya existe', 'warning')
        return redirect(url_for('configuracion'))

    destinatario = Destinatario(
        nombre=nombre, email=email, area=area,
        recibe_preventivos='recibe_preventivos' in request.form,
        recibe_correctivos='recibe_correctivos' in request.form,
        recibe_vencidos='recibe_vencidos' in request.form,
        activo=True
    )
    db.session.add(destinatario)
    db.session.commit()
    flash(f'Destinatario {nombre} agregado', 'success')
    return redirect(url_for('configuracion'))


@app.route('/destinatario/editar/<int:id>', methods=['POST'])
def editar_destinatario(id):
    d = Destinatario.query.get_or_404(id)
    d.nombre = request.form.get('nombre', '').strip()
    d.email = request.form.get('email', '').strip()
    d.area = request.form.get('area', '').strip()
    d.recibe_preventivos = 'recibe_preventivos' in request.form
    d.recibe_correctivos = 'recibe_correctivos' in request.form
    d.recibe_vencidos = 'recibe_vencidos' in request.form
    db.session.commit()
    flash('Destinatario actualizado', 'success')
    return redirect(url_for('configuracion'))


@app.route('/destinatario/toggle/<int:id>')
def toggle_destinatario(id):
    d = Destinatario.query.get_or_404(id)
    d.activo = not d.activo
    db.session.commit()
    flash(f'Destinatario {d.nombre} {"activado" if d.activo else "desactivado"}', 'info')
    return redirect(url_for('configuracion'))


@app.route('/destinatario/eliminar/<int:id>')
def eliminar_destinatario(id):
    d = Destinatario.query.get_or_404(id)
    nombre = d.nombre
    db.session.delete(d)
    db.session.commit()
    flash(f'Destinatario {nombre} eliminado', 'warning')
    return redirect(url_for('configuracion'))


@app.route('/api/test-email', methods=['POST'])
def test_email():
    try:
        with app.app_context():
            destinatarios = Destinatario.query.filter_by(activo=True).all()
            if not destinatarios:
                return jsonify({'success': False, 'error': 'No hay destinatarios activos'}), 400
            emails = [d.email for d in destinatarios]

            contenido = """
                <p style="font-size:15px;color:#2c3e50;">Este es un correo de prueba del sistema.</p>
                <p style="font-size:14px;color:#2c3e50;">Si lo recibe, la configuración funciona correctamente.</p>
            """
            msg = Message(subject='Prueba de configuración', recipients=emails)
            msg.html = email_wrapper(contenido, 'Prueba de Correo', f'{APP_NAME}', '#1a237e')
            mail.send(msg)
            return jsonify({'success': True, 'enviados': len(emails), 'emails': emails})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerta-vencidos', methods=['POST'])
def alerta_vencidos_manual():
    try:
        maquinas_vencidas = [m for m in Maquina.query.all() if m.estado_mantenimiento == 'vencido']
        if not maquinas_vencidas:
            return jsonify({'success': False, 'error': 'No hay mantenimientos vencidos'}), 400
        threading.Thread(target=enviar_alerta_vencidos, args=(maquinas_vencidas,)).start()
        return jsonify({'success': True, 'enviados': len(maquinas_vencidas)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== API PDF ====================

@app.route('/api/datos-maquinas-pdf')
def datos_maquinas_pdf():
    filtro_tipo = request.args.get('tipo', '')
    filtro_estado = request.args.get('estado', '')
    filtro_busqueda = request.args.get('busqueda', '')
    filtro_ubicacion = request.args.get('ubicacion', '')
    filtro_criticidad = request.args.get('criticidad', '')

    query = Maquina.query
    if filtro_tipo: query = query.filter(Maquina.tipo_codigo == filtro_tipo)
    if filtro_estado: query = query.filter(Maquina.estado == filtro_estado)
    if filtro_ubicacion: query = query.filter(Maquina.ubicacion.like(f'%{filtro_ubicacion}%'))
    if filtro_criticidad: query = query.filter(Maquina.criticidad == filtro_criticidad)
    if filtro_busqueda:
        query = query.filter(db.or_(
            Maquina.nombre.like(f'%{filtro_busqueda}%'),
            Maquina.codigo.like(f'%{filtro_busqueda}%'),
            Maquina.serial.like(f'%{filtro_busqueda}%'),
            Maquina.marca.like(f'%{filtro_busqueda}%')
        ))

    maquinas = query.order_by(Maquina.tipo_codigo, Maquina.codigo).all()

    datos = []
    total_preventivos = 0
    total_correctivos = 0

    for m in maquinas:
        mantenimientos = Mantenimiento.query.filter_by(maquina_id=m.id).all()
        preventivos = sum(1 for x in mantenimientos if x.tipo == 'Preventivo')
        correctivos = sum(1 for x in mantenimientos if x.tipo == 'Correctivo')
        ultimo = m.ultimo_mantenimiento

        datos.append({
            'codigo': m.codigo, 'serial': m.serial or '-',
            'tipo': m.tipo_nombre if m.tipo_codigo else '-',
            'tipo_codigo': m.tipo_codigo or '-',
            'nombre': m.nombre, 'marca': m.marca or '-', 'modelo': m.modelo or '-',
            'ubicacion': m.ubicacion or '-', 'estado': m.estado,
            'frecuencia': m.frecuencia_nombre, 'criticidad': m.criticidad_info['nombre'],
            'total_mant': len(mantenimientos),
            'preventivos': preventivos, 'correctivos': correctivos,
            'ultimo_mant': ultimo.fecha.strftime('%d/%m/%Y') if ultimo and ultimo.fecha else 'Sin registros'
        })
        total_preventivos += preventivos
        total_correctivos += correctivos

    stats_tipo = db.session.query(Maquina.tipo_codigo, db.func.count(Maquina.id)).group_by(Maquina.tipo_codigo).all()

    return jsonify({
        'datos': datos,
        'resumen': {
            'total_maquinas': len(maquinas),
            'total_preventivos': total_preventivos,
            'total_correctivos': total_correctivos,
            'total_mantenimientos': total_preventivos + total_correctivos,
            'por_tipo': [{'tipo': t or 'Sin tipo', 'cantidad': c} for t, c in stats_tipo]
        }
    })


# ==================== ETIQUETAS ====================

TAMANOS_ETIQUETA = {
    'pequena': {'nombre': 'Pequeña', 'ancho': 6, 'alto': 4, 'descripcion': '6 × 4 cm'},
    'mediana': {'nombre': 'Mediana', 'ancho': 10, 'alto': 6, 'descripcion': '10 × 6 cm'},
    'grande': {'nombre': 'Grande', 'ancho': 15, 'alto': 10, 'descripcion': '15 × 10 cm'},
    'a6': {'nombre': 'A6', 'ancho': 10.5, 'alto': 14.8, 'descripcion': '10.5 × 14.8 cm'},
}


@app.route('/etiquetas/<int:maquina_id>')
def etiqueta_individual(maquina_id):
    maquina = Maquina.query.get_or_404(maquina_id)
    tamano = request.args.get('tamano', 'mediana')
    if tamano not in TAMANOS_ETIQUETA:
        tamano = 'mediana'
    return render_template('etiqueta_individual.html', maquina=maquina, tamano=tamano,
                           tamanos=TAMANOS_ETIQUETA, tamano_actual=TAMANOS_ETIQUETA[tamano],
                           now=datetime.now())


@app.route('/etiquetas')
def etiquetas_masivas():
    ids = request.args.get('ids', '')
    tamano = request.args.get('tamano', 'mediana')
    if tamano not in TAMANOS_ETIQUETA:
        tamano = 'mediana'
    maquinas = []
    if ids:
        id_list = [int(x) for x in ids.split(',') if x.strip().isdigit()]
        if id_list:
            maquinas = Maquina.query.filter(Maquina.id.in_(id_list)).order_by(Maquina.codigo).all()
    if not maquinas:
        maquinas = Maquina.query.order_by(Maquina.codigo).all()
    return render_template('etiquetas_masivas.html', maquinas=maquinas, tamano=tamano,
                           tamanos=TAMANOS_ETIQUETA, tamano_actual=TAMANOS_ETIQUETA[tamano])


# ==================== REPORTES ====================

@app.route('/reportes')
def reportes():
    return render_template('reportes.html', maquinas=Maquina.query.all())


@app.route('/api/datos-reporte')
def datos_reporte():
    maquina_id = request.args.get('maquina_id', type=int)
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    tipo = request.args.get('tipo')
    estado = request.args.get('estado')

    query = Mantenimiento.query.join(Maquina)
    if maquina_id: query = query.filter(Mantenimiento.maquina_id == maquina_id)
    if fecha_inicio: query = query.filter(Mantenimiento.fecha >= datetime.strptime(fecha_inicio, '%Y-%m-%d'))
    if fecha_fin: query = query.filter(Mantenimiento.fecha <= datetime.strptime(fecha_fin + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    if tipo and tipo != 'Todos': query = query.filter(Mantenimiento.tipo == tipo)
    if estado and estado != 'Todos': query = query.filter(Mantenimiento.estado == estado)

    mantenimientos = query.order_by(Mantenimiento.fecha.desc()).all()

    datos = []
    for m in mantenimientos:
        datos.append({
            'maquina': m.maquina.nombre, 'codigo': m.maquina.codigo,
            'fecha': m.fecha.strftime('%d/%m/%Y %H:%M') if m.fecha else 'Sin fecha',
            'tipo': m.tipo, 'tecnico': m.tecnico, 'departamento': m.departamento or '-',
            'descripcion': m.descripcion[:100] + '...' if m.descripcion and len(m.descripcion) > 100 else m.descripcion,
            'duracion': m.duracion, 'prioridad': m.prioridad, 'estado': m.estado
        })

    return jsonify({
        'datos': datos,
        'resumen': {
            'total': len(mantenimientos),
            'preventivos': sum(1 for m in mantenimientos if m.tipo == 'Preventivo'),
            'correctivos': sum(1 for m in mantenimientos if m.tipo == 'Correctivo'),
            'completados': sum(1 for m in mantenimientos if m.estado == 'Completado'),
            'pendientes': sum(1 for m in mantenimientos if m.estado == 'Pendiente')
        }
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5500)