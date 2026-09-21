"""
Script para migrar códigos existentes al formato estándar TIPO-NNN
Ejecutar: python migrar_codigos.py
"""
from app import app
from database import db, Maquina, TIPOS_MAQUINA

# Mapeo de códigos especiales al nuevo sistema
MAPEO_ESPECIALES = {
    'SOL-ALU': 'SOL',
    'ARGON': 'ARG',
    'OXIGENO': 'OXI',
    'OXI': 'OXI',
    'GAS': 'GAS',
}


def extraer_tipo(codigo):
    """Extrae el tipo de un código existente"""
    if not codigo:
        return None
    
    codigo_upper = codigo.upper()
    
    # Buscar patrones especiales primero
    for prefijo, nuevo in MAPEO_ESPECIALES.items():
        if codigo_upper.startswith(prefijo):
            return nuevo
    
    # Extraer primera parte antes del guión
    if '-' in codigo:
        return codigo.split('-')[0].upper()
    
    # Si no tiene guión, tomar primeras 3 letras
    return codigo[:3].upper()


def migrar():
    with app.app_context():
        maquinas = Maquina.query.order_by(Maquina.id).all()
        
        print(f"📊 Total de máquinas a procesar: {len(maquinas)}\n")
        
        # Agrupar por tipo para renumerar
        por_tipo = {}
        
        for m in maquinas:
            tipo = extraer_tipo(m.codigo)
            
            if not tipo or tipo not in TIPOS_MAQUINA:
                print(f"⚠️  Tipo desconocido '{tipo}' en '{m.codigo}' → asignando OTR")
                tipo = 'OTR'
            
            if tipo not in por_tipo:
                por_tipo[tipo] = []
            por_tipo[tipo].append(m)
        
        # Renumerar cada grupo
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
                    
                    # Actualizar serial solo si está vacío o es un formato antiguo
                    if not maquina.serial or maquina.serial in ['', 'None']:
                        maquina.serial = nuevo_serial
                    
                    cambios += 1
                else:
                    # Asegurar tipo_codigo aunque el código no cambie
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