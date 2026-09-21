"""
Script para migrar códigos existentes al formato estándar TIPO-NNN
"""
from app import app
from database import db, Maquina, TIPOS_MAQUINA

MAPEO_ESPECIALES = {
    'SOL-ALU': 'SOL',
    'ARGON': 'ARG',
    'OXIGENO': 'OXI',
    'OXI': 'OXI',
    'GAS': 'GAS',
}

def extraer_tipo(codigo):
    if not codigo:
        return None
    codigo_upper = codigo.upper()
    for prefijo, nuevo in MAPEO_ESPECIALES.items():
        if codigo_upper.startswith(prefijo):
            return nuevo
    if '-' in codigo:
        return codigo.split('-')[0].upper()
    return codigo[:3].upper()

def migrar():
    with app.app_context():
        maquinas = Maquina.query.order_by(Maquina.id).all()
        print(f"📊 Total de máquinas a procesar: {len(maquinas)}\n")
        
        por_tipo = {}
        for m in maquinas:
            tipo = extraer_tipo(m.codigo)
            if not tipo or tipo not in TIPOS_MAQUINA:
                print(f"⚠️  Tipo desconocido '{tipo}' en '{m.codigo}' → asignando OTR")
                tipo = 'OTR'
            if tipo not in por_tipo:
                por_tipo[tipo] = []
            por_tipo[tipo].append(m)
        
        cambios = 0
        for tipo, lista in sorted(por_tipo.items()):
            lista.sort(key=lambda x: x.id)
            for i, maquina in enumerate(lista, start=1):
                nuevo_codigo = f'{tipo}-{i:03d}'
                nuevo_serial = f'{tipo}-{i:05d}'
                
                cambio_codigo = maquina.codigo != nuevo_codigo
                cambio_tipo = maquina.tipo_codigo != tipo
                
                if cambio_codigo or cambio_tipo:
                    print(f"🔄 {maquina.codigo:20} → {nuevo_codigo:15} | {maquina.nombre[:40]}")
                    maquina.codigo = nuevo_codigo
                    maquina.tipo_codigo = tipo
                    
                    if not maquina.serial or maquina.serial in ['', 'None']:
                        maquina.serial = nuevo_serial
                    
                    cambios += 1
                else:
                    if not maquina.tipo_codigo:
                        maquina.tipo_codigo = tipo
                        cambios += 1
        
        db.session.commit()
        print(f"\n✅ Migración completada: {cambios} máquinas actualizadas")
        print(f"\n📋 Resumen por tipo:")
        for tipo, lista in sorted(por_tipo.items()):
            print(f"   {tipo:6} ({TIPOS_MAQUINA.get(tipo, '?'):22}): {len(lista)} máquinas")

if __name__ == '__main__':
    migrar()
